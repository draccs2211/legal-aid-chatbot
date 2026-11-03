"""Tests for backend/intent_detector.py (pure Python, no API keys needed)."""
import pytest

from intent_detector import analyze_query, detect_domain, detect_emergency, detect_language


# ---------------------------------------------------------------------------
# Domain detection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "query, expected",
    [
        ("RTI kaise file karein UP mein?", "rti"),
        ("Police FIR likhne se mana kar rahi hai", "fir"),
        ("Pati maar raha hai ghar mein, kya karoon?", "women_safety"),
        ("Mera landlord deposit wapas nahi de raha", "tenant"),
        ("Challan galat kata hai mera", "traffic"),
        ("Mera makan malik ghar khali karwa raha hai", "tenant"),
    ],
)
def test_domain_detected_for_known_queries(query, expected):
    assert detect_domain(query) == expected


def test_short_keywords_do_not_match_inside_other_words():
    """F-02: 'sic' (an RTI keyword) used to match inside 'music'."""
    q = "Hello, how to file a complaint about my neighbour's loud music"
    assert detect_domain(q) != "rti"


@pytest.mark.parametrize(
    "query",
    [
        "My first posting was in a distant place",   # old code: 'fir' (from 'first'/'st')
        "The classic case of a crisis",              # old code: 'rti' (from 'sic')
        "Please send the transcript",                # old code: 'sc_st' (from 'sc'/'st')
        "I love the music in this movie",            # old code: 'rti' (from 'sic')
    ],
)
def test_text_with_no_legal_content_is_general(query):
    assert detect_domain(query) == "general"


def test_upi_fraud_goes_to_cyber_not_consumer():
    """F-03 (second symptom): 'upi fraud' is a more specific cyber keyword."""
    assert detect_domain("Online UPI fraud hua hai") == "cyber"


def test_unknown_text_is_general():
    assert detect_domain("hello there") == "general"


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
def test_devanagari_is_hindi():
    assert detect_language("मेरा मकान मालिक किराया नहीं लौटा रहा") == "hindi"


def test_plain_english_is_english():
    assert detect_language("How do I file an RTI application?") == "english"


def test_hinglish_markers_hogya_and_aapka_work():
    """F-13: a missing comma glued 'hogya' + 'aapka' into one bogus marker."""
    assert detect_language("mera kaam hogya") == "hindi"
    assert detect_language("aapka kya hai") == "hindi"


# ---------------------------------------------------------------------------
# Emergency detection: behaviour that works today
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "query",
    [
        "Pati maar raha hai ghar mein, kya karoon?",
        "bachao mujhe koi maar raha hai",
        "Someone is trying to kidnap my sister, help me",
    ],
)
def test_clear_emergencies_are_flagged(query):
    assert detect_emergency(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "RTI kaise file karein UP mein?",
        "Mera landlord deposit wapas nahi de raha",
        "How do I check my challan online?",
    ],
)
def test_ordinary_questions_are_not_emergencies(query):
    assert detect_emergency(query) is False


# ---------------------------------------------------------------------------
# Emergency detection: KNOWN DEFECTS (audit finding F-01).
# strict xfail = the test is expected to fail today; when someone fixes the
# behaviour the test starts passing and pytest forces them to remove the marker.
# ---------------------------------------------------------------------------
KNOWN_FALSE_POSITIVES = [
    "I am not in danger, just asking what the danger of defamation law is",
    "What is the rape law punishment under BNS?",
]
KNOWN_FALSE_NEGATIVES = [
    "Mere pati mujhe roz maarte hain",
    "sasur ne mujhe jalane ki dhamki di",
]
SELF_HARM_NOT_HANDLED = [
    "I want to end my life",
    "mujhe zinda nahi rehna",
]


@pytest.mark.xfail(strict=True, reason="F-01: substring keywords, no negation/context handling")
@pytest.mark.parametrize("query", KNOWN_FALSE_POSITIVES)
def test_informational_questions_should_not_trigger_emergency(query):
    assert detect_emergency(query) is False


@pytest.mark.xfail(strict=True, reason="F-01: only some Hindi verb forms are in the keyword list")
@pytest.mark.parametrize("query", KNOWN_FALSE_NEGATIVES)
def test_real_emergencies_should_be_flagged(query):
    assert detect_emergency(query) is True


@pytest.mark.xfail(strict=True, reason="F-01: no self-harm path exists yet (needs its own design and verified helplines)")
@pytest.mark.parametrize("query", SELF_HARM_NOT_HANDLED)
def test_self_harm_should_be_flagged(query):
    assert detect_emergency(query) is True


def test_analyze_query_returns_all_fields():
    out = analyze_query("RTI kaise file karein?")
    assert set(out) == {"language", "domain", "intent", "is_emergency"}
