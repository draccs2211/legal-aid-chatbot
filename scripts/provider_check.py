"""Check EACH configured LLM provider on its own: no fallback, no retry.

    python scripts/provider_check.py
    python scripts/provider_check.py --only groq openai

The smoke test only ever reaches the first provider that works, so a broken
fallback can go unnoticed (that is how Groq and OpenAI were never exercised).
This sends one tiny fixed prompt to every provider that has a key, with the
same model name and request parameters the app uses (via
sarvam_client.call_provider_once), and prints per provider:

    status (ok / error / no key), HTTP status, error class, latency,
    whether text came back, and at most the first 80 characters of the answer.

It never prints a key, a header, or an exception message (provider errors can
echo the request). Exit code: 0 if every provider that has a key answered,
1 if any failed, 2 if no provider has a key. Costs one small request per provider.
"""
import argparse
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import sarvam_client  # noqa: E402  (needs backend/ on the path)

PROMPT = [{"role": "user", "content": "Reply with one short sentence: what is the capital of India?"}]
PREVIEW_CHARS = 80


def preview(text: str) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= PREVIEW_CHARS else one_line[:PREVIEW_CHARS - 3] + "..."


def check(provider, timeout, clock=time.perf_counter):
    """Returns a dict safe to print: never the key, never an exception message."""
    result = {"provider": provider.name, "model": provider.model, "status": None, "http_status": None,
              "error": None, "latency_ms": None, "text_returned": False, "preview": ""}
    if not provider.api_key:
        result["status"] = "no key"
        return result
    started = clock()
    try:
        text = sarvam_client.call_provider_once(provider, PROMPT, timeout=timeout)
    except Exception as exc:  # classified only; the message is never shown
        failure = sarvam_client._classify(exc)
        result.update(status="error", http_status=failure.status, error=failure.error)
    else:
        result.update(status="ok", text_returned=bool(text), preview=preview(text))
    result["latency_ms"] = round((clock() - started) * 1000)
    return result


def format_row(r) -> str:
    parts = [f"{r['provider']:<7}", f"{r['model']:<28}", f"{r['status']:<7}"]
    if r["status"] != "no key":
        parts += [f"http={r['http_status'] or '-':<4}", f"error={r['error'] or '-':<22}",
                  f"{r['latency_ms']:>6} ms", f"text={'yes' if r['text_returned'] else 'no'}"]
    line = "  ".join(parts)
    if r["preview"]:
        line += f"\n         answer: {r['preview']}"
    return line


def exit_code(results) -> int:
    tried = [r for r in results if r["status"] != "no key"]
    if not tried:
        return 2
    return 0 if all(r["status"] == "ok" for r in tried) else 1


def main(argv=None):
    providers = sarvam_client._providers()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="+", choices=[p.name for p in providers], help="check only these providers")
    ap.add_argument("--timeout", type=float, default=sarvam_client.LLM_TIMEOUT_SECONDS,
                    help="seconds per provider (default: LLM_TIMEOUT_SECONDS)")
    args = ap.parse_args(argv)
    if args.only:
        providers = [p for p in providers if p.name in args.only]
    results = [check(p, args.timeout) for p in providers]
    for r in results:
        print(format_row(r))
    code = exit_code(results)
    print({0: "\nAll providers with a key answered.", 1: "\nAt least one provider FAILED.",
           2: "\nNo provider has a key: nothing was checked."}[code])
    return code


if __name__ == "__main__":
    sys.exit(main())
