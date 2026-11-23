"""B1: no error text, keys, paths or stack traces in API responses or in error logs.

Every failure is forced with an exception (or a speech error) whose message is
"bait": fake keys, a server path, the word Traceback and a marker standing in
for user text. Nothing of it may reach the caller or the log line; the caller
gets a fixed message with an error id that also appears in the log.
"""
import importlib.util
import logging
import os
import re

import pytest
from fastapi.testclient import TestClient

import main

ROOT = os.path.join(os.path.dirname(__file__), "..")
spec = importlib.util.spec_from_file_location("smoke", os.path.join(ROOT, "scripts", "smoke_test.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

USER_MARKER = "USERTEXTMARKER"
BAIT = ("sk-FAKESECRET0123456789abcdef gsk_FAKEGROQKEY0123456789 "
        r"C:\dev\nyaymitra\chromadb_store Traceback (most recent call last) " + USER_MARKER)
BAIT_PARTS = ["FAKESECRET", "FAKEGROQKEY", "chromadb_store", "Traceback", USER_MARKER, "Internal error"]
ERROR_ID = re.compile(r"Error id: ([0-9a-f]{8})")


def boom(*args, **kwargs):
    raise RuntimeError(BAIT)


async def async_boom(*args, **kwargs):
    raise RuntimeError(BAIT)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "ensure_db_loaded", lambda: None)
    main.sessions.clear()
    return TestClient(main.app)


def assert_safe(response, caplog, status=500):
    assert response.status_code == status
    body = response.text
    for part in BAIT_PARTS:
        assert part not in body, f"response leaks {part!r}"
    for pattern in smoke.LEAK_PATTERNS:
        assert not re.search(pattern, body), f"response matches leak pattern {pattern!r}"
    log = caplog.text
    for part in BAIT_PARTS:
        assert part not in log, f"log leaks {part!r}"
    return body, log


def assert_has_matching_error_id(body, log, endpoint):
    match = ERROR_ID.search(body)
    assert match, f"no error id in {body!r}"
    assert f"error_id={match.group(1)}" in log
    assert f"endpoint={endpoint}" in log and "error=RuntimeError" in log
    return match.group(1)


def test_chat_failure_is_generic_with_an_error_id(client, monkeypatch, caplog):
    monkeypatch.setattr(main, "retrieve_chunks", boom)
    with caplog.at_level(logging.INFO, logger="nyaymitra.api"):
        r = client.post("/chat", json={"message": f"{USER_MARKER} RTI fees kitni hai?"})
    body, log = assert_safe(r, caplog)
    assert_has_matching_error_id(body, log, "chat")


def test_the_log_keeps_where_it_failed_but_not_the_message(client, monkeypatch, caplog):
    monkeypatch.setattr(main, "retrieve_chunks", boom)
    with caplog.at_level(logging.INFO, logger="nyaymitra.api"):
        client.post("/chat", json={"message": "RTI fees kitni hai?"})
    assert "main.py" in caplog.text and "in chat" in caplog.text   # traceback frames: file, function
    assert "in boom" in caplog.text


def test_translate_failure_is_generic(client, monkeypatch, caplog):
    monkeypatch.setattr(main, "translate_text", boom)
    with caplog.at_level(logging.INFO, logger="nyaymitra.api"):
        r = client.post("/translate", params={"source_text": "hello"})
    body, log = assert_safe(r, caplog)
    assert_has_matching_error_id(body, log, "translate")


def test_stt_exception_is_generic(client, monkeypatch, caplog):
    monkeypatch.setattr(main, "speech_to_text", async_boom)
    with caplog.at_level(logging.INFO, logger="nyaymitra.api"):
        r = client.post("/stt", files={"audio": ("a.webm", b"xx", "audio/webm")})
    body, log = assert_safe(r, caplog)
    assert_has_matching_error_id(body, log, "stt")


def test_tts_exception_is_generic(client, monkeypatch, caplog):
    monkeypatch.setattr(main, "text_to_speech", async_boom)
    with caplog.at_level(logging.INFO, logger="nyaymitra.api"):
        r = client.post("/tts", json={"text": "hello"})
    body, log = assert_safe(r, caplog)
    assert_has_matching_error_id(body, log, "tts")


def test_stt_provider_error_text_never_reaches_the_caller(client, monkeypatch, caplog):
    async def stt_error(*a, **k):
        return {"error": BAIT, "transcript": ""}

    monkeypatch.setattr(main, "speech_to_text", stt_error)
    r = client.post("/stt", files={"audio": ("a.webm", b"xx", "audio/webm")})
    body, _ = assert_safe(r, caplog, status=503)
    assert r.json()["detail"] == main.SPEECH_UNAVAILABLE


def test_tts_provider_error_text_never_reaches_the_caller(client, monkeypatch, caplog):
    async def tts_error(*a, **k):
        return {"error": BAIT}

    monkeypatch.setattr(main, "text_to_speech", tts_error)
    r = client.post("/tts", json={"text": "hello"})
    assert_safe(r, caplog, status=503)
    assert r.json()["detail"] == main.SPEECH_UNAVAILABLE


@pytest.mark.parametrize("path, kwargs", [
    ("/stt", {"files": {"audio": ("a.webm", b"xx", "audio/webm")}}),
    ("/tts", {"json": {"text": "hello"}}),
])
def test_missing_speech_key_does_not_reveal_server_setup(client, path, kwargs, caplog):
    # conftest blanks SARVAM_API_KEY, so the real speech functions report a missing key.
    r = client.post(path, **kwargs)
    assert_safe(r, caplog, status=503)
    assert "key" not in r.text.lower() and "configured" not in r.text.lower()


def test_bad_input_messages_are_unchanged(client):
    assert client.post("/chat", json={"message": "  "}).json()["detail"] == "Message cannot be empty"
    assert client.post("/tts", json={"text": ""}).json()["detail"] == "Text is required"


def test_an_unexpected_error_outside_any_handler_shows_no_traceback(monkeypatch, caplog):
    monkeypatch.setattr(main, "ensure_db_loaded", boom)   # /stats has no try/except
    r = TestClient(main.app, raise_server_exceptions=False).get("/stats")
    assert r.status_code == 500 and r.text == "Internal Server Error"


def test_speech_module_never_returns_exception_text(monkeypatch):
    """sarvam_speech keeps only the error class internally, never str(e)."""
    import asyncio
    import sarvam_speech

    class Exploding:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            raise RuntimeError(BAIT)

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(sarvam_speech, "SARVAM_API_KEY", "fake")
    monkeypatch.setattr(sarvam_speech.httpx, "AsyncClient", Exploding)
    result = asyncio.run(sarvam_speech.speech_to_text(b"xx"))
    assert all(part not in result["error"] for part in BAIT_PARTS)
    assert result["error"] == "RuntimeError"
