"""Metric functions checked against hand-computed values."""
import math

import pytest

from evaluation import metrics as M
from evaluation.run_retrieval_eval import evaluate

REL = {"b": 2, "c": 1}          # b answers the question, c is related
RANKING = ["a", "b", "c"]


def test_hit_at_k():
    assert M.hit_at_k(RANKING, REL, 1) == 0.0
    assert M.hit_at_k(RANKING, REL, 2) == 1.0


def test_grade_one_alone_is_not_a_hit():
    assert M.hit_at_k(["c"], REL, 5) == 0.0


def test_reciprocal_rank():
    assert M.reciprocal_rank(RANKING, REL) == 0.5
    assert M.reciprocal_rank(["x", "y"], REL) == 0.0


def test_recall_at_k_counts_only_grade_two():
    rel = {"x": 2, "y": 2, "z": 1}
    assert M.recall_at_k(["x", "q", "y"], rel, 1) == 0.5
    assert M.recall_at_k(["x", "q", "y"], rel, 3) == 1.0
    assert M.recall_at_k(["x"], {"z": 1}, 3) is None


def test_precision_at_k_counts_grade_one_and_two():
    assert M.precision_at_k(RANKING, REL, 3) == pytest.approx(2 / 3)
    assert M.precision_at_k(RANKING, REL, 1) == 0.0


def test_ndcg_at_k_matches_hand_calculation():
    dcg = 0 / math.log2(2) + 2 / math.log2(3) + 1 / math.log2(4)
    idcg = 2 / math.log2(2) + 1 / math.log2(3)
    assert M.ndcg_at_k(RANKING, REL, 3) == pytest.approx(dcg / idcg)


def test_ndcg_is_one_for_the_ideal_order_and_none_without_relevant_chunks():
    assert M.ndcg_at_k(["b", "c", "a"], REL, 3) == pytest.approx(1.0)
    assert M.ndcg_at_k(["a"], {}, 3) is None


def test_aggregate_ignores_none_values():
    rows = [{"m": 1.0, "n": None}, {"m": 0.0, "n": 0.5}]
    assert M.aggregate(rows) == {"m": 0.5, "n": 0.5}


def test_threshold_table_separates_close_and_far_distances():
    rows = M.threshold_table([0.4, 0.5], [0.8, 0.9], steps=10)
    mid = next(r for r in rows if r["threshold"] == pytest.approx(0.6))
    assert mid["answered_kept"] == 1.0 and mid["unanswerable_rejected"] == 1.0
    assert M.threshold_table([], [0.9]) == []


# --- the runner, with fake retrievers --------------------------------------
DATASET = [
    {"id": "q1", "query": "fee?", "lang": "en", "qtype": "direct", "answerable": True,
     "expected_domain": "rti", "relevant": {"rti_003_fees": 2}, "answer_keywords": ["x"]},
    {"id": "q2", "query": "weather", "lang": "en", "qtype": "unanswerable", "answerable": False,
     "expected_domain": "general", "relevant": {}, "answer_keywords": []},
]


def _perfect(query, domain, k):
    return [{"id": "rti_003_fees", "distance": 0.1}] if query == "fee?" else [{"id": "zzz", "distance": 0.9}]


def test_perfect_retriever_scores_one():
    recs = evaluate(DATASET, _perfect, "unfiltered", 10, [1, 5], router=lambda q: "general")
    ans = recs[0]["scores"]
    assert ans["hit@1"] == 1.0 and ans["mrr"] == 1.0 and ans["ndcg@5"] == pytest.approx(1.0)
    assert "scores" not in recs[1]            # unanswerable queries are not scored
    assert recs[1]["top1_distance"] == 0.9


def test_empty_retriever_scores_zero_without_crashing():
    recs = evaluate(DATASET, lambda q, d, k: [], "unfiltered", 10, [1, 5], router=lambda q: "general")
    assert recs[0]["scores"]["hit@5"] == 0.0 and recs[0]["top1_distance"] is None


def test_modes_pick_the_expected_domain_filter():
    seen = {}

    def spy(query, domain, k):
        seen[(query, domain)] = True
        return []

    evaluate(DATASET, spy, "oracle", 10, [1], router=lambda q: "tenant")
    assert ("fee?", "rti") in seen and ("weather", "general") in seen
    seen.clear()
    evaluate(DATASET, spy, "routed", 10, [1], router=lambda q: "tenant")
    assert ("fee?", "tenant") in seen
    seen.clear()
    evaluate(DATASET, spy, "unfiltered", 10, [1], router=lambda q: "tenant")
    assert ("fee?", "general") in seen
