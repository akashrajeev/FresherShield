"""Regression guard: the posting layer must keep catching the labelled scams in eval/dataset.jsonl."""
from eval.run_eval import evaluate


def test_posting_layer_accuracy_does_not_regress():
    res = evaluate()
    assert res["n"] >= 40
    assert res["recall"] >= 0.95, res["misses"]      # missing a scam is the costly error
    assert res["precision"] >= 0.9, res["misses"]
