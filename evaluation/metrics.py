"""Retrieval metrics. Pure Python, no dependencies, easy to unit-test.

Vocabulary
----------
ranking   list of chunk ids in the order the retriever returned them
relevant  {chunk_id: grade} with grade 2 = contains the answer,
          grade 1 = related / supporting, anything missing = not relevant

Definitions used (state them next to every reported number)
-----------------------------------------------------------
Hit@K        1 if at least one grade-2 chunk is in the top K, else 0.
             This is the number that matters most for RAG: "did the model
             get the chunk it needs?"
Recall@K     grade-2 chunks found in the top K / all grade-2 chunks.
Precision@K  chunks with grade >= 1 in the top K / K.
MRR          1 / rank of the first grade-2 chunk (0 if none is returned).
nDCG@K       graded gain (gain = grade) with log2 discount, divided by the
             best possible DCG for that query.
"""
import math
from statistics import median


def _grade(relevant, chunk_id):
    return relevant.get(chunk_id, 0)


def hit_at_k(ranking, relevant, k):
    return 1.0 if any(_grade(relevant, c) == 2 for c in ranking[:k]) else 0.0


def recall_at_k(ranking, relevant, k):
    wanted = {c for c, g in relevant.items() if g == 2}
    if not wanted:
        return None
    return len(wanted & set(ranking[:k])) / len(wanted)


def precision_at_k(ranking, relevant, k):
    if k <= 0:
        return None
    return sum(1 for c in ranking[:k] if _grade(relevant, c) >= 1) / k


def reciprocal_rank(ranking, relevant):
    for i, c in enumerate(ranking, start=1):
        if _grade(relevant, c) == 2:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranking, relevant, k):
    gains = [_grade(relevant, c) for c in ranking[:k]]
    ideal = sorted(relevant.values(), reverse=True)[:k]
    if not ideal:
        return None
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else None


def score_query(ranking, relevant, k_values):
    """All metrics for one answerable query."""
    out = {"mrr": reciprocal_rank(ranking, relevant)}
    for k in k_values:
        out[f"hit@{k}"] = hit_at_k(ranking, relevant, k)
        out[f"recall@{k}"] = recall_at_k(ranking, relevant, k)
        out[f"precision@{k}"] = precision_at_k(ranking, relevant, k)
        out[f"ndcg@{k}"] = ndcg_at_k(ranking, relevant, k)
    return out


def mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def aggregate(per_query_scores):
    """Average every metric over a list of per-query score dicts."""
    if not per_query_scores:
        return {}
    keys = per_query_scores[0].keys()
    return {k: mean([q[k] for q in per_query_scores]) for k in keys}


def group_by(items, key):
    groups = {}
    for item in items:
        groups.setdefault(item[key], []).append(item)
    return groups


def distance_summary(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    return {"n": len(vals), "min": vals[0], "median": median(vals), "max": vals[-1]}


def threshold_table(answerable_top1, unanswerable_top1, steps=10):
    """For each candidate distance threshold t (abstain when top-1 distance > t):
    share of answerable queries still answered, share of unanswerable ones
    correctly rejected. Lower distance = closer match.
    """
    a = [v for v in answerable_top1 if v is not None]
    u = [v for v in unanswerable_top1 if v is not None]
    if not a or not u:
        return []
    lo, hi = min(a + u), max(a + u)
    rows = []
    for i in range(steps + 1):
        t = lo + (hi - lo) * i / steps
        rows.append({
            "threshold": t,
            "answered_kept": sum(1 for v in a if v <= t) / len(a),
            "unanswerable_rejected": sum(1 for v in u if v > t) / len(u),
        })
    return rows
