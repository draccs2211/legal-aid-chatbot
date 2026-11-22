# History: what has been done so far (chronological, condensed)

1. Audit of the original NyayMitra 1.0 (FastAPI + RAG + ChromaDB + Sarvam/Groq/OpenAI chain). Repo cloned to
   `C:\dev\nyaymitra`, work on branch `audit/phase1`. Old requirements file mix-up (`requirements.tx`) cleaned up.
2. Bugs found and fixed (all with tests): fragment-matching router; cyber domain name mismatch; domain not passed to
   helpline lookup; missing comma in Hinglish markers; broken `scripts/test_rag.py` (wrong import path and format string).
3. Safety rewrite: four levels (none, possible, emergency, self_harm), static self-harm message without LLM or retrieval,
   verified helplines only. Labelled risk set of 98 messages; alert recall 42/46 at that time; 8 (later 11) documented xfails.
4. Retrieval evaluation harness built: Hit@K, Recall, Precision, MRR, nDCG; modes routed/oracle/unfiltered; graded relevance.
   Results in `evaluation/results/`.
5. Multilingual embedder (e5-small) added behind flags, in its own collection; verified on the real code path.
   Hit@5 0.789 -> 0.901; Devanagari Hindi 3/55 -> 48/55. Keyword router found harmful with it (0/55 on Hindi), so `ROUTING_MODE=none`.
6. Config hardening: `CHROMADB_PATH` resolved against repo root; `_choice` validation; `.env.example`.
7. Doctor script (read-only; reads a temp copy of the sqlite file), smoke test (13/13), CI workflow, `.python-version`.
8. Branch pushed to GitHub, NOT merged. Render production still runs the original system.
9. (2026-11-23) Test guards: `tests/conftest.py` blanks keys and blocks network. 1076 verified. Provider layer
   rewritten (A1): one chain, env model names, per-attempt timeout plus total budget, retry only on timeout/5xx/429,
   reasoning text stripped, safe logs, `provider` in `/chat` responses.

## Incidents and lessons (do not repeat)
- `.env` had `CHROMADB_PATH=./chromadb_storecd backend` (two commands pasted into one line). Chroma silently created an empty DB.
  Lesson: validate paths, run the doctor. The owner rewrote `.env` without BOM via PowerShell.
- The first doctor was not read-only: opening Chroma writes to disk and dirtied tracked files. Fixed with a temp-copy approach.
- Distance-scale bug: the eval index used squared-L2 while production uses cosine. Fixed. Older e5 distance tables must be halved.
- Provider-down message was hard-coded English; now language-aware. An unverified helpline number (1076) was removed
  from that message. 1076 (UP CM grievance helpline) was later verified on 2026-11-23 against two UP government
  pages (see `docs/verified-helplines.md`); it remains in the `general` domain helpline, not in emergency text.
- A predicted crash in `test_rag.py` was misdiagnosed once (it was ModuleNotFoundError, not ValueError). Lesson: reproduce before claiming.
- A zip applied without its dependency caused 2 failing tests. Lesson: small commits, run the full suite each time.
- Sarvam `sarvam-30b` returns 400 (deprecated). Replaced in A1 (2026-11-23) by `sarvam-105b-conversations`; not yet
  confirmed by a real call. All real answers so far came from OpenAI, so real answer quality has never been evaluated.
- Groq was probably also dead (llama-3.3 shutdown for free tiers, 2026-08-16) without anyone noticing: failures were
  only `print`ed. Lesson: log which provider answered and surface it.
- CI was never fully verified before pushing; GitHub's first run is the real check.

## LLM provider facts (checked 2026-11-23; re-check before changing a model name)
Each claim with its source. These are what the docs SAY; none is confirmed by a real call until the owner's smoke run.
- Sarvam chat serves only `sarvam-105b` (128K) and `sarvam-105b-conversations` (32K). Reasoning is returned in a
  separate `reasoning_content` field; `reasoning_effort` defaults to `medium` and is on by default for `sarvam-105b`;
  `-conversations` never reasons (any level ignored). Source: https://docs.sarvam.ai/api-reference-docs/chat/chat-completions
  (checked 2026-11-23). The page is inconsistent on auth (Bearer vs `api-subscription-key`); our code uses the OpenAI SDK (Bearer).
- Groq: `llama-3.3-70b-versatile` scheduled for shutdown on 2026-08-16 for free and developer tiers (deprecation
  e-mail 2026-06-17); replacements `openai/gpt-oss-120b` or `qwen/qwen3.6-27b`. Source: https://console.groq.com/docs/deprecations
  (checked 2026-11-23). The models page https://console.groq.com/docs/models still lists it as an Enterprise production model.
- Groq `openai/gpt-oss-120b`: reasoning in a separate `reasoning` field (no `<think>` tags), hidden with
  `include_reasoning=false`; `reasoning_effort` low/medium/high; `reasoning_format` not supported.
  Source: https://console.groq.com/docs/reasoning (checked 2026-11-23).
- OpenAI `gpt-4o-mini`: deprecated 2026-10-14, shutdown 2027-01-14, recommended replacement `gpt-6-luna`.
  Source: https://developers.openai.com/api/docs/deprecations (checked 2026-11-23).
- OpenAI `gpt-6-luna`: supported on `v1/chat/completions`; `reasoning_effort` none/low/medium/high/xhigh/max, default
  `medium`. The page does NOT say whether it accepts `temperature` or `max_tokens`: we send `max_completion_tokens`
  and no temperature (unverified). Source: https://developers.openai.com/api/docs/models/gpt-6-luna (checked 2026-11-23).
- OpenAI Python SDK defaults (what the old code silently used): 10-minute timeout and 2 automatic retries. Now
  overridden (`max_retries=0`, our own timeout). Verified in code: `tests/test_provider_chain.py`.

## Sarvam facts (checked 2026-11-14; re-check before use)
Chat: `sarvam-105b` (128K ctx, reasoning low by default), `sarvam-105b-conversations` (32K, no reasoning); Sarvam-30B and Sarvam-M
deprecated. STT: Saaras v4 recommended, Saarika deprecated. TTS Bulbul v4 Flash/v3: no Awadhi/Bundeli. Awadhi and Bundeli are
not listed for any Sarvam service seen.

## Working style that worked
Reproduce first, fix small, test, measure, then document. Be honest about optimistic numbers. Ask before touching data files.
