"""The LLM provider chain (backend/sarvam_client.py), with fake providers only.

Covers: order and fallback, the retry policy (timeout, 5xx and 429 retried;
400/401/connection errors never), the per-attempt timeout and the total
budget, reasoning-text removal, safe logging, model names and settings from
env, and that the self-harm path never reaches a provider.
"""
import importlib
import logging
import os
import re

import dotenv
import httpx
import openai
import pytest
from fastapi.testclient import TestClient

import config
import main
import sarvam_client
from fakes import fake_client
from sarvam_client import EmptyReply, extract_answer

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
QUERY = "mera landlord deposit nahi lauta raha UNIQUEQUERY"
CONTEXT = "UNIQUEPASSAGE text"
FAKE_KEYS = {"SARVAM_API_KEY": "fake-sarvam-SECRET1", "GROQ_API_KEY": "fake-groq-SECRET2",
             "OPENAI_API_KEY": "fake-openai-SECRET3"}


# --- fakes ------------------------------------------------------------------------
def _request():
    return httpx.Request("POST", "https://provider.invalid/v1/chat/completions")


def status_error(code, headers=None, message="error"):
    response = httpx.Response(code, request=_request(), headers=headers or {})
    return openai.APIStatusError(message, response=response, body=None)


def timeout_error():
    return openai.APITimeoutError(request=_request())


def connection_error():
    return openai.APIConnectionError(request=_request())


def completion(content):
    message = type("Msg", (), {"content": content, "reasoning_content": "SECRET REASONING",
                               "reasoning": "SECRET REASONING"})()
    choice = type("Choice", (), {"message": message})()
    return type("Completion", (), {"choices": [choice]})()


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeProviders:
    """Scripted outcomes per provider. An outcome is a reply string, an exception,
    or (seconds, outcome) to make the call take that long on the fake clock."""

    NAMES = {config.SARVAM_BASE_URL: "sarvam", config.GROQ_BASE_URL: "groq", None: "openai"}

    def __init__(self, clock, **scripts):
        self.clock = clock
        self.scripts = {name: list(outcomes) for name, outcomes in scripts.items()}
        self.calls = []

    def get_client(self, base_url, api_key, timeout=None):
        name = self.NAMES[base_url]
        fake = self

        class Completions:
            def create(self, **kwargs):
                fake.calls.append({"provider": name, "timeout": timeout, "api_key": api_key, **kwargs})
                script = fake.scripts.get(name) or ["default answer from " + name]
                outcome = script.pop(0) if len(script) > 1 else script[0]
                if isinstance(outcome, tuple):
                    seconds, outcome = outcome
                    if timeout is not None and seconds > timeout:
                        # Like a real client: give up at the timeout.
                        fake.clock.now += timeout
                        raise timeout_error()
                    fake.clock.now += seconds
                if isinstance(outcome, Exception):
                    raise outcome
                return completion(outcome)

        return fake_client(Completions().create)

    def providers_called(self):
        return [c["provider"] for c in self.calls]


@pytest.fixture
def chain(monkeypatch):
    """Returns a function that installs scripted providers and fake time."""
    clock = FakeClock()
    monkeypatch.setattr(sarvam_client, "_clock", clock.clock)
    monkeypatch.setattr(sarvam_client, "_sleep", clock.sleep)
    for name, value in FAKE_KEYS.items():
        monkeypatch.setattr(sarvam_client, name, value)
    monkeypatch.setattr(sarvam_client, "LLM_TIMEOUT_SECONDS", 30.0)
    monkeypatch.setattr(sarvam_client, "LLM_TOTAL_BUDGET_SECONDS", 60.0)
    monkeypatch.setattr(sarvam_client, "LLM_MAX_RETRIES", 1)

    def install(**scripts):
        fake = FakeProviders(clock, **scripts)
        monkeypatch.setattr(sarvam_client, "_get_client", fake.get_client)
        return fake

    install.clock = clock
    return install


def ask(language="english", is_emergency=False):
    return sarvam_client.generate_reply(QUERY, CONTEXT, language=language,
                                        is_emergency=is_emergency, domain="tenant")


# --- order and fallback -------------------------------------------------------------
def test_first_provider_answers_and_no_other_is_called(chain):
    fake = chain(sarvam=["Sarvam answer."])
    reply = ask()
    assert reply == ("Sarvam answer.", "sarvam")
    assert fake.providers_called() == ["sarvam"]


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_client_errors_are_never_retried_and_fall_through(chain, code):
    fake = chain(sarvam=[status_error(code)], groq=["Groq answer."])
    assert ask() == ("Groq answer.", "groq")
    assert fake.providers_called() == ["sarvam", "groq"]
    assert chain.clock.sleeps == []


def test_connection_errors_are_not_retried(chain):
    fake = chain(sarvam=[connection_error()], groq=["Groq answer."])
    assert ask().provider == "groq"
    assert fake.providers_called() == ["sarvam", "groq"]


@pytest.mark.parametrize("error", [timeout_error, lambda: status_error(500), lambda: status_error(503),
                                   lambda: status_error(429)], ids=["timeout", "500", "503", "429"])
def test_retryable_errors_get_one_retry_then_succeed(chain, error):
    fake = chain(sarvam=[error(), "Second try worked."])
    assert ask() == ("Second try worked.", "sarvam")
    assert fake.providers_called() == ["sarvam", "sarvam"]
    assert chain.clock.sleeps == [sarvam_client.RETRY_PAUSE_SECONDS]


def test_retry_cap_then_next_provider(chain):
    fake = chain(sarvam=[status_error(503)], groq=["Groq answer."])
    assert ask().provider == "groq"
    assert fake.providers_called() == ["sarvam", "sarvam", "groq"]


def test_max_retries_zero_means_a_single_attempt(chain, monkeypatch):
    monkeypatch.setattr(sarvam_client, "LLM_MAX_RETRIES", 0)
    fake = chain(sarvam=[timeout_error()], groq=["Groq answer."])
    ask()
    assert fake.providers_called() == ["sarvam", "groq"]


def test_retry_after_is_honoured_but_capped(chain):
    chain(sarvam=[status_error(429, {"retry-after": "2"}), "ok"])
    ask()
    assert chain.clock.sleeps == [2.0]
    chain.clock.sleeps.clear()
    chain(sarvam=[status_error(429, {"retry-after": "120"}), "ok"])
    ask()
    assert chain.clock.sleeps == [sarvam_client.RETRY_AFTER_CAP_SECONDS]


def test_a_provider_without_a_key_is_skipped(chain, monkeypatch):
    monkeypatch.setattr(sarvam_client, "SARVAM_API_KEY", "")
    fake = chain(groq=["Groq answer."])
    assert ask().provider == "groq"
    assert fake.providers_called() == ["groq"]


def test_each_provider_gets_its_own_key(chain):
    fake = chain(sarvam=[status_error(400)], groq=[status_error(400)], openai=["OpenAI answer."])
    assert ask().provider == "openai"
    assert [c["api_key"] for c in fake.calls] == [FAKE_KEYS["SARVAM_API_KEY"], FAKE_KEYS["GROQ_API_KEY"],
                                                 FAKE_KEYS["OPENAI_API_KEY"]]


# --- all providers down -------------------------------------------------------------
@pytest.mark.parametrize("language, devanagari", [("english", False), ("hindi", True)])
def test_all_providers_down_gives_the_safe_message_in_the_users_language(chain, language, devanagari):
    chain(sarvam=[status_error(400)], groq=[status_error(401)], openai=[connection_error()])
    reply = ask(language=language)
    assert reply.provider == "none"
    assert reply.text == sarvam_client.unavailable_message(language)
    assert bool(DEVANAGARI.search(reply.text)) is devanagari


def test_all_providers_down_in_an_emergency_gives_the_static_emergency_block(chain):
    chain(sarvam=[status_error(500)], groq=[status_error(500)], openai=[status_error(500)])
    reply = ask(language="hindi", is_emergency=True)
    assert reply.provider == "none"
    assert reply.text == sarvam_client.emergency_block("hindi")


# --- timeouts and the total budget -------------------------------------------------
def test_each_attempt_gets_the_configured_timeout(chain):
    fake = chain(sarvam=["ok"])
    ask()
    assert fake.calls[0]["timeout"] == 30.0


def test_attempt_timeout_shrinks_to_what_is_left_of_the_budget(chain):
    # Sarvam: 25 s then 400. Groq gets the 30 s timeout, after which 5 s are left.
    fake = chain(sarvam=[(25, status_error(400))], groq=[(30, status_error(400))], openai=["ok"])
    assert ask().provider == "openai"
    assert [c["timeout"] for c in fake.calls] == [30.0, 30.0, 5.0]


def test_total_budget_stops_the_chain(chain):
    fake = chain(sarvam=[(30, timeout_error())], groq=[(30, timeout_error())], openai=["never reached"])
    reply = ask()
    assert reply.provider == "none"
    assert "openai" not in fake.providers_called()
    assert chain.clock.now - 1000.0 <= sarvam_client.LLM_TOTAL_BUDGET_SECONDS


def test_no_retry_when_the_pause_would_exceed_the_budget(chain, monkeypatch):
    monkeypatch.setattr(sarvam_client, "LLM_TOTAL_BUDGET_SECONDS", 10.0)
    fake = chain(sarvam=[(8.5, timeout_error()), "late"], groq=["Groq answer."])
    reply = ask()
    # 1.5 s left: a 1 s pause would leave less than MIN_ATTEMPT_SECONDS, so no retry.
    assert fake.providers_called()[:2] == ["sarvam", "groq"]
    assert chain.clock.sleeps == []
    assert reply.provider == "groq"


def test_sdk_client_has_its_own_retries_off_and_our_timeout():
    client = sarvam_client._get_client("https://api.groq.com/openai/v1", "fake", timeout=12.0)
    assert client.max_retries == 0
    assert client.timeout == 12.0


# --- reasoning text -----------------------------------------------------------------
@pytest.mark.parametrize("raw, expected", [
    ("Plain answer.", "Plain answer."),
    ("<think>secret plan</think>Answer.", "Answer."),
    ("<THINK>a</THINK> A <think>b</think> B", "A  B"),
    ("leaked reasoning without opener</think>Answer.", "Answer."),
    ("Answer.<think>cut off mid-reasoning", "Answer."),
])
def test_reasoning_text_is_removed(raw, expected):
    assert extract_answer(completion(raw)) == expected


def test_separate_reasoning_fields_are_never_used():
    out = extract_answer(completion("Answer."))   # fake also carries reasoning_content / reasoning
    assert "SECRET REASONING" not in out


@pytest.mark.parametrize("raw", [None, "", "   ", "<think>only reasoning</think>", "<think>unclosed"])
def test_a_reply_that_is_only_reasoning_is_empty(raw):
    with pytest.raises(EmptyReply):
        extract_answer(completion(raw))


def test_an_empty_reply_falls_through_without_retry(chain):
    fake = chain(sarvam=["<think>only reasoning</think>"], groq=["Groq answer."])
    assert ask().provider == "groq"
    assert fake.providers_called() == ["sarvam", "groq"]


# --- logging ------------------------------------------------------------------------
def test_logs_have_provider_status_error_latency_and_nothing_private(chain, caplog):
    # The error message echoes the request, as real provider errors can.
    leaky = status_error(400, message=f"bad request: {QUERY} {CONTEXT} {FAKE_KEYS['SARVAM_API_KEY']}")
    chain(sarvam=[(2, leaky)], groq=[(1, "Groq answer.")])
    with caplog.at_level(logging.INFO, logger="nyaymitra.llm"):
        ask()
    text = caplog.text
    for secret in ["UNIQUEQUERY", "UNIQUEPASSAGE", "SECRET", "bad request", "Groq answer"]:
        assert secret not in text, secret
    lines = [r.getMessage() for r in caplog.records if r.name == "nyaymitra.llm"]
    assert lines[0].startswith("llm_attempt provider=sarvam model=") and "status=400" in lines[0]
    assert "error=APIStatusError" in lines[0] and "latency_ms=2000" in lines[0]
    assert "provider=groq" in lines[1] and "outcome=ok" in lines[1] and "latency_ms=1000" in lines[1]


# --- request parameters per provider -----------------------------------------------
def test_request_parameters_match_each_providers_docs(chain):
    fake = chain(sarvam=[status_error(400)], groq=[status_error(400)], openai=["ok"])
    ask()
    sarvam, groq, oai = fake.calls
    assert sarvam["model"] == "sarvam-105b-conversations" and "max_tokens" in sarvam
    assert groq["model"] == "openai/gpt-oss-120b"
    assert groq["reasoning_effort"] == "low" and groq["extra_body"] == {"include_reasoning": False}
    assert oai["model"] == "gpt-6-luna" and oai["reasoning_effort"] == "none"
    assert "max_completion_tokens" in oai and "temperature" not in oai and "max_tokens" not in oai


def test_older_models_get_no_reasoning_parameters(chain, monkeypatch):
    monkeypatch.setattr(sarvam_client, "GROQ_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(sarvam_client, "OPENAI_MODEL", "gpt-4o-mini")
    fake = chain(sarvam=[status_error(400)], groq=[status_error(400)], openai=["ok"])
    ask()
    _, groq, oai = fake.calls
    assert "reasoning_effort" not in groq and "extra_body" not in groq
    assert "reasoning_effort" not in oai and "temperature" in oai


# --- settings from env ----------------------------------------------------------------
@pytest.fixture
def reload_config(monkeypatch):
    """Reload config with given env vars and WITHOUT reading the real .env, then restore."""
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)

    def _reload(**env):
        for name in ("SARVAM_MODEL", "GROQ_MODEL", "OPENAI_MODEL", "LLM_TIMEOUT_SECONDS",
                     "LLM_TOTAL_BUDGET_SECONDS", "LLM_MAX_RETRIES"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return importlib.reload(config)

    yield _reload
    for name in ("SARVAM_MODEL", "GROQ_MODEL", "OPENAI_MODEL", "LLM_TIMEOUT_SECONDS",
                 "LLM_TOTAL_BUDGET_SECONDS", "LLM_MAX_RETRIES"):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(config)


def test_code_defaults(reload_config):
    c = reload_config()
    assert (c.SARVAM_MODEL, c.GROQ_MODEL, c.OPENAI_MODEL) == (
        "sarvam-105b-conversations", "openai/gpt-oss-120b", "gpt-6-luna")
    assert (c.LLM_TIMEOUT_SECONDS, c.LLM_TOTAL_BUDGET_SECONDS, c.LLM_MAX_RETRIES) == (30.0, 60.0, 1)


def test_model_names_and_limits_come_from_env(reload_config):
    c = reload_config(SARVAM_MODEL="sarvam-105b", GROQ_MODEL="g", OPENAI_MODEL="gpt-4o-mini",
                      LLM_TIMEOUT_SECONDS="12.5", LLM_TOTAL_BUDGET_SECONDS="40", LLM_MAX_RETRIES="0")
    assert (c.SARVAM_MODEL, c.GROQ_MODEL, c.OPENAI_MODEL) == ("sarvam-105b", "g", "gpt-4o-mini")
    assert (c.LLM_TIMEOUT_SECONDS, c.LLM_TOTAL_BUDGET_SECONDS, c.LLM_MAX_RETRIES) == (12.5, 40.0, 0)


@pytest.mark.parametrize("env", [
    {"LLM_TIMEOUT_SECONDS": "thirty"}, {"LLM_TIMEOUT_SECONDS": "0"},
    {"LLM_TOTAL_BUDGET_SECONDS": "-5"}, {"LLM_MAX_RETRIES": "1.5"}, {"LLM_MAX_RETRIES": "-1"},
])
def test_bad_settings_fail_fast_at_startup(reload_config, env):
    with pytest.raises(ValueError, match=next(iter(env))):
        reload_config(**env)


def test_default_budget_is_shorter_than_the_frontends_chat_timeout():
    app_js = os.path.join(os.path.dirname(__file__), "..", "frontend", "app.js")
    with open(app_js, encoding="utf-8") as f:
        source = f.read()
    chat_call = source[source.index("/chat`"):]
    frontend_ms = int(re.search(r"AbortSignal\.timeout\((\d+)\)", chat_call).group(1))
    assert config.LLM_TOTAL_BUDGET_SECONDS * 1000 < frontend_ms


# --- the API reports who answered; self-harm never reaches a provider -----------------
@pytest.fixture
def api_with_real_chain(monkeypatch, chain):
    monkeypatch.setattr(main, "ensure_db_loaded", lambda: None)
    monkeypatch.setattr(main, "retrieve_chunks", lambda **kw: [])
    main.sessions.clear()
    return TestClient(main.app), chain


def test_chat_reports_which_provider_answered(api_with_real_chain):
    client, chain = api_with_real_chain
    chain(sarvam=[status_error(400)], groq=["Groq answer."])
    body = client.post("/chat", json={"message": "RTI fees kitni hai?"}).json()
    assert body["provider"] == "groq" and body["reply"].startswith("Groq answer.")


def test_chat_reports_none_when_every_provider_fails(api_with_real_chain):
    client, chain = api_with_real_chain
    chain(sarvam=[status_error(400)], groq=[status_error(400)], openai=[status_error(400)])
    body = client.post("/chat", json={"message": "RTI fees kitni hai?"}).json()
    assert body["provider"] == "none"


@pytest.mark.parametrize("message", ["I want to end my life", "mujhe zinda nahi rehna"])
def test_self_harm_never_calls_a_provider(api_with_real_chain, monkeypatch, message):
    client, _ = api_with_real_chain
    # Keys are set (fixture), so the chain WOULD run if it were reached. Every way
    # to a provider explodes, and retrieval too.
    def boom(*a, **k):
        raise AssertionError("a provider was called on the self-harm path")

    monkeypatch.setattr(sarvam_client, "_get_client", boom)
    monkeypatch.setattr(sarvam_client, "_run_chain", boom)
    monkeypatch.setattr(sarvam_client.openai, "AsyncOpenAI", boom)
    monkeypatch.setattr(sarvam_client, "call_provider_once", boom)
    monkeypatch.setattr(main, "retrieve_chunks", boom)
    body = client.post("/chat", json={"message": message, "session_id": "sh"}).json()
    assert body["risk_level"] == "self_harm"
    assert body["provider"] == "static"
    assert "14416" in body["reply"]
    assert "sh" not in main.sessions
