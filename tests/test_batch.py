from fastapi.testclient import TestClient

from app import main
from app.jobs import Job
from app.scam import assess, estimate_searches
from app.serp import SerpClient, cache_key


class FakeLive(SerpClient):
    """Real cache, but 'live' calls return an empty body instead of hitting SerpApi."""

    def __init__(self, path):
        super().__init__(api_key="x", cache_path=path, offline=False, fixture_dir=path.parent / "nofixtures")
        self.live = 0

    def search(self, engine, **params):
        if self.is_cached(engine, **params):
            return super().search(engine, **params)
        self.live += 1
        self._put_cached(cache_key(engine, params), engine, params.get("q", ""), {})
        return {}

    def account(self):
        return {"total_searches_left": 7}


def test_estimate_counts_only_uncached_searches(tmp_path):
    c = FakeLive(tmp_path / "c.sqlite")
    est = estimate_searches(c, ["Acme Corp"])
    assert est["searches"] == 5 and est["cached"] == 0 and c.live == 0  # estimating spends nothing
    assess(c, None, "Acme Corp")
    assert c.live == 5
    est = estimate_searches(c, ["Acme Corp", "Other Co"])
    assert est["per_company"] == {"Acme Corp": 0, "Other Co": 5}
    assert est["searches"] == 5 and est["cached"] == 1


def test_batch_dry_run_reports_cost_and_affordability(tmp_path, monkeypatch):
    c = FakeLive(tmp_path / "c.sqlite")
    monkeypatch.setattr(main, "client", c)
    jobs = [Job(f"j{i}", "Python Developer", co, "Pune", "LinkedIn", "Freshers welcome") for i, co in enumerate(["A1 Tech", "A1 Tech", "B2 Soft"])]
    for j in jobs:
        main._jobs[j.job_id] = j
    r = TestClient(main.app).post("/api/check-batch", json={"job_ids": [j.job_id for j in jobs], "dry_run": True}).json()
    assert r["jobs"] == 3 and r["companies"] == 2 and r["searches"] == 10
    assert r["credits_left"] == 7 and r["affordable"] is False
    assert c.live == 0
    r = TestClient(main.app).post("/api/check-batch", json={"job_ids": [j.job_id for j in jobs]}).json()
    assert set(r["reports"]) == {"j0", "j1", "j2"} and c.live == 10  # duplicate company paid once
