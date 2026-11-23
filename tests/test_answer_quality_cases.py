"""Keeps evaluation/data/answer_quality_cases.json honest: behaviour only, traceable
to a review finding, and no invented dialect sentences."""
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
CASES_PATH = os.path.join(ROOT, "evaluation", "data", "answer_quality_cases.json")
REVIEW_PATH = os.path.join(ROOT, "docs", "ANSWER_REVIEW_2026-11-23.md")

with open(CASES_PATH, encoding="utf-8") as f:
    DATA = json.load(f)
CASES = DATA["cases"]

spec = importlib.util.spec_from_file_location("smoke", os.path.join(ROOT, "scripts", "smoke_test.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
SMOKE_BY_MESSAGE = {c["message"]: c for c in smoke.CASES}

REQUIRED = {"id", "finding", "query", "lang", "risk_level", "answerable", "expected_domain",
            "expected_behaviour", "must_not"}
LANGS = {"en", "hinglish", "hi", "awadhi", "bundeli"}
RISKS = {"none", "possible", "emergency", "self_harm"}


def test_ids_are_unique_and_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"aq\d{3}", i) for i in ids)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_has_the_required_fields_and_valid_values(case):
    assert REQUIRED <= set(case), REQUIRED - set(case)
    assert case["lang"] in LANGS and case["risk_level"] in RISKS
    assert case["expected_behaviour"] and case["must_not"]
    assert all(isinstance(s, str) and s.strip() for s in case["expected_behaviour"] + case["must_not"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_is_behaviour_only_never_expected_legal_text(case):
    forbidden = {"expected_answer", "expected_text", "expected_law", "expected_section", "correct_answer"}
    assert not forbidden & set(case)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_traces_to_a_finding_in_the_review(case):
    with open(REVIEW_PATH, encoding="utf-8") as f:
        review = f.read()
    assert re.search(rf"^### {case['finding']}\. ", review, re.MULTILINE), f"no finding {case['finding']} in review"
    assert f"`{case['id']}`" in review, f"review does not link {case['id']}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_queries_come_from_the_smoke_list_with_the_same_risk_level(case):
    """No new sentences written here, so no invented dialect text (CLAUDE.md safety rule)."""
    smoke_case = SMOKE_BY_MESSAGE.get(case["query"])
    assert smoke_case is not None, "query is not a smoke-test message: add new queries only from real sources"
    assert smoke_case.get("risk") == case["risk_level"]


@pytest.mark.parametrize("case", [c for c in CASES if c["lang"] in {"awadhi", "bundeli"}], ids=lambda c: c["id"])
def test_dialect_cases_say_whether_a_native_speaker_reviewed_them(case):
    assert case.get("dialect_reviewed_by_native_speaker") is False
