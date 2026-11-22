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

## Incidents and lessons (do not repeat)
- `.env` had `CHROMADB_PATH=./chromadb_storecd backend` (two commands pasted into one line). Chroma silently created an empty DB.
  Lesson: validate paths, run the doctor. The owner rewrote `.env` without BOM via PowerShell.
- The first doctor was not read-only: opening Chroma writes to disk and dirtied tracked files. Fixed with a temp-copy approach.
- Distance-scale bug: the eval index used squared-L2 while production uses cosine. Fixed. Older e5 distance tables must be halved.
- Provider-down message was hard-coded English; now language-aware. An unverified helpline number (1076) was removed.
- A predicted crash in `test_rag.py` was misdiagnosed once (it was ModuleNotFoundError, not ValueError). Lesson: reproduce before claiming.
- A zip applied without its dependency caused 2 failing tests. Lesson: small commits, run the full suite each time.
- Sarvam `sarvam-30b` returns 400 (deprecated). Not fixed yet = task A1. All real answers came from OpenAI, so
  real answer quality has never been evaluated.
- CI was never fully verified before pushing; GitHub's first run is the real check.

## Sarvam facts (checked 2026-11-14; re-check before use)
Chat: `sarvam-105b` (128K ctx, reasoning low by default), `sarvam-105b-conversations` (32K, no reasoning); Sarvam-30B and Sarvam-M
deprecated. STT: Saaras v4 recommended, Saarika deprecated. TTS Bulbul v4 Flash/v3: no Awadhi/Bundeli. Awadhi and Bundeli are
not listed for any Sarvam service seen.

## Working style that worked
Reproduce first, fix small, test, measure, then document. Be honest about optimistic numbers. Ask before touching data files.
