"""End-to-end behaviour of /chat for each risk level, with fakes (no network)."""
import re

import pytest
from fastapi.testclient import TestClient

import main
import sarvam_client

DEVANAGARI = re.compile(r"[\u0900-\u097F]")


@pytest.fixture
def api(monkeypatch):
    calls = {"generate": [], "retrieve": 0}

    def fake_generate(**kwargs):
        calls["generate"].append(kwargs)
        return "model answer"

    def fake_retrieve(**kwargs):
        calls["retrieve"] += 1
        return []

    monkeypatch.setattr(main, "ensure_db_loaded", lambda: None)
    monkeypatch.setattr(main, "retrieve_chunks", fake_retrieve)
    monkeypatch.setattr(main, "generate_response", fake_generate)
    main.sessions.clear()
    return TestClient(main.app), calls


def test_self_harm_returns_static_message_and_skips_retrieval_llm_and_session(api):
    client, calls = api
    r = client.post("/chat", json={"message": "I want to end my life", "session_id": "s1"})
    body = r.json()
    assert r.status_code == 200
    assert body["risk_level"] == "self_harm"
    assert body["is_emergency"] is True
    assert "14416" in body["reply"] and "112" in body["reply"]
    assert calls["generate"] == [] and calls["retrieve"] == 0
    assert "s1" not in main.sessions


def test_hinglish_self_harm_gets_a_hindi_message(api):
    client, _ = api
    body = client.post("/chat", json={"message": "mujhe zinda nahi rehna"}).json()
    assert body["language"] == "hindi"
    assert DEVANAGARI.search(body["reply"])


def test_emergency_calls_the_model_with_the_emergency_flag_and_hindi(api):
    client, calls = api
    body = client.post("/chat", json={"message": "Mere pati mujhe roz maarte hain"}).json()
    assert body["risk_level"] == "emergency" and body["is_emergency"] is True
    assert calls["generate"][0]["is_emergency"] is True
    assert calls["generate"][0]["language"] == "hindi"


def test_possible_adds_footer_after_the_answer_but_not_to_history(api):
    client, _ = api
    body = client.post("/chat", json={"message": "What is the rape law punishment under BNS?", "session_id": "p1"}).json()
    assert body["risk_level"] == "possible" and body["is_emergency"] is False
    assert body["reply"].startswith("model answer")
    assert "112" in body["reply"]
    assert all("112" not in turn["content"] for turn in main.sessions["p1"])


def test_normal_question_gets_no_footer(api):
    client, _ = api
    body = client.post("/chat", json={"message": "RTI kaise file karein UP mein?"}).json()
    assert body["risk_level"] == "none"
    assert body["reply"] == "model answer"


# --- LLM client: behaviour when providers fail or succeed -------------------
@pytest.fixture
def no_keys(monkeypatch):
    for name in ("SARVAM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setattr(sarvam_client, name, "")


def test_all_providers_down_emergency_returns_static_block_in_user_language(no_keys):
    en = sarvam_client.generate_response("help", "ctx", language="english", is_emergency=True, domain="fir")
    hi = sarvam_client.generate_response("bachao", "ctx", language="hindi", is_emergency=True, domain="fir")
    assert "112" in en and not DEVANAGARI.search(en)
    assert "112" in hi and DEVANAGARI.search(hi)


def test_all_providers_down_normal_query_gets_a_safe_error_not_an_invented_answer(no_keys):
    out = sarvam_client.generate_response("RTI fees?", "ctx", language="english", is_emergency=False)
    assert "112" in out and "RTI" not in out


def test_emergency_reply_starts_with_helplines_when_a_provider_answers(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            msg = type("M", (), {"content": "Here is what you can do."})
            return type("R", (), {"choices": [type("C", (), {"message": msg})]})

    fake_client = type("F", (), {"chat": type("Ch", (), {"completions": FakeCompletions()})})
    monkeypatch.setattr(sarvam_client, "SARVAM_API_KEY", "x")
    monkeypatch.setattr(sarvam_client, "_get_client", lambda *a, **k: fake_client)
    out = sarvam_client.generate_response("bachao", "ctx", language="hindi", is_emergency=True)
    assert out.startswith("आपातकालीन हेल्पलाइन")
    assert out.endswith("Here is what you can do.")
