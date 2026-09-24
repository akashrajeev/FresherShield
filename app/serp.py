"""Thin SerpApi layer with a local SQLite cache and a call ledger.

Every search the app makes goes through `SerpClient.search`. Responses are cached
on disk keyed by (engine, params), so re-running the same query while building or
demoing costs zero credits. SerpApi also serves identical searches from its own
1-hour cache for free; we keep a longer local cache on top of that.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import serpapi  # official client: pip install serpapi
except ImportError:  # pragma: no cover - only hit when deps are missing
    serpapi = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = ROOT / ".cache" / "serp.sqlite"
FIXTURE_DIR = ROOT / "fixtures"


class SerpError(RuntimeError):
    pass


class OfflineMiss(SerpError):
    """Raised in offline mode when a query has no cached/recorded response."""


def cache_key(engine: str, params: dict[str, Any]) -> str:
    clean = {k: v for k, v in sorted(params.items()) if k not in ("api_key",) and v not in (None, "")}
    blob = json.dumps({"engine": engine, **clean}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


@dataclass
class CallRecord:
    engine: str
    query: str
    source: str  # "live" | "cache" | "fixture"
    ms: int
    at: float = field(default_factory=time.time)


class SerpClient:
    def __init__(
        self,
        api_key: str | None = None,
        cache_path: Path | str | None = None,
        ttl_hours: float | None = None,
        offline: bool | None = None,
        fixture_dir: Path | str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("SERPAPI_API_KEY", "")
        self.ttl = float(ttl_hours if ttl_hours is not None else os.getenv("FS_CACHE_TTL_HOURS", "168")) * 3600
        env_off = os.getenv("FS_OFFLINE", "0") == "1"
        self.offline = offline if offline is not None else (env_off or not self.api_key)
        self.fixture_dir = Path(fixture_dir) if fixture_dir else FIXTURE_DIR
        path = Path(cache_path) if cache_path else DEFAULT_CACHE
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, engine TEXT, query TEXT, fetched_at REAL, body TEXT)"
        )
        self._db.commit()
        self._lock = threading.Lock()
        self.ledger: list[CallRecord] = []

    # ------------------------------------------------------------------ cache
    def _get_cached(self, key: str, allow_stale: bool) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT fetched_at, body FROM responses WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        fetched_at, body = row
        if not allow_stale and time.time() - fetched_at > self.ttl:
            return None
        return json.loads(body)

    def _put_cached(self, key: str, engine: str, query: str, body: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO responses VALUES (?,?,?,?,?)",
                (key, engine, query, time.time(), json.dumps(body, ensure_ascii=False)),
            )
            self._db.commit()

    def _get_fixture(self, key: str) -> dict | None:
        f = self.fixture_dir / f"{key}.json"
        if f.exists():
            return json.loads(f.read_text("utf-8"))
        return None

    # ----------------------------------------------------------------- search
    def search(self, engine: str, **params: Any) -> dict:
        key = cache_key(engine, params)
        q = str(params.get("q", ""))
        t0 = time.time()

        hit = self._get_cached(key, allow_stale=self.offline)
        if hit is not None:
            self.ledger.append(CallRecord(engine, q, "cache", int((time.time() - t0) * 1000)))
            return hit
        fx = self._get_fixture(key)
        if fx is not None:
            self.ledger.append(CallRecord(engine, q, "fixture", int((time.time() - t0) * 1000)))
            return fx
        if self.offline:
            raise OfflineMiss(f"No cached response for {engine} q={q!r} and offline mode is on")
        if serpapi is None:
            raise SerpError("The 'serpapi' package is not installed. Run: pip install -r requirements.txt")

        try:
            client = serpapi.Client(api_key=self.api_key, timeout=40)
            result = client.search({"engine": engine, **params})
            body = result.as_dict() if hasattr(result, "as_dict") else dict(result)
        except Exception as exc:  # network, quota, bad key
            raise SerpError(f"SerpApi {engine} call failed: {exc}") from exc
        if body.get("error") and not _is_empty_result_error(body["error"]):
            raise SerpError(f"SerpApi {engine}: {body['error']}")

        self._put_cached(key, engine, q, body)
        self.ledger.append(CallRecord(engine, q, "live", int((time.time() - t0) * 1000)))
        return body

    def account(self) -> dict | None:
        """Plan and remaining searches. The Account API does not use credits."""
        if self.offline or serpapi is None:
            return None
        try:
            acct = serpapi.Client(api_key=self.api_key, timeout=20).account()
            acct = dict(acct)
        except Exception:
            return None
        keep = ("plan_name", "searches_per_month", "plan_searches_left", "total_searches_left", "this_month_usage")
        return {k: acct.get(k) for k in keep}

    def stats(self) -> dict:
        live = sum(1 for c in self.ledger if c.source == "live")
        cached = sum(1 for c in self.ledger if c.source != "live")
        by_engine: dict[str, int] = {}
        for c in self.ledger:
            by_engine[c.engine] = by_engine.get(c.engine, 0) + 1
        return {"live_calls": live, "cache_hits": cached, "by_engine": by_engine, "offline": self.offline}


def _is_empty_result_error(msg: str) -> bool:
    # SerpApi returns an "error" field when Google simply has no results.
    return "hasn't returned any results" in msg or "no results" in msg.lower()
