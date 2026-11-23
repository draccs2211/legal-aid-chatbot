# Project state (2026-11-23)

Branch `audit/phase1`, last pushed commit `03feed2`. Run `git status` and `git log --oneline -5` to see anything newer.
CI (GitHub Actions `tests` workflow) is GREEN: last 5 runs succeeded, latest 2026-11-22 (push + pull_request).
An open pull request from `audit/phase1` exists. Do NOT merge it (merging deploys to production).
Test suite on the owner's machine (2026-11-23): 760 passed, 11 xfailed.

## Fixed and verified (tests pass on the owner's Windows machine)
- Domain routing matched word fragments ("music" -> RTI). Now whole words.
- Cyber filter never matched (detector `cyber`, data `cyber_law`). Mapped in config.
- `main.py` did not pass the domain, so every user got the "general" helpline. Fixed.
- Hinglish marker list had a missing comma. Fixed.
- `scripts/test_rag.py` had a bad import path and format string. Fixed.
- Emergency detection rewritten as four levels (none, possible, emergency, self_harm) in `backend/safety.py`;
  self-harm gets a static message with Tele-MANAS 14416 and 112, no LLM. Verified helplines: 112, 1090, 181, 1098, 14416.
- `.env` had `CHROMADB_PATH=./chromadb_storecd backend` which silently created an empty DB (data was intact).
  Path now resolves against the repo root; `scripts/doctor.py` diagnoses it; `.env.example` added.
- Provider-down fallback message is now language-aware (found by the smoke test).
- `.python-version` pins 3.10 (Render's default for new services is 3.14).
- Tests could load real keys: `config.py` runs `load_dotenv()` on import. `tests/conftest.py` now blanks all
  three keys before any backend import (dotenv never overrides an existing variable) and blocks every
  non-loopback socket and DNS lookup. Proven by `tests/test_test_guards.py`.
- 1076 (UP CM grievance helpline) verified against two UP government pages; not used in emergency text.
- Provider layer (A1). Sarvam path confirmed by the owner's real-key smoke run (2026-11-23, see below);
  Groq and OpenAI request parameters NEVER exercised against the real APIs (Sarvam answered every time):
  defaults `sarvam-105b-conversations`, `openai/gpt-oss-120b` (Groq), `gpt-6-luna` (OpenAI), all env-configurable;
  30 s per attempt, 60 s total budget (frontend aborts /chat at 120 s), 1 retry on timeout/5xx/429 only;
  SDK's own retries off (it used to retry twice with a 10-minute timeout); reasoning text stripped;
  one log line per attempt without user text; `/chat` returns `provider`; smoke test prints it.

## Retrieval measurements (71 answerable + 12 unanswerable labelled queries; dev set, optimistic)
| Pipeline | Hit@5 | Hit@10 | MRR |
|---|---|---|---|
| Original (English MiniLM, keyword router) | 0.789 | 0.817 | 0.637 |
| e5-small multilingual, no filter (production code path, verified) | 0.901 | 0.958 | 0.757 |
| e5-small, keyword hard filter | 0.859 | 0.901 | 0.749 |
| e5-small, perfect routing (ceiling) | 0.958 | 0.986 | 0.845 |
- Original embedder is near chance on Devanagari Hindi (3/55); e5-small gets 48/55 on the same questions.
- Keyword router: 47/71 correct, 0/55 on Hindi. With e5 it hurts, so use `ROUTING_MODE=none`.
- Soft routing with small delta (0.005 to 0.03) gave 0.90-0.915 versus 0.901 unfiltered: within noise. Vote router hurt.
- 7 of 71 queries still fail (all "situation" phrasings). A reranker could rescue about 4 (ceiling ~ +5 points).
- A distance cut-off cannot separate answerable from unanswerable questions (ranges overlap).
- e5-small: ~595 MB after load, ~685 MB after 20 queries, 59 ms per query on the owner's PC.

## Smoke test (local server, real keys)
- 2026-11-23, AFTER A1 (owner's run): 13/13 PASS. All 8 LLM answers came from Sarvam `sarvam-105b-conversations`;
  median latency 1.27 s (whole run, including static and rejected cases). Groq and OpenAI were never reached, so their
  parameters (`gpt-oss-120b` reasoning settings, `gpt-6-luna` `max_completion_tokens` / `reasoning_effort=none`)
  remain unverified: run `scripts/provider_check.py` to test each one directly.
- 2026-11-14, BEFORE A1: 13/13 PASS, but Sarvam returned 400 (`sarvam-30b` deprecated) and every answer came from
  the OpenAI fallback. Answer latency 4-19 s. Self-harm path 7 ms (static). Empty message correctly rejected.
- Answer QUALITY is still not evaluated (the smoke test checks status, safety level, helplines, script; not content).
- Owner's first read of real answers (2026-11-23): 8 findings in `docs/ANSWER_REVIEW_2026-11-23.md` (no abstain on
  out-of-scope, possibly wrong/outdated sections, irrelevant laws, Awadhi DV answered with FIR steps, helpline labels,
  forced long answers). No legal claim is marked verified or wrong. Labelled as cases aq001-aq008 for B6.

## Open backlog (rough priority)
1. Provider layer: done (A1). Groq/OpenAI parameters unverified until `scripts/provider_check.py` is run.
2. (Roadmap B0a) FIXED 2026-11-23: `/chat` was `async def` with blocking calls, so one slow answer froze the event loop
   for everyone. Now plain `def` (FastAPI runs it in its thread pool, AnyIO default 40 threads) and the first DB load
   is behind a lock. Proven on one event loop by `tests/test_concurrency.py` (failed 3/3 before the fix).
   Same pattern still in `/translate` (blocking 30 s httpx call) and `/`, `/stats` on a cold DB load: not fixed.
3. (Roadmap B0b) FIXED 2026-11-23: httpx's timeout restarts whenever bytes arrive, so a trickling provider could run
   past it. Each call now uses the SDK's async client inside `asyncio.wait_for` (hard wall-clock limit =
   min(LLM_TIMEOUT_SECONDS, budget left)); a timeout is retried like any other. The 60 s budget is now hard (only
   overshoot: under 1 s of retry pause, already checked). Proven with a real trickling server on 127.0.0.1.
   NOT yet re-checked against the real providers: re-run `provider_check.py` and the smoke test.
4. Security hardening: error text leaks (`str(e)` in 500s), no auth or rate limit on paid endpoints, no size limit on
   `/stt` upload and `/tts` text, CORS `*`, `/stats` shows server path, sessions (shared "default", guessable ids, never evicted).
5. Grounding: return sources, stop invented section numbers (system prompt says "always mention section"), abstain when passages
   do not answer; answer-quality evaluation (faithfulness, citation correctness, hallucination, language of the reply).
6. Safe ingestion: update/delete chunks, content hashes, stable ids, source registry (URL, date, version), stray
   `data/women_safety_chromadb_chunks.json` (20 chunks, not loaded) vs folder file (15).
7. Safety gaps (documented xfail tests): fire/medical emergencies, indirect suicidal phrasing, third-party crisis, being followed.
8. Speech: migrate STT off `saarika:v2.5`; error paths; measure on real Hindi and dialect audio.
9. Frontend: self-harm reply still shows the red "EMERGENCY - Call 112" banner; loading/error states; Android source missing.
10. Deployment: Render staging per `docs/render-staging-plan.md` (untested: CPU-only torch, model cache), readiness check, structured logs.
11. Docs: README, architecture and request diagrams, threat model, benchmark report, release report.

## Waiting on the owner (people tasks)
Native Awadhi/Bundeli speakers (templates in `evaluation/templates/`), a lawyer for `legal_review_template.csv`,
20-30 held-out test questions (keep unseen), Hindi review of `backend/safety.py` messages.

## Next session
(Claude Code: write here, at the end of each task, what to do next and anything half-finished.)
- A0 done (2026-11-23): docs reconciled with code; only lag was this file's commit/CI lines.
- A3 done: CI green, nothing to fix.
- A2 done: conftest guards + proof tests.
- A1 done: owner's smoke run 13/13, all answers from Sarvam. Caveat: Groq and OpenAI parameters never exercised.
- Added `scripts/provider_check.py` (one tiny prompt to EACH provider, no fallback) and `smoke_test.py --save-answers`
  (full answers to git-ignored `evaluation/results/smoke_answers/`). Owner to run provider_check with real keys;
  if gpt-6-luna rejects a parameter, set `OPENAI_MODEL=gpt-4o-mini` (works to 2027-01-14).
- Commits since `03feed2` are local, NOT pushed (owner confirms first).
- Answer review recorded; B5/B6 have their inputs. Legal claims in it still need checking against official texts, then a lawyer.
- B0a done (not pushed). Not verified on a real running server under concurrent load.
- B0b done (not pushed): the provider call path is now async inside each worker thread. Owner: re-run
  `scripts\provider_check.py` and `scripts\smoke_test.py` with real keys to confirm it on the real network.
