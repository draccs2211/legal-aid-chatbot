"""scripts/provider_check.py with fake providers: each provider checked on its own,
no fallback, no retry, nothing private printed."""
import importlib.util
import os

import httpx
import openai
import pytest

import sarvam_client
from fakes import fake_client

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("provider_check", os.path.join(HERE, "..", "scripts", "provider_check.py"))
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

KEYS = {"SARVAM_API_KEY": "fake-sarvam-SECRETKEY1", "GROQ_API_KEY": "fake-groq-SECRETKEY2",
        "OPENAI_API_KEY": "fake-openai-SECRETKEY3"}
NAMES = {sarvam_client.SARVAM_BASE_URL: "sarvam", sarvam_client.GROQ_BASE_URL: "groq", None: "openai"}


def status_error(code, message="error"):
    req = httpx.Request("POST", "https://provider.invalid/v1/chat/completions")
    return openai.APIStatusError(message, response=httpx.Response(code, request=req), body=None)


def completion(content):
    msg = type("Msg", (), {"content": content})()
    return type("Completion", (), {"choices": [type("Choice", (), {"message": msg})()]})()


@pytest.fixture
def providers(monkeypatch):
    """outcomes: provider name -> reply text or exception. Records every call."""
    calls = []

    def install(**outcomes):
        def get_client(base_url, api_key, timeout=None):
            name = NAMES[base_url]

            class Completions:
                def create(self, **kwargs):
                    calls.append({"provider": name, "timeout": timeout, **kwargs})
                    outcome = outcomes.get(name, "ok from " + name)
                    if isinstance(outcome, Exception):
                        raise outcome
                    return completion(outcome)

            return fake_client(Completions().create)

        monkeypatch.setattr(sarvam_client, "_get_client", get_client)
        return calls

    for name, value in KEYS.items():
        monkeypatch.setattr(sarvam_client, name, value)
    return install


def run(capsys, *argv):
    code = pc.main(list(argv))
    return code, capsys.readouterr().out


def test_every_provider_is_checked_even_when_an_earlier_one_fails(providers, capsys):
    calls = providers(sarvam=status_error(400), groq=status_error(503))
    code, out = run(capsys)
    assert [c["provider"] for c in calls] == ["sarvam", "groq", "openai"]   # no fallback logic, no retry
    assert code == 1
    assert "http=400" in out and "http=503" in out and "FAILED" in out


def test_all_ok_gives_exit_0_and_a_short_preview(providers, capsys):
    providers()
    code, out = run(capsys)
    assert code == 0
    assert out.count("ok ") >= 3 and "text=yes" in out and "answer: ok from groq" in out


def test_uses_the_production_model_and_request_parameters(providers):
    calls = providers()
    pc.main(["--timeout", "7"])
    for call, provider in zip(calls, sarvam_client._providers()):
        sent = {k: v for k, v in call.items() if k not in ("provider", "timeout", "messages")}
        assert sent == {"model": provider.model, **provider.params}
        assert call["timeout"] == 7.0
        assert call["messages"] == pc.PROMPT


def test_a_provider_without_a_key_is_reported_and_not_called(providers, monkeypatch, capsys):
    monkeypatch.setattr(sarvam_client, "GROQ_API_KEY", "")
    calls = providers()
    code, out = run(capsys)
    assert "groq" not in [c["provider"] for c in calls]
    assert "no key" in out and code == 0


def test_no_keys_at_all_gives_exit_2(providers, monkeypatch, capsys):
    for name in KEYS:
        monkeypatch.setattr(sarvam_client, name, "")
    calls = providers()
    code, out = run(capsys)
    assert code == 2 and calls == [] and "nothing was checked" in out


def test_only_limits_the_providers(providers, capsys):
    calls = providers()
    run(capsys, "--only", "openai")
    assert [c["provider"] for c in calls] == ["openai"]


def test_empty_or_reasoning_only_reply_is_an_error(providers, capsys):
    providers(sarvam="<think>only reasoning</think>")
    code, out = run(capsys, "--only", "sarvam")
    assert code == 1 and "empty_reply" in out


def test_never_prints_keys_or_exception_messages(providers, capsys):
    leaky = status_error(401, message=f"invalid key {KEYS['SARVAM_API_KEY']} for request PROMPTECHO")
    providers(sarvam=leaky)
    _, out = run(capsys)
    assert "SECRETKEY" not in out and "PROMPTECHO" not in out and "invalid key" not in out


def test_answer_preview_is_at_most_80_characters(providers, capsys):
    providers(sarvam="word " * 100)
    _, out = run(capsys, "--only", "sarvam")
    answer_line = next(line for line in out.splitlines() if "answer:" in line)
    assert len(answer_line.split("answer: ", 1)[1]) <= 80


def test_preview_flattens_newlines():
    assert pc.preview("line one\n\nline two") == "line one line two"
