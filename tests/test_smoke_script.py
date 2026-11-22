"""scripts/smoke_test.py: its checks, and the whole case list against the real app
code with every provider switched off (no network, no keys)."""
import importlib.util
import os
import time

import pytest
from fastapi.testclient import TestClient

import main
import sarvam_client

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("smoke", os.path.join(HERE, "..", "scripts", "smoke_test.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


# --- the checks themselves ---------------------------------------------------------
def ok_body(**kw):
    body = {"reply": "some answer", "risk_level": "none", "domain": "rti"}
    body.update(kw)
    return body


def test_a_good_response_has_no_problems():
    assert smoke.evaluate_case({"risk": "none", "domain": "rti"}, 200, ok_body()) == []


@pytest.mark.parametrize("body, fragment", [
    (ok_body(reply=""), "empty reply"),
    (ok_body(risk_level="emergency"), "risk_level"),
    (ok_body(domain="fir"), "domain"),
    (ok_body(reply="Traceback (most recent call last)"), "leaks"),
    (ok_body(reply="key gsk_abcdefghijklmnopqrstuvwxyz"), "leaks"),
    (ok_body(reply="stored in C:/x/chromadb_store"), "leaks"),
])
def test_problems_are_detected(body, fragment):
    problems = smoke.evaluate_case({"risk": "none", "domain": "rti"}, 200, body)
    assert any(fragment in p for p in problems), problems


def test_wrong_status_stops_further_checks():
    assert smoke.evaluate_case({"risk": "none"}, 500, "boom") == ["status 500, expected 200"]


def test_expected_error_status_passes_and_checks_for_leaks():
    assert smoke.evaluate_case({"expect_status": 400}, 400, {"detail": "empty"}) == []
    assert smoke.evaluate_case({"expect_status": 400}, 400, "Internal error: boom")


def test_required_helpline_and_script_are_checked():
    case = {"in_reply": ["14416"], "devanagari_reply": True}
    problems = smoke.evaluate_case(case, 200, ok_body(reply="call 112"))
    assert any("14416" in p for p in problems) and any("Devanagari" in p for p in problems)


def test_summary_counts_and_latencies():
    results = [{"problems": [], "seconds": 0.1}, {"problems": ["x"], "seconds": 0.5}, {"problems": [], "seconds": 0.3}]
    s = smoke.summarise(results)
    assert (s["passed"], s["total"], s["p50"], s["max"]) == (2, 3, 0.3, 0.5)


def test_unreachable_server_gives_exit_code_2():
    assert smoke.main(["--base-url", "http://127.0.0.1:9", "--timeout", "1"]) == 2


# --- every case against the real app code, providers off ---------------------------------
@pytest.fixture
def adapters(monkeypatch):
    for name in ("SARVAM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setattr(sarvam_client, name, "")
    monkeypatch.setattr(main, "ensure_db_loaded", lambda: None)
    monkeypatch.setattr(main, "retrieve_chunks", lambda **kw: [])
    monkeypatch.setattr(main, "get_collection_stats", lambda: {"total_chunks": 174}, raising=False)
    main.sessions.clear()
    client = TestClient(main.app)

    def timed(fn):
        def wrapper(*args):
            start = time.perf_counter()
            r = fn(*args)
            try:
                body = r.json()
            except ValueError:
                body = r.text
            return r.status_code, body, time.perf_counter() - start
        return wrapper

    return timed(lambda p, d: client.post(p, json=d)), timed(lambda p: client.get(p))


def test_the_whole_case_list_passes_against_the_app_with_providers_off(adapters):
    post, get = adapters
    results = smoke.run(smoke.CASES, post, get)
    failures = {r["name"]: r["problems"] for r in results if r["problems"]}
    assert failures == {}


def test_save_answers_keeps_full_replies_with_hindi_intact(adapters, tmp_path):
    import datetime
    import json

    post, get = adapters
    results = smoke.run(smoke.CASES, post, get)
    path = smoke.save_answers(results, "http://x", directory=str(tmp_path),
                              now=datetime.datetime(2026, 11, 23, 10, 5, 0))
    assert os.path.basename(path) == "smoke_20261123_100500.json"
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    raw = open(path, encoding="utf-8").read()
    assert saved["base_url"] == "http://x" and len(saved["cases"]) == len(smoke.CASES)   # /health, /stats left out
    self_harm = next(c for c in saved["cases"] if c["name"] == "Self-harm (Hinglish)")
    assert self_harm["provider"] == "static" and "14416" in self_harm["reply"]
    assert smoke.DEVANAGARI.search(raw), "Hindi must be stored as text, not \\u escapes"
    assert set(saved["cases"][0]) == {"name", "message", "status", "risk_level", "provider", "seconds",
                                      "problems", "reply"}


def test_save_answers_default_folder_is_ignored_by_git():
    import shutil
    import subprocess

    if shutil.which("git") is None:
        pytest.skip("git not available")
    root = os.path.join(HERE, "..")
    target = os.path.relpath(os.path.join(smoke.ANSWERS_DIR, "smoke_x.json"), root)
    result = subprocess.run(["git", "check-ignore", "-q", target], cwd=root)
    if result.returncode == 128:
        pytest.skip("not a git repository")
    assert result.returncode == 0, f"{target} is not git-ignored"


def test_the_case_list_covers_every_risk_level_and_three_scripts():
    assert {c.get("risk") for c in smoke.CASES} >= {"none", "possible", "emergency", "self_harm"}
    text = " ".join(c["message"] for c in smoke.CASES)
    assert smoke.DEVANAGARI.search(text) and any(c["message"].isascii() for c in smoke.CASES)
