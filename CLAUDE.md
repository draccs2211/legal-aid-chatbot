# NyayMitra 1.0: instructions for Claude Code

AI legal-INFORMATION chatbot for Uttar Pradesh citizens (not legal advice). FastAPI backend, RAG over
174 chunks (11 legal domains) in ChromaDB, LLM chain Sarvam -> Groq -> OpenAI, Hindi/Hinglish/English.
Awadhi and Bundeli are a requirement but are still unmeasured.
Repo: github.com/draccs2211/legal-aid-chatbot. Work branch: `audit/phase1`.
Start every session by reading: @docs/PROJECT_STATE.md (current state) and @docs/ROADMAP.md (work queue).
Read on demand: docs/GOALS.md (why, targets, pilot checklist), docs/HISTORY.md (what was done, incidents, lessons).

## How to work (non-negotiable)
- Understand before editing: read the code, its callers and its tests first. No speculative changes.
- Small, reviewable changes, one concern per commit. Add or update tests with every change.
- Never claim something passed or improved without running it. Say what you ran and what you did not.
- Retrieval changes are measured with the evaluation harness against the baseline. The labelled set was
  tuned on, so numbers are optimistic until a held-out set exists. Do not oversell them.
- Explain decisions in simple English. The owner is a developing AI/ML engineer who must be able to
  defend every choice in an interview.
- Prefer removing complexity to adding it. No new framework, vector DB or agent system without a
  demonstrated limitation.
- Check current official docs before touching a provider, model name or API. Model names go stale.

## Safety rules
- NEVER read, print, copy or commit `.env` or any API key. `.env` holds real keys. Document variables in
  `.env.example` only. Tests must not use real keys or the network: fake the providers.
- Never push to `main`, never force-push, never merge a pull request. Work on `audit/phase1` only.
  Render auto-deploys from `main`, so merging deploys to production.
- Legal content: never invent laws, sections, deadlines or phone numbers. Helplines come only from
  `docs/verified-helplines.md`. Edits to legal text need a lawyer's review.
- `backend/safety.py` is safety-critical (emergency and self-harm). Bias towards alerting. Any change
  needs labelled cases in `tests/data/risk_labelled.json`. Dialect cases there are unreviewed by native speakers.
- Self-harm path: fixed supportive message, no retrieval, no LLM, nothing stored. Do not change that design.
- Never write dialect (Awadhi/Bundeli) test sentences yourself and present them as real; they need native speakers.

## Environment (Windows, PowerShell, Python 3.10)
- Python: `.\.venv\Scripts\python.exe`   (activate: `.\.venv\Scripts\Activate.ps1`)
- Tests: `.\.venv\Scripts\python.exe -m pytest`   (last known: 655 passed, 11 xfailed; xfail = documented gap).
  `tests/conftest.py` blanks API keys and blocks outside network in every test; keep it that way.
- Server: `cd backend; ..\.venv\Scripts\python.exe -m uvicorn main:app --port 8000`
- Smoke test (server running): `.\.venv\Scripts\python.exe scripts\smoke_test.py`
- Doctor (read-only diagnosis of config and DB): `.\.venv\Scripts\python.exe scripts\doctor.py`
- Retrieval eval: `.\.venv\Scripts\python.exe evaluation\run_retrieval_eval.py --label NAME --quiet --modes unfiltered`
- Risk eval: `.\.venv\Scripts\python.exe scripts\eval_risk.py`
- Git CRLF warnings on Windows are harmless. CI is GitHub Actions running pytest with `requirements-ci.txt`.

## Layout
- `backend/` main.py (API), config.py (env + validation), rag_pipeline.py, embedding.py (optional
  multilingual embedder), intent_detector.py, safety.py, sarvam_client.py (LLM chain), sarvam_speech.py
- `data/<domain>/<domain>_chromadb_chunks.json`: the knowledge base. `chromadb_store/` is generated and git-ignored.
- `evaluation/`: metrics, retrievers, labelled sets (`data/`), results (`results/`), templates for people.
- `tests/`, `scripts/` (loader, doctor, smoke test, evals), `docs/` (plans, policies, registries).
- `frontend/`: static web app. The Android app is a WebView wrapper whose source is NOT in this repo.

## Configuration flags (see .env.example)
EMBEDDING_BACKEND (chroma_default | sentence_transformers), EMBEDDING_MODEL, ROUTING_MODE (hard | none),
CHROMADB_PATH (relative values resolve against the repo root). Defaults reproduce the original behaviour.
A new embedding model gets its own collection. Never mix models inside one collection.

## Decisions already made
- Third-party services are fine for now (Sarvam, Groq, OpenAI); long-term goal is self-hosted. Send providers
  only the question and retrieved passages. Do not log whole conversations.
- Hosting: Render Standard (2 GB). The multilingual model needs about 0.6-0.7 GB RAM.
- Replies in simple Hindi or English first; replies written in Awadhi/Bundeli come later with native review.
- Production is NOT switched to the multilingual embedder yet. Plan: `docs/render-staging-plan.md`.

## Facts you must not rediscover the hard way
- `sarvam-30b` is DEPRECATED: the live API returns 400. Per Sarvam docs the replacements are `sarvam-105b` and
  `sarvam-105b-conversations`. Until fixed, every answer comes from the OpenAI fallback.
- Sarvam STT `saarika:v2.5` is listed as deprecated; Saaras (v4 recommended) is current. Not migrated yet.
- A wrong `CHROMADB_PATH` in `.env` once silently created an empty database. Run the doctor first.
- Real LLM latency seen in a smoke run: 4 to 19 seconds per answer. Nothing has been optimised.

## You are the project driver
The owner works with you directly. Pick the next unchecked item in docs/ROADMAP.md unless told otherwise, propose a plan
before editing, and never skip the blocked-on-owner items by faking data. If the owner says "continue", continue the roadmap.
At the END of every task update docs/PROJECT_STATE.md (state, numbers, new findings) and tick docs/ROADMAP.md only with evidence.
Keep a short "Next session" note at the bottom of PROJECT_STATE.md so a fresh session can resume.

## Definition of done for a task
Tests pass (state the count), new behaviour has tests, docs updated, `git status` shows no secrets, small commit
with a clear message, pushed to `audit/phase1`, CI green. Then list what remains unverified.
