# Trying the multilingual build on Render (staging first)

Goal: run the `audit/phase1` code with the multilingual embedder on a **separate
Render service**, check it with `scripts/smoke_test.py`, and only then touch
production. The existing service is never modified during this.

Render facts below come from Render's own docs (checked 2026-11-08). Items marked
**untested** are my recommendations and have not been run on Render.

## Facts that matter

* **Python version.** Render's default for services created on or after 2026-02-11 is
  3.14.3. This project is tested on **3.10**. Render picks the version from the
  `PYTHON_VERSION` environment variable (a fully qualified version such as `3.10.14`)
  or from a `.python-version` file in the repo root. The repo's old `startup.txt`
  is not used by Render. The branch now contains `.python-version` with `3.10`.
* **Memory.** Free and Starter services have 512 MB; Standard has 2 GB. The
  embedding model alone used about 600 to 700 MB on a development PC, so the
  multilingual build needs Standard (or a smaller model).
* **Port.** Render's default is 10000; the start command already uses `$PORT`.

## Create the staging service (Render dashboard)

| Setting | Value |
|---|---|
| Type / runtime | Web Service, Python 3 |
| Repository / branch | `draccs2211/legal-aid-chatbot`, branch **`audit/phase1`** |
| Instance type | **Standard** (2 GB); check the current price in the dashboard |
| Auto-deploy | off while testing |
| Health check path | `/health` |
| Start command | `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |

Run one uvicorn worker only: each worker would load its own copy of the model.

**Build command (untested):** install the CPU-only PyTorch first, because the default
Linux wheel pulls in GPU libraries worth gigabytes, then the rest, then download the
model into the build.

    pip install --upgrade pip && pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

Check the PyTorch install selector for the current CPU command. If the model
downloaded at build time is not found at run time, the service still works, but it
downloads about 470 MB on every start.

**Environment variables**

| Key | Value |
|---|---|
| `EMBEDDING_BACKEND` | `sentence_transformers` |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` |
| `ROUTING_MODE` | `none` |
| `HF_HOME` | `/opt/render/project/src/.hf-cache` (untested; keeps the model cache inside the build) |
| `SARVAM_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY` | your keys, entered in the dashboard only |

Leave `CHROMADB_PATH` unset (it defaults to `chromadb_store` in the repo). The disk
is rebuilt on every deploy, and the app fills the index at start-up.

## Checks after the first deploy

1. **Logs:** you should see `[rag] ChromaDB path: ...`, the model loading, and the
   server starting. A start-up error about `EMBEDDING_BACKEND` means a typo in the
   variables (they are validated).
2. **Smoke test from your PC:**

       python scripts\smoke_test.py --base-url https://<your-staging-service>.onrender.com

   Every line should say PASS. The `/stats` line should show 174 chunks and the
   multilingual model. Latency of the first calls shows the cold behaviour.
3. **Memory graph** in the Render dashboard after a few calls. Expect roughly 0.8 to
   1 GB (an estimate); if it climbs above about 1.5 GB, stop and tell me.
4. **A real answer:** ask three questions from the retrieval set (Hindi, Hinglish,
   English) and read the replies for quality. The smoke test cannot judge wording.

## Rolling out to production (two phases)

1. **Merge with defaults.** Merge the pull request. The production service then runs the
   new code with its current settings (no `EMBEDDING_*` variables), so retrieval behaves
   as before; the safety fixes, tests and docs ship. Note that `.python-version` also
   pins production to 3.10, which is what everything was tested on.
2. **Switch on.** Upgrade the production instance to Standard and add
   `EMBEDDING_BACKEND`, `EMBEDDING_MODEL` and `ROUTING_MODE`. Run the smoke test against
   it.

**Rollback:** remove those three variables (the original behaviour returns), or
redeploy the previous commit. A staging service can simply be deleted.

## Not decided or not verified

* Whether the model cache survives from build to run on Render.
* Real memory and latency on Render's CPU (a development PC is faster).
* Security hardening is still open: the service is unauthenticated, so do not publish
  the staging URL.
