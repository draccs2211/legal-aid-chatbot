# Prompts to paste into Claude Code, in order

Start every session in plan mode (Shift+Tab until it says plan) for anything that is not a tiny fix.
After each task: check `git diff`, run the tests yourself once, then `git push`.

## 0. Orientation (read-only)
Read CLAUDE.md and docs/PROJECT_STATE.md. Run `git status -sb`, `git log --oneline -5` and the full test suite. Do not edit
anything. Tell me in simple English: what state the repo is in, whether the tests match the numbers in CLAUDE.md, and anything
in the docs that contradicts the code.

## 1. Fix the deprecated Sarvam model and harden the provider layer
Read backend/sarvam_client.py, backend/config.py and the tests that touch them. Then check Sarvam's CURRENT docs
(docs.sarvam.ai models page and chat completions) for the replacement of sarvam-30b and how its reasoning output is returned.
Plan first, then: make SARVAM_MODEL, GROQ_MODEL and OPENAI_MODEL environment variables with validated defaults, update .env.example
and the env-example test, log which provider answered (no secrets, no user text), add bounded timeouts, one retry for retryable
errors only, and tests with fake clients for: success, 400 deprecated model, 401, 429, timeout, empty response, fallback chain, all down.
Do not call real APIs in tests. Then, with my keys in .env (never print them), run the smoke test and report which provider answered.

## 2. Make tests unable to use real keys
Add tests/conftest.py that blanks SARVAM_API_KEY, GROQ_API_KEY and OPENAI_API_KEY and blocks real network access for every test.
Prove it: temporarily put a fake key in the environment and show a test cannot reach the network. Keep all existing tests green.

## 3. Security hardening (one commit per item)
From the backlog item 3: stop returning str(e); add a request size limit for /stt and /tts; restrict /stats; make CORS configurable
via env; replace the shared "default" session and guessable ids with server-generated ids and eviction; add basic rate limiting on
/chat, /stt, /tts. Each item needs tests, including a test that no error response contains a stack trace or key-like string.

## 4. Grounding gate and sources
Design first (plan mode): return the retrieved sources in the API response; change the system prompt so the model must only use the
passages and must say it cannot answer when they do not cover the question; decide a safe abstain rule (distance thresholds alone
do not work, see PROJECT_STATE). Then build a small labelled answer-quality set from the existing retrieval set (answerable and
unanswerable), a runner that works with fake providers in CI and real providers on demand, and report faithfulness and abstain accuracy
separately. Do not claim legal correctness.

## 5. Safe ingestion
Make scripts/load_chromadb.py idempotent with content hashes: report added, updated, unchanged and removed chunks, delete chunks whose source
disappeared, never touch another model's collection. Add tests with a temporary store. Resolve the stray women_safety file by asking me first.

## 6. Switching to the multilingual embedder in production code
Only after the staging deploy works: follow docs/render-staging-plan.md. Do not merge or push to main.

## Habits
- Say "plan first, do not edit yet" when you want to review the approach.
- Ask it to explain every change in simple English and what could break.
- /clear between unrelated tasks; CLAUDE.md is reloaded automatically.
- If it asks to read .env or push to main, answer no.
