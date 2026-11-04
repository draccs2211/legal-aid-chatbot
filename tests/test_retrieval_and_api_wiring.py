"""Wiring tests with fakes: no network, no API keys, no embedding model."""
import pytest
from fastapi.testclient import TestClient

import main
import rag_pipeline


class FakeCollection:
    def __init__(self):
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


@pytest.fixture
def fake_collection(monkeypatch):
    fake = FakeCollection()
    monkeypatch.setattr(rag_pipeline, "get_collection", lambda: fake)
    return fake


def test_cyber_domain_uses_stored_metadata_value(fake_collection):
    """F-03: detector says 'cyber', data stores 'cyber_law'."""
    rag_pipeline.retrieve_chunks("phishing email aaya", domain="cyber")
    assert fake_collection.calls[0]["where"] == {"domain": "cyber_law"}


def test_other_domains_pass_through_unchanged(fake_collection):
    rag_pipeline.retrieve_chunks("rti fees", domain="rti")
    assert fake_collection.calls[0]["where"] == {"domain": "rti"}


def test_general_domain_means_no_filter(fake_collection):
    rag_pipeline.retrieve_chunks("hello", domain="general")
    assert fake_collection.calls[0]["where"] is None


@pytest.fixture
def client(monkeypatch):
    captured = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return "ok reply"

    monkeypatch.setattr(main, "ensure_db_loaded", lambda: None)
    monkeypatch.setattr(main, "retrieve_chunks", lambda **kw: [])
    monkeypatch.setattr(main, "generate_response", fake_generate)
    main.sessions.clear()
    return TestClient(main.app), captured


def test_chat_passes_detected_domain_to_the_llm_layer(client):
    """F-04: main.py used to omit domain=, so the helpline was always 'general'."""
    c, captured = client
    r = c.post("/chat", json={"message": "Mera landlord deposit wapas nahi de raha", "session_id": "t1"})
    assert r.status_code == 200
    assert r.json()["domain"] == "tenant"
    assert captured["domain"] == "tenant"


def test_chat_rejects_empty_message(client):
    c, _ = client
    assert c.post("/chat", json={"message": "   "}).status_code == 400


def test_retrieve_chunks_returns_chunk_ids(monkeypatch):
    """The evaluation harness scores retrieval by chunk id."""
    class Fake:
        def query(self, **kwargs):
            return {"ids": [["rti_003_fees", "rti_006_time_limits"]],
                    "documents": [["a", "b"]],
                    "metadatas": [[{"domain": "rti"}, {"domain": "rti"}]],
                    "distances": [[0.1, 0.2]]}

    monkeypatch.setattr(rag_pipeline, "get_collection", lambda: Fake())
    chunks = rag_pipeline.retrieve_chunks("fee", domain="rti")
    assert [c["id"] for c in chunks] == ["rti_003_fees", "rti_006_time_limits"]


def test_retrieve_chunks_tolerates_a_result_without_ids(monkeypatch):
    class Fake:
        def query(self, **kwargs):
            return {"documents": [["a"]], "metadatas": [[{}]], "distances": [[0.1]]}

    monkeypatch.setattr(rag_pipeline, "get_collection", lambda: Fake())
    assert rag_pipeline.retrieve_chunks("x")[0]["id"] is None
