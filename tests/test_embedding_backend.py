"""Flag-gated multilingual embedding backend, with fakes (no model downloads)."""
import hashlib
import math
import re
import sys
import types

import chromadb
import pytest
from fastapi.testclient import TestClient

import config
import embedding
import main
import rag_pipeline

DIM = 64


def _vec(text):
    v = [0.0] * DIM
    for w in re.findall(r"\w+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FakeEmbedder:
    def __init__(self):
        self.doc_calls = 0
        self.query_calls = []

    def embed_documents(self, texts):
        self.doc_calls += 1
        return [_vec(t) for t in texts]

    def embed_query(self, text):
        self.query_calls.append(text)
        return _vec(text)


@pytest.fixture
def external(monkeypatch):
    """Point rag_pipeline at an in-memory Chroma and a fake multilingual embedder."""
    fake = FakeEmbedder()
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(rag_pipeline, "EMBEDDING_BACKEND", "sentence_transformers")
    monkeypatch.setattr(rag_pipeline, "EMBEDDING_MODEL", "fake/model-1")
    monkeypatch.setattr(rag_pipeline, "get_embedder", lambda: fake)
    monkeypatch.setattr(rag_pipeline, "get_client", lambda: client)
    monkeypatch.setattr(rag_pipeline, "_collection", None)
    monkeypatch.setattr(rag_pipeline, "COLLECTION_NAME", "t_" + hashlib.md5(str(id(fake)).encode()).hexdigest()[:8])
    yield fake, client
    monkeypatch.setattr(rag_pipeline, "_collection", None)


# --- configuration ----------------------------------------------------------
def test_choice_accepts_allowed_values_and_rejects_typos(monkeypatch):
    monkeypatch.setenv("SOME_FLAG", "hard")
    assert config._choice("SOME_FLAG", "none", {"hard", "none"}) == "hard"
    monkeypatch.setenv("SOME_FLAG", "hrad")
    with pytest.raises(ValueError, match="SOME_FLAG"):
        config._choice("SOME_FLAG", "none", {"hard", "none"})


def test_defaults_keep_todays_behaviour():
    assert config.EMBEDDING_BACKEND == "chroma_default" and config.ROUTING_MODE == "hard"


def test_collection_name_is_unchanged_by_default_and_model_specific_otherwise(monkeypatch):
    assert rag_pipeline.active_collection_name() == rag_pipeline.COLLECTION_NAME
    monkeypatch.setattr(rag_pipeline, "EMBEDDING_BACKEND", "sentence_transformers")
    monkeypatch.setattr(rag_pipeline, "EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    assert rag_pipeline.active_collection_name().endswith("__intfloat_multilingual_e5_small")


# --- embedder wrapper ---------------------------------------------------------
def test_embedder_applies_e5_prefixes_and_normalises(monkeypatch):
    seen = []

    class _Row:
        def tolist(self):
            return [0.1]

    class _Arr:
        def __init__(self, n):
            self.n = n

        def tolist(self):
            return [[0.1] for _ in range(self.n)]

        def __getitem__(self, i):
            return _Row()

    class FakeST:
        max_seq_length = 512

        def __init__(self, name):
            self.name = name

        def encode(self, texts, normalize_embeddings=False):
            seen.append((list(texts), normalize_embeddings))
            return _Arr(len(texts))

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeST))
    emb = embedding.SentenceTransformerEmbedder("intfloat/multilingual-e5-small")
    emb.embed_documents(["abc"])
    emb.embed_query("मेरा चालान")
    assert seen[0] == (["passage: abc"], True)
    assert seen[1] == (["query: मेरा चालान"], True)
    assert emb.info()["max_seq_length"] == 512


def test_get_embedder_refuses_when_the_backend_is_not_enabled():
    with pytest.raises(RuntimeError):
        embedding.get_embedder()


# --- ingestion and retrieval through the real pipeline code ------------------------
def test_load_all_data_embeds_documents_and_is_idempotent(external):
    fake, _ = external
    assert rag_pipeline.load_all_data() == 174
    assert fake.doc_calls >= 11
    assert rag_pipeline.load_all_data() == 0
    stats = rag_pipeline.get_collection_stats()
    assert stats["total_chunks"] == 174 and stats["embedding_model"] == "fake/model-1"


def test_retrieval_embeds_the_query_and_returns_ids(external):
    fake, _ = external
    rag_pipeline.load_all_data()
    chunks = rag_pipeline.retrieve_chunks("rti application fee kitni hoti hai", top_k=3)
    assert len(chunks) == 3 and all(c["id"] for c in chunks)
    assert fake.query_calls == ["rti application fee kitni hoti hai"]


def test_domain_filter_still_applies_with_the_external_backend(external):
    rag_pipeline.load_all_data()
    chunks = rag_pipeline.retrieve_chunks("phishing upi fraud", domain="cyber", top_k=5)
    assert chunks and all(c["metadata"]["domain"] == "cyber_law" for c in chunks)


def test_a_collection_built_with_another_model_is_refused(external, monkeypatch):
    _, client = external
    client.get_or_create_collection(name=rag_pipeline.active_collection_name(),
                                    metadata={"hnsw:space": "cosine", "embedding_model": "other/model"})
    with pytest.raises(RuntimeError, match="other/model"):
        rag_pipeline.get_collection()


def test_distances_are_cosine_like_production(external):
    """Same query text as a chunk -> distance ~0; unrelated -> close to 1, never ~2."""
    rag_pipeline.load_all_data()
    first = rag_pipeline.retrieve_chunks("zzzz qqqq", top_k=1)[0]
    assert 0.0 <= first["distance"] <= 1.05


# --- routing mode and warm-up in the API ----------------------------------------------
@pytest.fixture
def api(monkeypatch):
    seen = {}
    monkeypatch.setattr(main, "ensure_db_loaded", lambda: None)
    monkeypatch.setattr(main, "retrieve_chunks", lambda **kw: seen.setdefault("domains", []).append(kw["domain"]) or [])
    monkeypatch.setattr(main, "generate_response", lambda **kw: "ok")
    main.sessions.clear()
    return TestClient(main.app), seen


def test_routing_mode_hard_filters_by_the_detected_domain(api, monkeypatch):
    client, seen = api
    monkeypatch.setattr(main, "ROUTING_MODE", "hard")
    client.post("/chat", json={"message": "Mera landlord deposit wapas nahi de raha"})
    assert seen["domains"][0] == "tenant"


def test_routing_mode_none_never_filters(api, monkeypatch):
    client, seen = api
    monkeypatch.setattr(main, "ROUTING_MODE", "none")
    client.post("/chat", json={"message": "Mera landlord deposit wapas nahi de raha"})
    assert seen["domains"][0] is None


def test_warm_up_does_nothing_on_the_default_backend(monkeypatch):
    called = []
    monkeypatch.setattr(main, "get_embedder", lambda: called.append("model"))
    monkeypatch.setattr(main, "ensure_db_loaded", lambda: called.append("db"))
    monkeypatch.setattr(main, "uses_external_embedder", lambda: False)
    main.warm_up()
    assert called == []


def test_warm_up_loads_model_then_index_on_the_external_backend(monkeypatch):
    called = []
    monkeypatch.setattr(main, "get_embedder", lambda: called.append("model"))
    monkeypatch.setattr(main, "ensure_db_loaded", lambda: called.append("db"))
    monkeypatch.setattr(main, "uses_external_embedder", lambda: True)
    main.warm_up()
    assert called == ["model", "db"]


def test_evaluation_index_uses_cosine_space_like_production():
    from evaluation import embedders
    coll = embedders.build_index(
        [{"id": "a", "text": "a", "metadata": {"domain": "d"}}, {"id": "b", "text": "b", "metadata": {"domain": "d"}}],
        lambda texts: [[1.0, 0.0] if t == "a" else [0.0, 1.0] for t in texts])
    res = coll.query(query_embeddings=[[1.0, 0.0]], n_results=2)
    assert [round(x, 3) for x in res["distances"][0]] == [0.0, 1.0]


def test_the_app_runs_warm_up_when_it_starts(monkeypatch):
    called = []
    monkeypatch.setattr(main, "warm_up", lambda: called.append("warm"))
    with TestClient(main.app):
        pass
    assert called == ["warm"]
