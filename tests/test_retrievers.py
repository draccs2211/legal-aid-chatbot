"""Soft-routing retriever and comparison helpers, with fake retrieval (no Chroma)."""
import pytest

from evaluation.retrievers import make_soft_retriever, make_vote_retriever
from evaluation.run_retrieval_eval import comparison_rows


def chunk(cid, domain, dist):
    return {"id": cid, "metadata": {"domain": domain}, "distance": dist, "text": cid}


CORPUS = [
    chunk("rti_x", "rti", 0.50),
    chunk("fir_a", "fir", 0.40),
    chunk("fir_b", "fir", 0.42),
    chunk("ten_x", "tenant", 0.45),
    chunk("ten_y", "tenant", 0.60),
]


class FakeRetrieve:
    """Mimics rag_pipeline.retrieve_chunks over CORPUS and counts calls."""
    def __init__(self):
        self.calls = []

    def __call__(self, query, domain, top_k):
        self.calls.append(domain)
        pool = [c for c in CORPUS if domain is None or c["metadata"]["domain"] == domain]
        return sorted(pool, key=lambda c: c["distance"])[:top_k]


def ids(chunks):
    return [c["id"] for c in chunks]


def test_correct_route_lifts_the_right_domain_above_a_closer_wrong_one():
    soft = make_soft_retriever(FakeRetrieve(), lambda d: d, delta=0.10)
    # unfiltered order is fir_a .40, fir_b .42, ten_x .45; tenant bonus puts ten_x (.35) first
    assert ids(soft("q", "tenant", 3))[0] == "ten_x"


def test_wrong_route_cannot_remove_the_right_chunk():
    """The hard filter would return only 'fir' chunks here and lose rti_x."""
    soft = make_soft_retriever(FakeRetrieve(), lambda d: d, delta=0.10)
    out = ids(soft("q", "fir", 5))
    assert "rti_x" in out


def test_damage_from_a_wrong_route_is_bounded_by_delta():
    soft = make_soft_retriever(FakeRetrieve(), lambda d: d, delta=0.05)
    # fir_a .40 - .05 = .35 beats ten_x .45, but cannot beat anything closer than .35
    top = soft("q", "fir", 2)
    assert ids(top)[0] == "fir_a"
    assert top[0]["adjusted_distance"] == pytest.approx(0.35)


def test_general_domain_is_a_single_unfiltered_search():
    fake = FakeRetrieve()
    soft = make_soft_retriever(fake, lambda d: d, delta=0.10)
    out = soft("q", "general", 3)
    assert fake.calls == [None]
    assert ids(out) == ["fir_a", "fir_b", "ten_x"]


def test_chunks_are_not_duplicated_and_k_is_respected():
    soft = make_soft_retriever(FakeRetrieve(), lambda d: d, delta=0.10)
    out = ids(soft("q", "fir", 4))
    assert len(out) == len(set(out)) == 4


def test_original_distance_is_preserved_next_to_the_adjusted_one():
    soft = make_soft_retriever(FakeRetrieve(), lambda d: d, delta=0.10)
    top = soft("q", "tenant", 1)[0]
    assert top["distance"] == 0.45 and top["adjusted_distance"] == pytest.approx(0.35)


def test_zero_delta_matches_plain_unfiltered_ranking_for_the_top_results():
    soft = make_soft_retriever(FakeRetrieve(), lambda d: d, delta=0.0)
    assert ids(soft("q", "tenant", 3)) == ["fir_a", "fir_b", "ten_x"]


def test_missing_distances_sort_last():
    class NoDist:
        def __call__(self, q, d, k):
            return [{"id": "a", "metadata": {}, "distance": None}, {"id": "b", "metadata": {}, "distance": 0.9}]

    assert ids(make_soft_retriever(NoDist(), lambda d: d, 0.1)("q", "general", 2)) == ["b", "a"]


def test_domain_value_mapping_is_used_for_the_bonus():
    """The router says 'cyber' but chunks are stored as 'cyber_law'."""
    corpus = [chunk("c1", "cyber_law", 0.50), chunk("o1", "fir", 0.45)]
    soft = make_soft_retriever(lambda q, d, k: sorted(corpus, key=lambda c: c["distance"])[:k],
                               lambda d: {"cyber": "cyber_law"}.get(d, d), delta=0.10)
    assert ids(soft("q", "cyber", 2))[0] == "c1"


def test_comparison_rows_pick_the_headline_numbers():
    summary = {"overall": {"hit@5": 0.8, "hit@10": 0.9, "mrr": 0.7, "ndcg@5": 0.6},
               "by_lang": {"en": {"hit@5": 1.0}, "hinglish": {"hit@5": 0.7}}}
    rows = comparison_rows({("baseline", "routed"): summary}, 5)
    assert rows[0]["retriever"] == "baseline" and rows[0]["hit@5"] == 0.8
    assert rows[0]["hit_en"] == 1.0 and rows[0]["hit_hinglish"] == 0.7
    assert rows[0]["hit_devanagari"] is None


# --- vote router ---------------------------------------------------------------
def test_vote_router_picks_the_majority_domain_of_the_top_results_and_boosts_it():
    # unfiltered top-3 is fir_a .40, fir_b .42, ten_x .45  -> 'fir' wins the vote
    vote = make_vote_retriever(FakeRetrieve(), lambda d: d, delta=0.10, vote_k=3)
    out = vote("q", "tenant", 4)            # the keyword router's 'tenant' is ignored
    assert all(c["voted_domain"] == "fir" for c in out)
    assert ids(out)[:2] == ["fir_a", "fir_b"]


def test_vote_ties_go_to_the_better_ranked_chunk():
    corpus = [chunk("a", "x", 0.30), chunk("b", "y", 0.31)]
    vote = make_vote_retriever(lambda q, d, k: sorted(corpus, key=lambda c: c["distance"])[:k],
                               lambda d: d, delta=0.0, vote_k=2)
    assert vote("q", "general", 2)[0]["voted_domain"] == "x"


def test_vote_router_works_without_any_keyword_router_domain():
    vote = make_vote_retriever(FakeRetrieve(), lambda d: d, delta=0.10)
    assert ids(vote("q", None, 2)) and ids(vote("q", "general", 2)) == ids(vote("q", None, 2))


def test_vote_router_falls_back_to_unfiltered_when_nothing_can_be_voted_on():
    class NoMeta:
        def __call__(self, q, d, k):
            return [{"id": "a", "metadata": {}, "distance": 0.1}, {"id": "b", "metadata": {}, "distance": 0.2}]

    out = make_vote_retriever(NoMeta(), lambda d: d, 0.1)("q", "fir", 2)
    assert ids(out) == ["a", "b"] and "voted_domain" not in out[0]


def test_vote_router_maps_metadata_domain_back_through_domain_value():
    """Voting yields stored values (cyber_law); the mapping must accept them."""
    corpus = [chunk("c1", "cyber_law", 0.40), chunk("c2", "cyber_law", 0.41), chunk("o1", "fir", 0.42)]
    vote = make_vote_retriever(lambda q, d, k: [c for c in sorted(corpus, key=lambda c: c["distance"])
                                                if d is None or c["metadata"]["domain"] == d][:k],
                               lambda d: {"cyber": "cyber_law"}.get(d, d), delta=0.1)
    assert ids(vote("q", "general", 3))[0] == "c1"
