"""Embedding-model comparison plumbing, using a fake embedder (no downloads)."""
import hashlib
import math
import re

import pytest

from evaluation import embedders
from evaluation import run_retrieval_eval as R

DIM = 64


def _vec(text):
    v = [0.0] * DIM
    for w in re.findall(r"\w+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def fake_factory(model_name):
    calls = {"docs": 0}

    def embed_docs(texts):
        calls["docs"] += 1
        return [_vec(t) for t in texts]

    info = {"model": model_name, "dimension": DIM, "calls": calls}
    return embed_docs, _vec, info


CHUNKS = [
    {"id": "rti_1", "text": "rti application fee is rs 10", "metadata": {"domain": "rti"}},
    {"id": "rti_2", "text": "rti appeal to first appellate authority", "metadata": {"domain": "rti"}},
    {"id": "fir_1", "text": "how to file an fir at the police station", "metadata": {"domain": "fir"}},
    {"id": "cyb_1", "text": "report online upi fraud on the cyber crime portal", "metadata": {"domain": "cyber_law"}},
]


@pytest.fixture
def retriever():
    docs, query, _ = fake_factory("m")
    coll = embedders.build_index(CHUNKS, docs)
    return embedders.make_index_retriever(coll, query, lambda d: {"cyber": "cyber_law"}.get(d, d))


def ids(chunks):
    return [c["id"] for c in chunks]


def test_unfiltered_search_finds_the_closest_chunk(retriever):
    assert ids(retriever("rti application fee", None, 2))[0] == "rti_1"
    assert ids(retriever("rti application fee", "general", 2))[0] == "rti_1"


def test_domain_filter_restricts_results(retriever):
    out = retriever("file a complaint", "fir", 4)
    assert ids(out) == ["fir_1"]


def test_router_domain_is_translated_to_stored_metadata(retriever):
    assert ids(retriever("upi fraud", "cyber", 3)) == ["cyb_1"]


def test_results_carry_ids_text_metadata_and_distance_sorted_ascending(retriever):
    out = retriever("rti appeal", None, 4)
    assert all({"id", "text", "metadata", "distance"} <= set(c) for c in out)
    d = [c["distance"] for c in out]
    assert d == sorted(d) and len(out) == 4


def test_k_is_respected(retriever):
    assert len(retriever("rti", None, 2)) == 2


def test_e5_models_get_query_and_passage_prefixes_others_do_not():
    assert embedders.model_prefixes("intfloat/multilingual-e5-small") == ("query: ", "passage: ")
    assert embedders.model_prefixes("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") == ("", "")


def test_load_chunks_reads_the_real_corpus():
    from config import DATA_DIR
    chunks = embedders.load_chunks(DATA_DIR)
    assert len(chunks) == 174 and all({"id", "text", "metadata"} <= set(c) for c in chunks)


# --- spec parsing ------------------------------------------------------------
@pytest.mark.parametrize("spec, expected", [
    ("baseline", ("baseline", None, None)),
    ("soft_0.10", ("baseline", 0.10, "soft")),
    ("baseline+soft_0.15", ("baseline", 0.15, "soft")),
    ("st:intfloat/multilingual-e5-small", ("st:intfloat/multilingual-e5-small", None, None)),
    ("st:org/model+soft_0.05", ("st:org/model", 0.05, "soft")),
    ("st:org/model+vote_0.15", ("st:org/model", 0.15, "vote")),
])
def test_parse_spec(spec, expected):
    assert R.parse_spec(spec) == expected


@pytest.mark.parametrize("spec", ["", "st:", "other", "baseline+boost_1", "soft_x", "soft_0.1+soft_0.2", "soft_-0.1", "st:m+vote_x", "st:m+vote_-1", "vote_0.1"])
def test_parse_spec_rejects_bad_input(spec):
    with pytest.raises(ValueError):
        R.parse_spec(spec)


def test_build_retriever_builds_one_index_per_model_and_can_wrap_soft_routing(monkeypatch):
    monkeypatch.setattr(R, "_INDEX_CACHE", {})
    counts = {"n": 0}

    def counting(model):
        counts["n"] += 1
        return fake_factory(model)

    plain, info = R.build_retriever("st:fake/model", embedder_factory=counting)
    soft, _ = R.build_retriever("st:fake/model+soft_0.1", embedder_factory=counting)
    assert counts["n"] == 1 and info["model"] == "fake/model"
    assert plain("rti application fee", "general", 2)[0]["id"].startswith("rti")
    assert "adjusted_distance" in soft("rti application fee", "rti", 2)[0]


# --- parallel experiment -------------------------------------------------------
DATASET = [
    {"id": "a", "query": "x hinglish", "lang": "hinglish", "answerable": True},
    {"id": "b", "query": "y hinglish", "lang": "hinglish", "answerable": True},
]
TRANSLATIONS = {"a": {"en": "x english", "hi": "x hindi"}}


def test_variant_original_keeps_text_but_filters_to_parallel_ids():
    out = R.apply_variant(DATASET, TRANSLATIONS, "original")
    assert [d["id"] for d in out] == ["a"] and out[0]["query"] == "x hinglish"


def test_variants_swap_text_and_language_label():
    en = R.apply_variant(DATASET, TRANSLATIONS, "en")[0]
    hi = R.apply_variant(DATASET, TRANSLATIONS, "hi")[0]
    assert (en["query"], en["lang"]) == ("x english", "en")
    assert (hi["query"], hi["lang"]) == ("x hindi", "devanagari")


def test_unknown_variant_is_rejected():
    with pytest.raises(ValueError):
        R.apply_variant(DATASET, TRANSLATIONS, "fr")


def test_safe_name_is_a_valid_windows_filename():
    assert R.safe_name("st:intfloat/multilingual-e5-small+soft_0.15") == "st_intfloat_multilingual-e5-small_soft_0.15"


def test_build_retriever_supports_vote_routing(monkeypatch):
    monkeypatch.setattr(R, "_INDEX_CACHE", {})
    vote, _ = R.build_retriever("st:fake/model+vote_0.1", embedder_factory=fake_factory)
    out = vote("rti application fee", "general", 3)
    assert out and all("voted_domain" in c for c in out)
