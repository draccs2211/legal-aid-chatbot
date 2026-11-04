"""Regression suite over tests/data/risk_labelled.json.

The dataset and the rules were written and tuned by the same person, so a pass
here proves the rules are consistent with the labels, NOT that they are
accurate on new messages. See scripts/eval_risk.py for the caveat.
"""
import json
import os

import pytest

from safety import ALERT_LEVELS, assess_risk

PATH = os.path.join(os.path.dirname(__file__), "data", "risk_labelled.json")
with open(PATH, encoding="utf-8") as f:
    DATA = json.load(f)

CASES = [d for d in DATA if not d.get("known_gap")]
GAPS = [d for d in DATA if d.get("known_gap")]


def _id(d):
    return d["text"][:40]


@pytest.mark.parametrize("case", CASES, ids=_id)
def test_label_matches(case):
    assert assess_risk(case["text"])["level"] == case["label"]


@pytest.mark.xfail(strict=True, reason="documented gap: remove the xfail and the known_gap flag once fixed")
@pytest.mark.parametrize("case", GAPS, ids=_id)
def test_known_gaps_are_still_gaps(case):
    assert assess_risk(case["text"])["level"] == case["label"]


def test_every_gap_has_a_note():
    assert all(d.get("note") for d in GAPS)


def test_dataset_covers_all_levels_and_languages():
    assert {d["label"] for d in DATA} == {"none", "possible", "emergency", "self_harm"}
    assert {d["lang"] for d in DATA} == {"en", "hinglish", "devanagari"}
    assert len(DATA) >= 90


def test_no_alert_is_missed_outside_documented_gaps():
    missed = [d["text"] for d in CASES
              if d["label"] in ALERT_LEVELS and assess_risk(d["text"])["level"] not in ALERT_LEVELS]
    assert missed == []


def test_no_benign_message_triggers_an_alert():
    false_alarms = [d["text"] for d in DATA
                    if d["label"] == "none" and assess_risk(d["text"])["level"] in ALERT_LEVELS]
    assert false_alarms == []
