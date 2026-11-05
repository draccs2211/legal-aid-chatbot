"""Risk assessment and static safety messages for NyayMitra.

Why this module exists (audit finding F-01)
-------------------------------------------
The old emergency check was a substring list: it fired on "danger" inside a
question about defamation law and stayed silent on "Mere pati mujhe roz maarte
hain". This module replaces it with four explicit levels:

    none        normal question, normal answer
    possible    risk words present but no sign of immediate danger
                -> normal answer + a short "call 112 if in danger" footer
    emergency   someone appears to be in immediate danger
                -> helplines FIRST, in the user's language
    self_harm   the person may be thinking of ending their life
                -> static supportive message only; no retrieval, no LLM

Design rules
------------
* A false alarm costs one extra helpline line. A missed emergency can cost far
  more. When unsure, round UP (towards `possible`), never down to `none`.
* Everything here is deterministic and runs without any API key, so it keeps
  working when every LLM provider is down.
* Only helpline numbers recorded in docs/verified-helplines.md are used here.
* This is a rule-based first line of defence, not a guarantee. It will miss
  indirect phrasing; see tests/data/risk_labelled.json (`known_gap` cases).
"""
import re
import unicodedata

NONE = "none"
POSSIBLE = "possible"
EMERGENCY = "emergency"
SELF_HARM = "self_harm"

ALERT_LEVELS = (EMERGENCY, SELF_HARM)


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------
_PUNCT = re.compile(r"[.,!?;:()\[\]{}\"'\u2018\u2019\u201c\u201d\u0964|/\\\-_*#@~^<>=+]+")
_REPEATED_LETTER = re.compile(r"([a-z])\1+")
# Same collapse for regex sources, but never touch escapes such as \s or \b.
_REPEATED_LETTER_IN_PATTERN = re.compile(r"(?<!\\)([a-z])\1+")


def normalize(text: str) -> str:
    """Lowercase, NFKC, punctuation -> spaces, collapse repeated Latin letters.

    Collapsing makes "bachaooo", "maaar" and "maar" comparable. The same
    collapse is applied to every pattern below, so both sides stay consistent.
    Devanagari is left intact (matras must not be stripped).
    """
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = _PUNCT.sub(" ", t)
    t = _REPEATED_LETTER.sub(r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def _compile(source: str):
    source = unicodedata.normalize("NFKC", source)
    source = _REPEATED_LETTER_IN_PATTERN.sub(r"\1", source)
    # Whole-token match: text is already split on whitespace.
    return re.compile(r"(?<!\S)(?:" + source + r")(?!\S)")


# ---------------------------------------------------------------------------
# Pattern tables.  Each entry: (regex, language, immune_to_negation)
#   language: "en" or "hi" (hi = Hindi, Hinglish or Devanagari)
#   immune: the phrase contains its own negation ("jeena nahi chahta"),
#           so the negation check must not cancel it.
# Written in ordinary spelling; _compile() collapses repeated letters.
# ---------------------------------------------------------------------------
_SELF_HARM_STRONG = [
    # English
    (r"kill\s+(?:my\s*self|myself)", "en", False),
    (r"end\s+(?:my\s+life|it\s+all)", "en", False),
    (r"take\s+my\s+(?:own\s+)?life", "en", False),
    (r"commit\s+suicide", "en", False),
    (r"suicidal", "en", False),
    (r"(?:thinking|thought|think)\s+(?:of|about)\s+suicide", "en", False),
    (r"want(?:ed|s)?\s+to\s+die", "en", False),
    (r"wanna\s+die", "en", False),
    (r"going\s+to\s+die\s+by\s+suicide", "en", False),
    (r"(?:hurt|harm)\s+my\s*self", "en", False),
    (r"better\s+off\s+dead", "en", False),
    (r"suicide\s+note", "en", False),
    (r"(?:tried|attempted|trying)\s+to\s+(?:kill\s+my\s*self|commit\s+suicide|end\s+my\s+life)", "en", False),
    (r"(?:dont|don\s+t|do\s+not)\s+want\s+to\s+(?:live|be\s+alive|be\s+here|exist)", "en", True),
    (r"no\s+reason\s+to\s+live", "en", True),
    (r"(?:cant|can\s+t|cannot)\s+(?:go\s+on|live\s+like\s+this)", "en", True),
    # Hinglish (Roman script)
    (r"jaan\s+de\s+(?:dunga|dungi|du|dena|dene)", "hi", False),
    (r"apni\s+jaan\s+(?:de|le|lunga|lungi|dunga|dungi)", "hi", False),
    (r"(?:khud|khudh)\s*(?:kushi|khushi)\s+(?:kar|karna|karne|karunga|karungi|karlunga|karlungi)", "hi", False),
    (r"(?:khud|khudh)\s*(?:kushi|khushi)\s+(?:ki\s+)?koshish", "hi", False),
    (r"(?:aatma|atma)\s*hatya\s+(?:kar|karna|karne|karunga|karungi)", "hi", False),
    (r"suicide\s+(?:kar|karna|karne|karunga|karungi|karlunga|karlungi|karun)\S*", "hi", False),
    (r"mar\s+jaana\s+chah(?:ta|ti|te)", "hi", False),
    (r"marna\s+chah(?:ta|ti|te)", "hi", False),
    (r"mar\s+jaun(?:ga|gi)?", "hi", False),
    (r"marne\s+ka\s+(?:man|mann|mood)", "hi", False),
    (r"(?:jeena|jina|jeene|jine)\s+(?:nahi|nhi|nahin)\s+chah\S*", "hi", True),
    (r"(?:jeene|jine)\s+ka\s+(?:man|mann|dil)\s+(?:nahi|nhi|nahin)", "hi", True),
    (r"(?:jeena|jina)\s+(?:nahi|nhi|nahin)\s+(?:hai|h|he)", "hi", True),
    (r"(?:zinda|jinda|zindagi|jindagi)\s+(?:nahi|nhi|nahin)\s+(?:rehna|rahna|reh|rah)\S*", "hi", True),
    (r"(?:zindagi|jindagi|life)\s+khatam\s+kar\S*", "hi", False),
    (r"khud\s+ko\s+khatam\s+kar\S*", "hi", False),
    # Devanagari
    (r"जान\s+दे\s+दूं(?:गा|गी)", "hi", False),
    (r"जान\s+दे\s+दूँ(?:गा|गी)", "hi", False),
    (r"(?:खुदकुशी|आत्महत्या)\s+(?:कर|करना|करने|करूंगा|करूंगी|करूँगा|करूँगी)\S*", "hi", False),
    (r"(?:खुदकुशी|आत्महत्या)\s+की\s+कोशिश", "hi", False),
    (r"मरना\s+चाह(?:ता|ती|ते)", "hi", False),
    (r"मर\s+जाना\s+चाह(?:ता|ती|ते)", "hi", False),
    (r"खुद\s+को\s+खत्म\s+कर\S*", "hi", False),
    (r"(?:जीना|जीने)\s+नहीं\s+(?:चाह\S*|है|हैं)", "hi", True),
    (r"जीने\s+का\s+मन\s+नहीं", "hi", True),
    (r"(?:ज़िंदा|ज़िन्दा|जिंदा|जिन्दा|जिंदगी|ज़िंदगी)\s+नहीं\s+रह\S*", "hi", True),
    # Awadhi / Bundeli (best-effort, pending native-speaker review; see docs/language-support.md)
    (r"(?:मरै|मरब|मरिबे|मरबे|मरबो)\s+(?:\S+\s+){0,1}(?:चाह|चात|चाउ)\S*", "hi", False),
    (r"मर\s+(?:जाब|जइब|जैहों|जैहौं|जाहों)", "hi", False),
    (r"(?:जियै|जिए|जीबे|जीबो)\s+(?:का|क|को|के)\s+(?:मन|मनवा|दिल)\s+(?:नाहीं|नाही|नईं|नइ|नहीं)", "hi", True),
    (r"(?:जिए|जियै|जीबो|जीवै)\s+(?:नाहीं|नाही|नईं)\s+(?:चाह|चात|चाउ)\S*", "hi", True),
    (r"(?:आतमहत्या|आत्महत्या)\s+(?:कइ|कर|करि)\s+(?:लेब|लेहौं|लैहों|लूँगा|लूंगा)", "hi", False),
    (r"(?:जहर|ज़हर)\s+(?:खाय|खाइ|खा)\s+(?:लेब|लेहौं|लैहों|लूँगा|लूंगा)", "hi", False),
    (r"फांसी\s+(?:लगाय|लगा|लगाइ)\s+(?:लेब|लेहौं|लैहों|लूँगा|लूंगा)", "hi", False),
    (r"jaan\s+de\s+deb", "hi", False),
    (r"mar(?:ai|ae|e)\s+chah\S*", "hi", False),
    (r"marbo\s+chah\S*", "hi", False),
]

# Mentions that need a gentle footer but are not, by themselves, a crisis
# (for example a legal question about abetment of suicide).
_SELF_HARM_WEAK = [
    (r"suicide", "en", False),
    (r"(?:khud|khudh)\s*(?:kushi|khushi)", "hi", False),
    (r"(?:aatma|atma)\s*hatya", "hi", False),
    (r"खुदकुशी", "hi", False),
    (r"आत्महत्या", "hi", False),
]

_EMERGENCY_STRONG = [
    # English
    (r"save\s+me", "en", False),
    (r"someone\s+help", "en", False),
    (r"help\s+me\s+(?:now|immediately|quickly)", "en", False),
    (r"need\s+help\s+(?:now|immediately|urgently|urgent|right\s+now)", "en", False),
    (r"(?:is|are|s|re|am\s+being|was\s+being)\s+(?:beating|hitting|attacking|assaulting|stabbing|strangling|choking|burning|raping|molesting)", "en", False),
    (r"(?:keeps?|kept|started|starts?|continues?)\s+(?:beating|hitting|attacking|strangling|choking)\s+(?:me|her|him|us)", "en", False),
    (r"(?:going|want|wants|trying|threaten(?:ed|ing|s)?|plans?)\s+(?:to\s+)?kill\s+(?:me|us|him|her|them|my\s+\w+)", "en", False),
    (r"kill\s+me", "en", False),
    (r"(?:trying|tried|threaten(?:ed|ing)?)\s+to\s+(?:kidnap|rape|molest|burn|stab|shoot|strangle|abduct)", "en", False),
    (r"(?:was|got|been|being|is|are)\s+(?:kidnapped|abducted)", "en", False),
    (r"(?:i\s+am|im|i\s+m|was|got)\s+(?:being\s+)?raped", "en", False),
    (r"raped\s+me", "en", False),
    (r"(?:broke|breaking|break)\s+into\s+(?:my\s+)?(?:house|home|room)", "en", False),
    (r"(?:pulled|showed|pointed|pointing|waving)\s+(?:a\s+|his\s+|her\s+|the\s+)?(?:gun|knife|pistol|weapon)", "en", False),
    (r"(?:gun|knife|pistol)\s+(?:at|to)\s+(?:me|my|us)", "en", False),
    (r"(?:threw|throw|thrown)\s+acid", "en", False),
    (r"set\s+(?:me|her|him|us)\s+on\s+fire", "en", False),
    (r"locked\s+(?:me|her|him)\s+(?:in|up)", "en", False),
    (r"fear\s+for\s+my\s+life", "en", False),
    # Hinglish (Roman script)
    (r"bachao", "hi", False),
    (r"bacha\s+lo", "hi", False),
    (r"bachaiye", "hi", False),
    (r"(?:jaldi|turant|abhi)\s+madad", "hi", False),
    (r"(?:maar|peet|pit|marpeet|maar\s*peet)\s+(?:raha|rahe|rahi)", "hi", False),
    (r"(?:maar|peet|pit)\s+(?:kar|ke)\s+(?:raha|rahe|rahi)", "hi", False),
    (r"(?:maar|marta|marte|peet|peeta|peete|peetta|peette)\s+(?:hai|hain|h)", "hi", False),
    (r"maarta\s+(?:hai|hain|h)", "hi", False),
    (r"maarte\s+(?:hai|hain|h)", "hi", False),
    (r"(?:mujhe|mujhko|mereko|use|usko|bachche\s+ko|bachchon\s+ko)\s+(?:bahut\s+|roz\s+|bahot\s+)?(?:maara|mara|maar\s+diya|pita|peeta|peet\s+diya)", "hi", False),
    (r"maar\s+(?:dala|diya|dalega|dega|denge|dunga|dalunga|dalenge|daalunga|daalega)", "hi", False),
    (r"jaan\s+se\s+(?:maar|mar)\S*", "hi", False),
    (r"jaan\s+(?:ka\s+khatra|lega|le\s+lega|le\s+lunga|le\s+lenge)", "hi", False),
    (r"kaat\s+(?:dunga|dega|denge|dalunga|dalega)", "hi", False),
    (r"jala\s+(?:dunga|dega|denge|dungi|diya|dalega|dalunga|dene)", "hi", False),
    (r"jalane\s+(?:ki|ka)\s+(?:dhamki|koshish)", "hi", False),
    (r"aag\s+laga\s+(?:di|diya|dunga|dega|denge)", "hi", False),
    (r"utha\s+(?:liya|liye|le\s+gaye|le\s+gaya|le\s+gayi|ke\s+le\s+gaye|le\s+gaye\s+hain)", "hi", False),
    (r"apaharan\s+(?:kar|ho|hua)\S*", "hi", False),
    (r"kidnap\s+(?:kar\s+liya|kar\s+liye|ho\s+gaya|ho\s+gayi|kar\s+rahe|kar\s+raha)", "hi", False),
    (r"ghar\s+(?:mein|me|main|ma|maa)\s+(?:\S+\s+){0,3}ghus\S*", "hi", False),
    (r"(?:chaku|chakoo|pistol|bandook|tamancha|katta|talwar|gun|knife)\s+(?:dikha\S*|se|lekar|le\s+kar|laga\S*|nikal\S*|tan\S*)", "hi", False),
    (r"(?:rape|balatkar)\s+(?:kar\s+diya|kar\s+di|ho\s+gaya|hua|hui|kiya)", "hi", False),
    (r"khoon\s+(?:beh|bah|nikal|aa)\S*", "hi", False),
    (r"mar\s*peet\s+(?:ho|kar)\s+(?:raha|rahi|rahe)", "hi", False),
    # Devanagari
    (r"बचाओ", "hi", False),
    (r"बचा\s+लो", "hi", False),
    (r"(?:मार|पीट)\s+रह[ाेी]", "hi", False),
    (r"(?:मारत|पीटत)[ाे]\s+(?:है|हैं)", "hi", False),
    (r"(?:मुझे|मुझको)\s+(?:बहुत\s+|रोज\s+|रोज़\s+)?(?:मारा|पीटा)", "hi", False),
    (r"मार\s+(?:दिया|डाला|दूंगा|दूँगा|देगा|डालूंगा|डालेगा)", "hi", False),
    (r"जान\s+से\s+(?:मार|मर)\S*", "hi", False),
    (r"जान\s+का\s+खतरा", "hi", False),
    (r"जला\s+(?:दूंगा|दूँगा|देगा|दिया|दूंगी|डालेगा)", "hi", False),
    (r"जलाने\s+की\s+(?:धमकी|कोशिश)", "hi", False),
    (r"उठा\s+(?:लिया|ले\s+गए|ले\s+गया|ले\s+गई)", "hi", False),
    (r"घर\s+(?:में|मा|मे|मों)\s+(?:\S+\s+){0,3}घुस\S*", "hi", False),
    (r"(?:चाकू|पिस्तौल|बंदूक|तमंचा|कट्टा)\s+(?:दिखा\S*|से|लेकर|ले\s+कर|लगा\S*|निकाल\S*)", "hi", False),
    (r"खून\s+(?:बह|निकल)\S*", "hi", False),
    # Awadhi / Bundeli (best-effort, pending native-speaker review)
    (r"(?:मार|पीट)त\s+(?:बा|बाटै|बाटे|बाटैं|बाटी|बाटीं|हवै|हवे|अहै|आय)", "hi", False),
    (r"(?:मार|पीट)\s+(?:रओ|रई|रये|रयो|रहो)", "hi", False),
    (r"मार\s+(?:डार|डर|दिह|देह)\S*", "hi", False),
    (r"जरा\s+(?:देब|दीन|दिहिस|देहै|देहें|दिहैं)", "hi", False),
    (r"(?:हमका|मोय|मोखों|मोहे|मोये)\s+(?:\S+\s+){0,2}(?:मारिस|मारेस|पीटिस|पीटेस|मारो|पीटो)", "hi", False),
    (r"बचावा", "hi", False),
    (r"बचा\s+(?:लेओ|लियो|लेव)", "hi", False),
    (r"(?:हमका|मोय|मोखों)\s+बचा\S*", "hi", False),
    (r"उठा\s+(?:लिहिन|लइगे|लई\s+गे|ले\s+गे|ले\s+गइन|ले\s+गयो)", "hi", False),
    (r"(?:maar|peet|pit)at\s+(?:ba|bate|baate|bati|hawai|hai|hain)", "hi", False),
    (r"maar\s+(?:dalab|dalihe|dalihen|daarab|dari|dihe|dihen)", "hi", False),
    (r"(?:maar|peet|pit)\s+(?:rao|rai|raye|rayo|raho)", "hi", False),
]

_POSSIBLE_WEAK = [
    # English
    (r"danger(?:ous)?", "en", False),
    (r"threat(?:s|ened|ening|en)?", "en", False),
    (r"kidnap\S*", "en", False),
    (r"abduct(?:ed|ion)?", "en", False),
    (r"murder(?:ed)?", "en", False),
    (r"kill(?:ed|ing)?", "en", False),
    (r"attack(?:ed|s)?", "en", False),
    (r"assault(?:ed)?", "en", False),
    (r"rape(?:d|s)?", "en", False),
    (r"molest\S*", "en", False),
    (r"harass(?:ed|ment|ing)?", "en", False),
    (r"(?:domestic\s+)?violence", "en", False),
    (r"abus(?:e|ed|ive|ing)", "en", False),
    (r"beaten", "en", False),
    (r"(?:beat|hit|slapped|kicked)\s+(?:me|her|him)", "en", False),
    (r"stalk\S*", "en", False),
    (r"acid", "en", False),
    (r"injur(?:ed|y)", "en", False),
    (r"emergency", "en", False),
    (r"unsafe", "en", False),
    (r"scared", "en", False),
    (r"afraid", "en", False),
    (r"hostage", "en", False),
    (r"trafficking", "en", False),
    (r"accident", "en", False),
    # Hinglish
    (r"khatra", "hi", False),
    (r"dhamki(?:\s+de\s+(?:raha|rahe|rahi))?", "hi", False),
    (r"dhamka\S*", "hi", False),
    (r"hatya", "hi", False),
    (r"khoon", "hi", False),
    (r"mar\s*peet", "hi", False),
    (r"balatkar", "hi", False),
    (r"hinsa", "hi", False),
    (r"utpidan", "hi", False),
    (r"chher\s*chhad", "hi", False),
    (r"jabardasti|zabardasti", "hi", False),
    (r"maara|mara\s+tha|peeta\s+tha|pita\s+tha", "hi", False),
    (r"dar\s+(?:lag|lagta|lagti)\S*", "hi", False),
    (r"tang\s+kar\S*", "hi", False),
    # Devanagari
    (r"खतरा", "hi", False),
    (r"धमकी", "hi", False),
    (r"हत्या", "hi", False),
    (r"बलात्कार", "hi", False),
    (r"हिंसा", "hi", False),
    (r"मारपीट", "hi", False),
    (r"उत्पीड़न", "hi", False),
    (r"जबरदस्ती|ज़बरदस्ती", "hi", False),
    (r"छेड़छाड़", "hi", False),
    (r"अपहरण", "hi", False),
    (r"डर", "hi", False),
]


def _prepare(entries):
    return [(_compile(src), lang, immune) for src, lang, immune in entries]


_TABLES = {
    "self_harm_strong": _prepare(_SELF_HARM_STRONG),
    "self_harm_weak": _prepare(_SELF_HARM_WEAK),
    "emergency_strong": _prepare(_EMERGENCY_STRONG),
    "possible_weak": _prepare(_POSSIBLE_WEAK),
}

# A negator directly before (up to 2 tokens) or directly after (1 token) a
# match cancels it. The window is deliberately tiny: a wide window would let
# "police nahi sun rahi, pati maar raha hai" wrongly cancel a real emergency.
_NEGATORS = {
    "not", "no", "never", "dont", "don", "didn", "isn", "aren", "wasn",
    "cannot", "wont", "won", "nahi", "nhi", "nahin", "nai", "mat", "नहीं", "नही",
}


def _is_negated(norm: str, start: int, end: int) -> bool:
    tokens = norm.split()
    first = len(norm[:start].split())
    last = len(norm[:end].split())
    before = tokens[max(0, first - 2):first]
    after = tokens[last:last + 1]
    return any(tok in _NEGATORS for tok in before + after)


def _scan(norm: str, table):
    """Return (live_hits, negated_hits); each hit is (pattern_text, language)."""
    live, negated = [], []
    for pattern, lang, immune in table:
        for m in pattern.finditer(norm):
            hit = (m.group(0), lang)
            if not immune and _is_negated(norm, m.start(), m.end()):
                negated.append(hit)
            else:
                live.append(hit)
    return live, negated


def assess_risk(text: str) -> dict:
    """Classify a user message.

    Returns {"level", "matched", "language_hint"}:
      level          one of none / possible / emergency / self_harm
      matched        the matched phrases (for logs and tests; never shown)
      language_hint  "hindi" if the winning phrases were Hindi/Hinglish,
                     "english" if English, None if nothing matched
    """
    norm = normalize(text)
    if not norm:
        return {"level": NONE, "matched": [], "language_hint": None}

    sh_live, sh_neg = _scan(norm, _TABLES["self_harm_strong"])
    em_live, em_neg = _scan(norm, _TABLES["emergency_strong"])
    shw_live, _ = _scan(norm, _TABLES["self_harm_weak"])
    pw_live, _ = _scan(norm, _TABLES["possible_weak"])

    if sh_live:
        level, hits = SELF_HARM, sh_live
    elif em_live:
        level, hits = EMERGENCY, em_live
    elif sh_neg or em_neg or shw_live or pw_live:
        # Negated strong phrases are kept at `possible`, not dropped to `none`.
        level, hits = POSSIBLE, sh_neg + em_neg + shw_live + pw_live
    else:
        return {"level": NONE, "matched": [], "language_hint": None}

    langs = {lang for _, lang in hits}
    hint = "hindi" if "hi" in langs else "english"
    return {"level": level, "matched": [h[0] for h in hits], "language_hint": hint}


# ---------------------------------------------------------------------------
# Static messages.  Only numbers listed in docs/verified-helplines.md.
# Native-speaker review of the Hindi text is still pending.
# ---------------------------------------------------------------------------
EMERGENCY_BLOCK = {
    "english": (
        "EMERGENCY HELPLINES: "
        "Police, fire and ambulance 112. "
        "UP Women Power Line 1090. "
        "Women Helpline 181. "
        "Child Helpline 1098."
    ),
    "hindi": (
        "आपातकालीन हेल्पलाइन: "
        "पुलिस, फायर और एम्बुलेंस के लिए 112। "
        "यूपी वुमन पावर लाइन 1090। "
        "महिला हेल्पलाइन 181। "
        "चाइल्डलाइन 1098।"
    ),
}

POSSIBLE_FOOTER = {
    "english": "If you or someone else is in danger right now, please call 112.",
    "hindi": "अगर आप या कोई और अभी खतरे में है, तो कृपया 112 पर कॉल करें।",
}

SELF_HARM_MESSAGE = {
    "english": (
        "I'm really sorry you are going through this, and I'm glad you reached out. "
        "You do not have to carry this alone. Please talk to someone right now: "
        "call Tele-MANAS on 14416 (free, 24x7, in many languages). "
        "If you are in immediate danger or have already hurt yourself, call 112 "
        "or go to the nearest hospital. "
        "If you can, tell someone you trust where you are and ask them to stay with you. "
        "When you feel ready, I can also help with any legal problem that is weighing on you."
    ),
    "hindi": (
        "आप जिस दौर से गुज़र रहे हैं, उसके लिए मुझे बहुत दुख है, और अच्छा है कि आपने बात की। "
        "आपको यह अकेले नहीं सहना है। कृपया अभी किसी से बात करें: "
        "Tele-MANAS पर 14416 पर कॉल करें (मुफ़्त, 24x7, कई भाषाओं में)। "
        "अगर आप अभी खतरे में हैं या खुद को चोट पहुँचा चुके हैं, तो 112 पर कॉल करें "
        "या नज़दीकी अस्पताल जाएँ। "
        "हो सके तो किसी भरोसेमंद व्यक्ति को बताएँ कि आप कहाँ हैं और उनसे अपने पास रुकने को कहें। "
        "जब आप तैयार हों, तो मैं आपकी किसी भी कानूनी परेशानी में भी मदद कर सकता हूँ।"
    ),
}


def _lang(language: str) -> str:
    return "hindi" if language == "hindi" else "english"


def emergency_block(language: str = "english") -> str:
    return EMERGENCY_BLOCK[_lang(language)]


def possible_footer(language: str = "english") -> str:
    return POSSIBLE_FOOTER[_lang(language)]


def self_harm_message(language: str = "english") -> str:
    return SELF_HARM_MESSAGE[_lang(language)]
