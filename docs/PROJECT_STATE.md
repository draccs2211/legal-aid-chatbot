# Project state (2026-11-23)

Branch `audit/phase1`, last pushed commit `efc359c`. Run `git status` and `git log --oneline -5` to see anything newer.
GitHub Actions result for the CI workflow has NOT been reported yet: check the Actions tab.

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

## Smoke test (local server, multilingual embedder, real keys): 13/13 PASS
- Sarvam call failed with 400: model `sarvam-30b` deprecated. All answers came from the OpenAI fallback.
- Answer latency 4-19 s. Self-harm path 7 ms (static). Empty message correctly rejected.

## Open backlog (rough priority)
1. Provider layer: replace `sarvam-30b` (check current Sarvam docs), make model names env-configurable, verify Groq and
   OpenAI model names, log which provider answered, bounded timeouts and retries, tests for each failure mode.
2. `tests/conftest.py`: blank all API keys and block network in every test so a real key can never be used by accident.
3. Security hardening: error text leaks (`str(e)` in 500s), no auth or rate limit on paid endpoints, no size limit on
   `/stt` upload and `/tts` text, CORS `*`, `/stats` shows server path, sessions (shared "default", guessable ids, never evicted).
4. Grounding: return sources, stop invented section numbers (system prompt says "always mention section"), abstain when passages
   do not answer; answer-quality evaluation (faithfulness, citation correctness, hallucination, language of the reply).
5. Safe ingestion: update/delete chunks, content hashes, stable ids, source registry (URL, date, version), stray
   `data/women_safety_chromadb_chunks.json` (20 chunks, not loaded) vs folder file (15).
6. Safety gaps (documented xfail tests): fire/medical emergencies, indirect suicidal phrasing, third-party crisis, being followed.
7. Speech: migrate STT off `saarika:v2.5`; error paths; measure on real Hindi and dialect audio.
8. Frontend: self-harm reply still shows the red "EMERGENCY - Call 112" banner; loading/error states; Android source missing.
9. Deployment: Render staging per `docs/render-staging-plan.md` (untested: CPU-only torch, model cache), readiness check, structured logs.
10. Docs: README, architecture and request diagrams, threat model, benchmark report, release report.

## Waiting on the owner (people tasks)
Native Awadhi/Bundeli speakers (templates in `evaluation/templates/`), a lawyer for `legal_review_template.csv`,
20-30 held-out test questions (keep unseen), Hindi review of `backend/safety.py` messages.

## Next session
(Claude Code: write here, at the end of each task, what to do next and anything half-finished.)
- Not started: Phase A0 orientation. See docs/ROADMAP.md.
