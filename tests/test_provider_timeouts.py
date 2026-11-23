"""B0b: a provider call has a hard wall-clock limit, not only a limit per wait.

httpx's timeout restarts every time a few bytes arrive, so a provider that
trickles its reply never trips it. These tests run a real HTTP server on
127.0.0.1 (allowed by conftest) that sends a valid chat completion 10 bytes
every 0.2 s, and point the real OpenAI SDK + httpx + our code at it.
"""
import json
import logging
import socket
import threading
import time

import pytest

import sarvam_client
from sarvam_client import Provider

REPLY = json.dumps({
    "id": "x", "object": "chat.completion", "created": 0, "model": "m",
    "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
}).encode()
MESSAGES = [{"role": "user", "content": "hi"}]


class TrickleServer:
    """Minimal HTTP server: headers at once, then the body `chunk` bytes every `gap` seconds."""

    def __init__(self, chunk=10, gap=0.2):
        self.chunk, self.gap = chunk, gap
        self.errors, self.handlers = [], []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.1)
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.sock.getsockname()[1]}/v1"

    def _serve(self):
        while not self.stopping.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            t = threading.Thread(target=self._handle, args=(conn,), daemon=True)
            self.handlers.append(t)
            t.start()

    def _handle(self, conn):
        try:
            conn.settimeout(5)
            data = b""
            while b"\r\n\r\n" not in data:
                data += conn.recv(4096)
            head, _, body = data.partition(b"\r\n\r\n")
            length = int(next((line.split(b":")[1] for line in head.split(b"\r\n")
                               if line.lower().startswith(b"content-length")), b"0"))
            while len(body) < length:
                body += conn.recv(4096)
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         b"Content-Length: %d\r\nConnection: close\r\n\r\n" % len(REPLY))
            for i in range(0, len(REPLY), self.chunk):
                if self.stopping.is_set():
                    return
                time.sleep(self.gap)
                conn.sendall(REPLY[i:i + self.chunk])
        except (ConnectionError, OSError):
            pass   # the client gave up and closed the connection: expected
        except Exception as exc:  # pragma: no cover - a bug in the test server itself
            self.errors.append(exc)
        finally:
            conn.close()

    def close(self):
        self.stopping.set()
        self.sock.close()
        self.thread.join(2)
        for t in self.handlers:
            t.join(2)


@pytest.fixture
def server():
    servers = []

    def start(**kwargs):
        s = TrickleServer(**kwargs)
        servers.append(s)
        return s

    yield start
    for s in servers:
        s.close()
        assert s.errors == []
        assert not any(t.is_alive() for t in s.handlers), "a server thread is stuck"


def provider_at(url):
    return Provider("sarvam", "m", "fake-key", url, {"max_tokens": 10})


def test_the_trickle_server_really_takes_longer_than_the_limit(server):
    """Sanity: each gap (0.2 s) is far below the limit, the whole body is ~2.8 s."""
    s = server()
    assert s.gap < 1.0 and (len(REPLY) / s.chunk) * s.gap > 2.0


def test_a_single_call_stops_at_its_limit_even_when_bytes_keep_arriving(server):
    s = server()
    start = time.perf_counter()
    with pytest.raises(Exception) as exc:
        sarvam_client.call_provider_once(provider_at(s.base_url), MESSAGES, timeout=1.0)
    elapsed = time.perf_counter() - start
    assert sarvam_client._classify(exc.value).error == "timeout"
    assert sarvam_client._classify(exc.value).retryable is True
    assert elapsed < 1.5, f"call ran {elapsed:.2f} s with a 1.0 s limit"


def test_a_normal_fast_reply_still_works_on_the_real_socket_path(server):
    s = server(chunk=len(REPLY), gap=0.0)
    assert sarvam_client.call_provider_once(provider_at(s.base_url), MESSAGES, timeout=2.0) == "ok"


@pytest.fixture
def only_sarvam(monkeypatch, server):
    s = server()
    monkeypatch.setattr(sarvam_client, "SARVAM_BASE_URL", s.base_url)
    monkeypatch.setattr(sarvam_client, "SARVAM_API_KEY", "fake-key")
    monkeypatch.setattr(sarvam_client, "LLM_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(sarvam_client, "RETRY_PAUSE_SECONDS", 0.1)
    return s


def test_the_whole_chain_ends_within_its_budget(only_sarvam, monkeypatch):
    monkeypatch.setattr(sarvam_client, "LLM_TOTAL_BUDGET_SECONDS", 2.0)
    start = time.perf_counter()
    reply = sarvam_client.generate_reply("q", "ctx", language="english")
    elapsed = time.perf_counter() - start
    assert reply.provider == "none"
    assert reply.text == sarvam_client.unavailable_message("english")
    assert elapsed < 2.6, f"chain ran {elapsed:.2f} s with a 2.0 s budget"


def test_a_trickling_provider_is_logged_as_timeout_and_retried_once(only_sarvam, monkeypatch, caplog):
    monkeypatch.setattr(sarvam_client, "LLM_TOTAL_BUDGET_SECONDS", 5.0)
    with caplog.at_level(logging.INFO, logger="nyaymitra.llm"):
        sarvam_client.generate_reply("q", "ctx", language="english")
    attempts = [r.getMessage() for r in caplog.records if r.getMessage().startswith("llm_attempt")]
    assert len(attempts) == 2
    assert all("provider=sarvam" in a and "error=timeout" in a for a in attempts)
