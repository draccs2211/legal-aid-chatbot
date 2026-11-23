"""B0a: one slow /chat must not block other users.

FastAPI serves every request on one event loop. An `async def` endpoint that
calls blocking code (the provider chain, retrieval) freezes that loop for
everyone until it returns. These tests run two requests on ONE event loop, the
way the server does, with a fake provider that holds the first request until
the second has finished. No network, no real keys.
"""
import asyncio
import threading
import time

import httpx
import pytest

import main
import sarvam_client

SAFETY_TIMEOUT = 3.0   # a broken build fails after this instead of hanging CI


def completion(content):
    msg = type("Msg", (), {"content": content})()
    return type("Completion", (), {"choices": [type("Choice", (), {"message": msg})()]})()


@pytest.fixture
def slow_provider(monkeypatch):
    """A request whose question contains SLOWQUERY waits until `release` is set
    (or SAFETY_TIMEOUT passes). Any other question is answered at once."""
    state = {"release": threading.Event(), "released_by_timeout": None}

    def get_client(base_url, api_key, timeout=None):
        class Completions:
            def create(self, **kwargs):
                if "SLOWQUERY" in kwargs["messages"][-1]["content"]:
                    state["released_by_timeout"] = not state["release"].wait(SAFETY_TIMEOUT)
                    return completion("slow answer")
                return completion("fast answer")

        return type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()

    monkeypatch.setattr(sarvam_client, "SARVAM_API_KEY", "fake-key")
    monkeypatch.setattr(sarvam_client, "_get_client", get_client)
    monkeypatch.setattr(main, "ensure_db_loaded", lambda: None)
    monkeypatch.setattr(main, "retrieve_chunks", lambda **kw: [])
    main.sessions.clear()
    return state


def run_together(state, slow_message, other_message):
    """Send both requests on one event loop; return (slow, other, finish order, seconds)."""
    order = []

    async def send(client, message, name):
        r = await client.post("/chat", json={"message": message, "session_id": name})
        order.append(name)
        if name == "other":
            state["release"].set()   # the fast request releases the slow one
        return r

    async def main_coro():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            slow_task = asyncio.create_task(send(client, slow_message, "slow"))
            await asyncio.sleep(0.05)   # let the slow request reach the provider first
            other = await send(client, other_message, "other")
            return await slow_task, other

    start = time.perf_counter()
    slow, other = asyncio.run(main_coro())
    return slow, other, order, time.perf_counter() - start


def test_a_fast_request_is_served_while_a_slow_one_waits_on_the_provider(slow_provider):
    slow, other, order, seconds = run_together(slow_provider, "SLOWQUERY RTI fees kitni hai?",
                                               "RTI fees kitni hai?")
    assert slow.status_code == 200 and other.status_code == 200
    assert order == ["other", "slow"], "the second request had to wait for the first"
    assert slow_provider["released_by_timeout"] is False
    assert other.json()["reply"].startswith("fast answer")
    assert slow.json()["reply"].startswith("slow answer")
    assert seconds < SAFETY_TIMEOUT


def test_a_self_harm_message_is_answered_while_a_slow_request_waits(slow_provider):
    slow, other, order, _ = run_together(slow_provider, "SLOWQUERY RTI fees kitni hai?", "I want to end my life")
    assert order == ["other", "slow"]
    assert other.json()["provider"] == "static" and "14416" in other.json()["reply"]
    assert slow_provider["released_by_timeout"] is False


def test_the_database_is_loaded_once_even_when_first_requests_arrive_together(monkeypatch):
    """With /chat in a thread pool, two cold-start requests could both start the load."""
    calls = []

    def slow_load():
        calls.append(1)
        time.sleep(0.2)

    monkeypatch.setattr(main, "load_all_data", slow_load)
    monkeypatch.setattr(main, "db_loaded", False)
    threads = [threading.Thread(target=main.ensure_db_loaded) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1 and main.db_loaded is True
