"""Measure the posting-layer red flags on a labelled set of scam and genuine postings.

    python eval/run_eval.py            # prints metrics, writes eval/results.json
Uses only the posting text (no SerpApi calls, no credits). A posting counts as flagged
when its posting-only risk level is "caution" or "high".
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.jobs import Job  # noqa: E402
from app.scam import assess  # noqa: E402


class NoWeb:
    offline, api_key, ledger = True, "", []

    def search(self, *a, **k):
        raise AssertionError("eval must not call SerpApi")


def evaluate(path: Path = ROOT / "eval" / "dataset.jsonl") -> dict:
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
    tp = fp = tn = fn = 0
    by_lang: dict[str, dict] = {}
    misses = []
    for r in rows:
        rep = assess(NoWeb(), Job("pasted", "", "", "", "", r["text"]), "", use_web=False)
        flagged = rep.level in ("caution", "high")
        scam = r["label"] == "scam"
        tp += scam and flagged
        fn += scam and not flagged
        fp += (not scam) and flagged
        tn += (not scam) and not flagged
        lang = by_lang.setdefault(r["lang"], {"n": 0, "correct": 0})
        lang["n"] += 1
        lang["correct"] += flagged == scam
        if flagged != scam:
            misses.append({"id": r["id"], "label": r["label"], "score": rep.risk_score, "signals": [s.id for s in rep.signals]})
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"n": len(rows), "tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": round(precision, 3),
            "recall": round(recall, 3), "f1": round(f1, 3), "accuracy": round((tp + tn) / len(rows), 3),
            "by_lang": by_lang, "misses": misses}


if __name__ == "__main__":
    res = evaluate()
    (ROOT / "eval" / "results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "misses"}, ensure_ascii=False))
    for m in res["misses"]:
        print("MISS", m)
