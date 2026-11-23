import asyncio
import logging
import os
import re
import time
from typing import NamedTuple, Optional

import httpx
import openai
from config import (
    SARVAM_API_KEY, SARVAM_BASE_URL, SARVAM_MODEL,
    SARVAM_TRANSLATE_URL, GROQ_API_KEY, GROQ_BASE_URL,
    GROQ_MODEL, OPENAI_MODEL, SYSTEM_PROMPT, MAX_TOKENS, TEMPERATURE,
    DOMAIN_HELPLINES, LLM_TIMEOUT_SECONDS, LLM_TOTAL_BUDGET_SECONDS,
    LLM_MAX_RETRIES,
)

from safety import emergency_block, unavailable_message

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# One line per attempt: provider, model, attempt, outcome, HTTP status, error
# class and latency. NEVER user text, passages, keys or str(exception): provider
# error messages can echo parts of the request.
log = logging.getLogger("nyaymitra.llm")

# Pause before a retry when the server does not send Retry-After, and the most
# we will wait even if it asks for longer (the chain budget matters more).
RETRY_PAUSE_SECONDS = 1.0
RETRY_AFTER_CAP_SECONDS = 5.0
# Do not start an attempt with less than this left in the budget.
MIN_ATTEMPT_SECONDS = 1.0

# Injected so tests can control time without sleeping.
_clock = time.monotonic
_sleep = time.sleep

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


def _get_client(base_url: Optional[str], api_key: str, timeout: float = LLM_TIMEOUT_SECONDS) -> openai.AsyncOpenAI:
    # max_retries=0: the SDK would otherwise retry twice on its own, including
    # cases our policy does not retry. Its default timeout is 10 minutes.
    # `timeout` here is httpx's per-wait limit: an inner safety net only; the
    # hard limit is asyncio.wait_for in call_provider_once.
    return openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)


class Provider(NamedTuple):
    name: str
    model: str
    api_key: str
    base_url: Optional[str]   # None = the SDK's default (OpenAI)
    params: dict              # provider-specific request parameters


def _providers() -> list:
    """The chain in order. Read at call time so a test can patch one setting."""
    groq_params = {"max_completion_tokens": MAX_TOKENS, "temperature": TEMPERATURE}
    if GROQ_MODEL.startswith("openai/gpt-oss"):
        # Reasoning model: keep the trace out of the reply and keep it short.
        groq_params["reasoning_effort"] = "low"
        groq_params["extra_body"] = {"include_reasoning": False}

    openai_params = {"max_completion_tokens": MAX_TOKENS}
    if OPENAI_MODEL.startswith("gpt-4o"):
        openai_params["temperature"] = TEMPERATURE   # older model, no reasoning setting
    else:
        # Reasoning model (gpt-6-luna). Temperature left out: not documented for it.
        openai_params["reasoning_effort"] = "none"

    return [
        Provider("sarvam", SARVAM_MODEL, SARVAM_API_KEY, SARVAM_BASE_URL,
                 {"max_tokens": MAX_TOKENS, "temperature": TEMPERATURE}),
        Provider("groq", GROQ_MODEL, GROQ_API_KEY, GROQ_BASE_URL, groq_params),
        Provider("openai", OPENAI_MODEL, OPENAI_API_KEY, None, openai_params),
    ]


class EmptyReply(Exception):
    """The provider answered, but nothing was left after removing reasoning text."""


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think>.*\Z", re.DOTALL | re.IGNORECASE)
_THINK_CLOSE = re.compile(r"\A.*</think>", re.DOTALL | re.IGNORECASE)


def extract_answer(response) -> str:
    """The answer text only. Separate reasoning fields (Sarvam `reasoning_content`,
    Groq `reasoning`) are ignored because only `content` is read. Inline reasoning
    is removed: whole <think>...</think> blocks, text up to a stray </think>, and
    everything after an unclosed <think> (a reply cut off mid-reasoning)."""
    content = response.choices[0].message.content or ""
    content = _THINK_BLOCK.sub("", content)
    content = _THINK_CLOSE.sub("", content)
    content = _THINK_OPEN.sub("", content)
    content = content.strip()
    if not content:
        raise EmptyReply()
    return content


class _Failure(NamedTuple):
    error: str                  # error class name, safe to log
    status: Optional[int]       # HTTP status if there was one
    retryable: bool
    retry_after: Optional[float]


def _classify(exc: Exception) -> _Failure:
    """Retry only what a retry can fix: timeouts, 5xx and 429.
    Never 400/401/403/404/422 (bad request, bad key, bad model name), never a
    connection error, never an empty reply: those go straight to the next provider."""
    # APITimeoutError: httpx's per-wait limit. asyncio.TimeoutError: our hard
    # per-call limit (on Python 3.10 it is NOT the built-in TimeoutError).
    if isinstance(exc, (openai.APITimeoutError, asyncio.TimeoutError, TimeoutError)):
        return _Failure("timeout", None, True, None)
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        retryable = status == 429 or status >= 500
        return _Failure(type(exc).__name__, status, retryable, _retry_after(exc) if retryable else None)
    if isinstance(exc, EmptyReply):
        return _Failure("empty_reply", None, False, None)
    return _Failure(type(exc).__name__, None, False, None)


def _retry_after(exc) -> Optional[float]:
    try:
        value = float(exc.response.headers.get("retry-after"))
    except (AttributeError, TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _log_attempt(provider, attempt, outcome, started, failure=None):
    log.info(
        "llm_attempt provider=%s model=%s attempt=%d outcome=%s status=%s error=%s latency_ms=%d",
        provider.name, provider.model, attempt, outcome,
        failure.status if failure else None, failure.error if failure else None,
        round((_clock() - started) * 1000),
    )


class Reply(NamedTuple):
    text: str
    provider: str   # "sarvam" | "groq" | "openai" | "none" (static fallback message)


def call_provider_once(provider: Provider, messages: list, timeout: float) -> str:
    """One request to one provider, exactly as the chain sends it. Raises on any
    failure (including EmptyReply); no retry, no fallback. Also used by
    scripts/provider_check.py so the check tests the production request.

    `timeout` is a HARD wall-clock limit for the whole call (B0b). httpx's own
    timeout restarts whenever a few bytes arrive, so a provider trickling its
    reply would never trip it. asyncio.wait_for cancels the request and closes
    the connection when the limit is reached. Must be called from a thread
    without a running event loop (/chat is a plain `def`, see B0a)."""

    async def _create():
        async with _get_client(provider.base_url, provider.api_key, timeout=timeout) as client:
            return await client.chat.completions.create(model=provider.model, messages=messages, **provider.params)

    async def _with_limit():
        return await asyncio.wait_for(_create(), timeout=timeout)

    return extract_answer(asyncio.run(_with_limit()))


def _run_chain(messages) -> tuple:
    """Try each provider in order within one time budget.
    Returns (raw_text, provider_name) or (None, "none")."""
    deadline = _clock() + LLM_TOTAL_BUDGET_SECONDS
    for provider in _providers():
        if not provider.api_key:
            log.info("llm_skip provider=%s reason=no_key", provider.name)
            continue
        for attempt in range(1, LLM_MAX_RETRIES + 2):
            remaining = deadline - _clock()
            if remaining < MIN_ATTEMPT_SECONDS:
                log.warning("llm_budget_exhausted provider=%s attempt=%d", provider.name, attempt)
                return None, "none"
            started = _clock()
            try:
                text = call_provider_once(provider, messages, timeout=min(LLM_TIMEOUT_SECONDS, remaining))
            except Exception as exc:  # classified; never logged as text
                failure = _classify(exc)
                _log_attempt(provider, attempt, "error", started, failure)
                if not failure.retryable or attempt > LLM_MAX_RETRIES:
                    break
                pause = min(failure.retry_after if failure.retry_after is not None else RETRY_PAUSE_SECONDS,
                            RETRY_AFTER_CAP_SECONDS)
                if deadline - _clock() - pause < MIN_ATTEMPT_SECONDS:
                    break   # no time for a retry: try the next provider instead
                _sleep(pause)
                continue
            _log_attempt(provider, attempt, "ok", started)
            return text, provider.name
    log.warning("llm_chain_failed")
    return None, "none"


def generate_reply(query: str, context: str, language: str = "english",
                   is_emergency: bool = False, conversation_history: list = None,
                   domain: str = "general") -> Reply:
    """Answer with the Sarvam -> Groq -> OpenAI chain; also say who answered."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history[-6:])

    user_msg = build_user_message(query, context, language, is_emergency, domain)
    messages.append({"role": "user", "content": user_msg})

    raw_reply, provider = _run_chain(messages)

    if raw_reply is None:
        text = emergency_block(language) if is_emergency else unavailable_message(language)
        return Reply(text, "none")

    cleaned = clean_response(raw_reply)

    if is_emergency:
        cleaned = emergency_block(language) + "\n\n" + cleaned

    return Reply(cleaned, provider)


def generate_response(*args, **kwargs) -> str:
    """Text only; kept for callers that do not need the provider name."""
    return generate_reply(*args, **kwargs).text


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
        print(f"⚠️  Translation error: {type(e).__name__}")   # class only (B1)

    return text
