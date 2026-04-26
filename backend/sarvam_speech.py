# ── sarvam_speech.py — Final version ──
import httpx
import os
import re
import asyncio

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

HELPLINE_NUMBERS_HI = {
    '112':   'एक सौ बारह',
    '1090':  'एक शून्य नौ शून्य',
    '181':   'एक सौ इक्यासी',
    '1098':  'एक शून्य नौ आठ',
    '14566': 'एक चार पांच छह छह',
    '1076':  'एक शून्य सात छह',
    '100':   'एक सौ',
    '108':   'एक सौ आठ',
    '1930':  'एक नौ तीन शून्य',
    '1915':  'एक नौ एक पांच',
    '15100': 'एक पांच एक शून्य शून्य',
    '1800':  'एक आठ शून्य शून्य',
    '0522':  'शून्य पांच दो दो',
}

DIGIT_WORDS_HI = {
    '0': 'शून्य', '1': 'एक', '2': 'दो', '3': 'तीन', '4': 'चार',
    '5': 'पांच', '6': 'छह', '7': 'सात', '8': 'आठ', '9': 'नौ',
}

EN_DIGITS = {
    '0':'zero','1':'one','2':'two','3':'three','4':'four',
    '5':'five','6':'six','7':'seven','8':'eight','9':'nine'
}


def convert_numbers_for_tts(text: str, language: str) -> str:
    """Convert numbers to speakable words for TTS."""
    if language == "hi-IN":
        # Known helplines — longest first to avoid partial match
        for num in sorted(HELPLINE_NUMBERS_HI.keys(), key=len, reverse=True):
            text = re.sub(r'(?<!\d)' + re.escape(num) + r'(?!\d)',
                          HELPLINE_NUMBERS_HI[num], text)
        # Remaining numbers — digit by digit
        def to_hindi(m):
            return ' '.join(DIGIT_WORDS_HI.get(d, d) for d in m.group(0))
        text = re.sub(r'\b\d+\b', to_hindi, text)
    else:
        # English — helplines digit by digit
        def to_english(m):
            num = m.group(0)
            if len(num) <= 5:
                return ' '.join(EN_DIGITS.get(d, d) for d in num)
            return num
        text = re.sub(r'\b\d{3,5}\b', to_english, text)
    return text


def detect_text_language(text: str) -> str:
    """Detect if text is Hindi or English based on Devanagari chars."""
    devanagari = len(re.findall(r'[\u0900-\u097F]', text))
    total = len(text.strip())
    # If >20% Devanagari chars → Hindi
    return "hi-IN" if total > 0 and (devanagari / total) > 0.20 else "en-IN"


def split_text_for_tts(text: str, max_chars: int = 350) -> list:
    """Split text into TTS-friendly chunks at sentence boundaries."""
    text = re.sub(r'[*#_`•\[\]]', '', text).strip()
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r' {2,}', ' ', text)

    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r'(?<=[।.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            if len(sentence) > max_chars:
                parts = re.split(r'(?<=[,;])\s+', sentence)
                part_chunk = ""
                for part in parts:
                    if len(part_chunk) + len(part) + 1 <= max_chars:
                        part_chunk = (part_chunk + " " + part).strip()
                    else:
                        if part_chunk:
                            chunks.append(part_chunk)
                        part_chunk = part[:max_chars]
                if part_chunk:
                    chunks.append(part_chunk)
            else:
                current = sentence

    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


async def speech_to_text(audio_bytes: bytes, language: str = "unknown") -> dict:
    """Convert audio to text using Sarvam Saarika v2.5."""
    if not SARVAM_API_KEY:
        return {"error": "Sarvam API key not configured", "transcript": ""}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                SARVAM_STT_URL,
                headers={"api-subscription-key": SARVAM_API_KEY},
                files={"file": ("audio.webm", audio_bytes, "audio/webm")},
                data={"model": "saarika:v2.5", "language_code": language, "with_timestamps": "false"}
            )
            if response.status_code == 200:
                data = response.json()
                return {"transcript": data.get("transcript", ""), "language_code": data.get("language_code", "hi-IN")}
            print(f"STT Error: {response.status_code}")
            return {"error": f"STT failed: {response.status_code}", "transcript": ""}
    except Exception as e:
        return {"error": str(e), "transcript": ""}


async def tts_single_chunk(text: str, language: str, speaker: str) -> str | None:
    """Fetch single TTS chunk."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                SARVAM_TTS_URL,
                headers={"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"},
                json={"inputs": [text], "target_language_code": language,
                      "speaker": speaker, "model": "bulbul:v3",
                      "pace": 1.0, "enable_preprocessing": True}
            )
            if response.status_code == 200:
                audios = response.json().get("audios", [])
                return audios[0] if audios else None
            print(f"TTS chunk error: {response.status_code} — {response.text}")
            return None
    except Exception as e:
        print(f"TTS chunk exception: {e}")
        return None


async def text_to_speech(text: str, language: str = "auto") -> dict:
    """
    Convert text to speech with parallel chunk fetching.
    language: "auto" = detect from text content (fixes wrong language issue)
    """
    if not SARVAM_API_KEY:
        return {"error": "Sarvam API key not configured"}

    # AUTO-DETECT language from actual text content — fixes the core issue
    # Frontend might send wrong language, so we detect from text itself
    if language == "auto" or language not in ("hi-IN", "en-IN"):
        language = detect_text_language(text)
        print(f"TTS auto-detected language: {language}")

    speaker = "shreya" if language == "hi-IN" else "shreya"

    # Convert numbers ALWAYS
    text = convert_numbers_for_tts(text, language)

    chunks = split_text_for_tts(text, max_chars=350)
    print(f"TTS: {len(chunks)} chunks, lang={language}, parallel fetch")

    # Fetch ALL chunks concurrently
    tasks = [tts_single_chunk(chunk, language, speaker) for chunk in chunks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    audio_chunks = [r for r in results if isinstance(r, str) and r]

    if not audio_chunks:
        return {"error": "All TTS chunks failed"}

    return {
        "audio_chunks": audio_chunks,
        "chunk_count": len(audio_chunks),
        "content_type": "audio/wav",
        "detected_language": language
    }