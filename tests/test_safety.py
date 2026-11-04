"""Unit tests for backend/safety.py (no network, no API keys)."""
import re

import pytest

from safety import (
    ALERT_LEVELS,
    EMERGENCY,
    NONE,
    POSSIBLE,
    SELF_HARM,
    assess_risk,
    emergency_block,
    normalize,
    possible_footer,
    self_harm_message,
)

# Numbers recorded as verified in docs/verified-helplines.md
VERIFIED = {"112", "1090", "181", "1098", "14416"}


def _numbers(text):
    return set(re.findall(r"\b\d{3,5}\b", text))


# --- normalisation ---------------------------------------------------------
def test_normalize_collapses_repeats_and_punctuation():
    assert normalize("BACHAOOO!!! maaar  raha, hai.") == "bachao mar raha hai"


def test_normalize_keeps_devanagari_matras():
    assert normalize("मुझे  बचाओ!") == "मुझे बचाओ"


def test_empty_and_whitespace_are_none():
    assert assess_risk("")["level"] == NONE
    assert assess_risk("   ")["level"] == NONE
    assert assess_risk(None)["level"] == NONE


# --- levels ----------------------------------------------------------------
@pytest.mark.parametrize(
    "text, level",
    [
        ("I want to end my life", SELF_HARM),
        ("मुझे जीना नहीं है", SELF_HARM),
        ("Pati maar raha hai ghar mein", EMERGENCY),
        ("मेरा पति मुझे मार रहा है बचाओ", EMERGENCY),
        ("What is the punishment for abetment of suicide?", POSSIBLE),
        ("RTI kaise file karein UP mein?", NONE),
    ],
)
def test_levels(text, level):
    assert assess_risk(text)["level"] == level


def test_self_harm_outranks_emergency():
    out = assess_risk("Pati maar raha hai aur main marna chahti hoon")
    assert out["level"] == SELF_HARM


def test_negation_cancels_a_strong_match_but_never_drops_below_possible():
    out = assess_risk("I don't want to die, I just want my deposit back")
    assert out["level"] == POSSIBLE


def test_negation_window_is_too_small_to_hide_a_real_emergency():
    """'nahi' belongs to the police clause, not to 'maar raha hai'."""
    assert assess_risk("police nahi sun rahi, pati maar raha hai")["level"] == EMERGENCY


def test_phrases_with_their_own_negation_are_not_cancelled():
    assert assess_risk("mujhe zinda nahi rehna")["level"] == SELF_HARM
    assert assess_risk("I do not want to live")["level"] == SELF_HARM


def test_whole_word_matching_only():
    # 'kill' must not fire inside another word, 'st'-style fragments neither
    assert assess_risk("I have a skill in drafting")["level"] == NONE


@pytest.mark.parametrize("text", ["bachaooo", "pati mujhe maarr raha hai", "i wanna dieee"])
def test_elongated_and_misspelled_forms_still_match(text):
    assert assess_risk(text)["level"] in ALERT_LEVELS


# --- language hint ---------------------------------------------------------
def test_language_hint():
    assert assess_risk("marna chahta hu")["language_hint"] == "hindi"
    assert assess_risk("I want to end my life")["language_hint"] == "english"
    assert assess_risk("hello")["language_hint"] is None


# --- static messages -------------------------------------------------------
@pytest.mark.parametrize("language", ["english", "hindi"])
def test_emergency_block_uses_only_verified_numbers(language):
    assert _numbers(emergency_block(language)) <= VERIFIED
    assert "112" in emergency_block(language)


@pytest.mark.parametrize("language", ["english", "hindi"])
def test_self_harm_message_points_to_tele_manas_and_112(language):
    msg = self_harm_message(language)
    assert "14416" in msg and "112" in msg
    assert _numbers(msg) <= VERIFIED


@pytest.mark.parametrize("language", ["english", "hindi"])
def test_possible_footer_mentions_112(language):
    assert "112" in possible_footer(language)


def test_hindi_messages_are_devanagari_and_english_are_not():
    dev = re.compile(r"[\u0900-\u097F]")
    assert dev.search(self_harm_message("hindi")) and not dev.search(self_harm_message("english"))
    assert dev.search(emergency_block("hindi")) and not dev.search(emergency_block("english"))


def test_unknown_language_falls_back_to_english():
    assert emergency_block("klingon") == emergency_block("english")


def test_self_harm_message_gives_no_method_or_judgement():
    low = self_harm_message("english").lower()
    for banned in ("how to", "method", "pills", "your fault", "selfish"):
        assert banned not in low
