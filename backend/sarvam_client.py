import re
import httpx
from openai import OpenAI
from backend.config import (
    SARVAM_API_KEY, SARVAM_BASE_URL, SARVAM_MODEL,
    SARVAM_TRANSLATE_URL, GROQ_API_KEY, GROQ_BASE_URL,
    GROQ_MODEL, SYSTEM_PROMPT, MAX_TOKENS, TEMPERATURE,
    DOMAIN_HELPLINES
)
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o-mini"

EMERGENCY_HELPLINES = (
    "EMERGENCY HELPLINES: "
    "UP Police Emergency 112. "
    "UP Mahila Power Line 1090. "
    "One Stop Centre Sakhi 181. "
    "Child Helpline 1098. "
    "SC ST Atrocities Helpline 14566. "
    "UP CM Helpline 1076."
)


def clean_response(text: str) -> str:
    """Remove think tags, markdown, and special characters for clean ASR/TTS output."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)
    text = re.sub(r'^\s*[•\-\*\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*(\d+)\.\s+', r'\1. ', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'^[-_\*]{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'`+([^`]*)`+', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def build_user_message(query: str, context: str, language: str,
                       is_emergency: bool, domain: str) -> str:
    """Build a detailed, domain-aware user message for better LLM responses."""

    lang_instruction = (
        "Hindi mein jawab do — simple aur seedha, poori tarah Devanagari script mein. "
        "Aam nagrik samajh sake aisi bhasha use karo."
        if language == "hindi"
        else "Reply in clear simple English that any citizen can understand."
    )

    emergency_note = (
        "CRITICAL EMERGENCY: Give relevant helplines in the VERY FIRST SENTENCE before any other information."
        if is_emergency else ""
    )

    helpline = DOMAIN_HELPLINES.get(domain, DOMAIN_HELPLINES["general"])

    return f"""User's Question: {query}

Relevant Legal Knowledge from Knowledge Base:
{context}

Domain: {domain}
Relevant Helpline: {helpline}

Your Task:
{emergency_note}
1. Answer this specific question directly in the first sentence
2. Use the legal knowledge above to give UP-specific accurate guidance
3. Include actual law names and section numbers where relevant
4. Give clear numbered steps if a process or procedure is involved
5. End the response by mentioning: {helpline}
6. {lang_instruction}
7. Write only in natural spoken sentences — no markdown, no asterisks, no bullet symbols, no special characters
8. Keep response focused and practical — the user needs to take action today
"""


def _get_client(base_url: str, api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def generate_response(query: str, context: str, language: str = "english",
                      is_emergency: bool = False, conversation_history: list = None,
                      domain: str = "general") -> str:
    """Generate response using Sarvam-M → Groq → OpenAI fallback chain."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history[-6:])

    user_msg = build_user_message(query, context, language, is_emergency, domain)
    messages.append({"role": "user", "content": user_msg})

    raw_reply = None

    # ── Try Sarvam-M ──
    if SARVAM_API_KEY:
        try:
            r = _get_client(SARVAM_BASE_URL, SARVAM_API_KEY).chat.completions.create(
                model=SARVAM_MODEL, messages=messages,
                max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
            raw_reply = r.choices[0].message.content
            print("✅ Sarvam-M responded")
        except Exception as e:
            print(f"⚠️  Sarvam-M failed: {e}")

    # ── Try Groq ──
    if raw_reply is None and GROQ_API_KEY:
        try:
            r = _get_client(GROQ_BASE_URL, GROQ_API_KEY).chat.completions.create(
                model=GROQ_MODEL, messages=messages,
                max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
            raw_reply = r.choices[0].message.content
            print("✅ Groq responded")
        except Exception as e:
            print(f"⚠️  Groq failed: {e}")

    # ── Try OpenAI ──
    if raw_reply is None and OPENAI_API_KEY:
        try:
            r = OpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
                model=OPENAI_MODEL, messages=messages,
                max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
            raw_reply = r.choices[0].message.content
            print("✅ OpenAI responded")
        except Exception as e:
            print(f"⚠️  OpenAI failed: {e}")

    if raw_reply is None:
        return EMERGENCY_HELPLINES if is_emergency else \
               "Sorry, unable to process right now. Please call 112 for emergency or 1076 for UP CM Helpline."

    cleaned = clean_response(raw_reply)

    if is_emergency:
        cleaned = EMERGENCY_HELPLINES + "\n\n" + cleaned

    return cleaned


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text using Sarvam Translate API."""
    if not SARVAM_API_KEY:
        return text

    lang_map = {"hindi": "hi-IN", "english": "en-IN"}
    source = lang_map.get(source_lang, "en-IN")
    target = lang_map.get(target_lang, "hi-IN")

    if source == target:
        return text

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                SARVAM_TRANSLATE_URL,
                headers={"api-subscription-key": SARVAM_API_KEY,
                         "Content-Type": "application/json"},
                json={"input": text, "source_language_code": source,
                      "target_language_code": target, "speaker_gender": "Male",
                      "mode": "formal", "enable_preprocessing": True}
            )
            if r.status_code == 200:
                return r.json().get("translated_text", text)
            print(f"⚠️  Translate API: {r.status_code}")
    except Exception as e:
        print(f"⚠️  Translation error: {e}")

    return text
