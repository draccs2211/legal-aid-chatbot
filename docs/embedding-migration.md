# Switching to a multilingual embedding model

Status: **built behind flags, not enabled by default.** With no environment
variables set, behaviour is exactly as before.

## Why

On the labelled queries (`evaluation/`), Chroma's default embedder
(`all-MiniLM-L6-v2`, English) scores about chance level on Hindi in Devanagari
(Hit@5 3/55 with no domain filter). `intfloat/multilingual-e5-small` scores
48/55 on the same questions, and on the full 71 answerable queries Hit@5 goes
from 0.789 (today's routed pipeline) to 0.901 with no filter at all
(0.859 with the keyword router's hard filter). Measured on the development set
only; a held-out set and Awadhi/Bundeli data are still needed.

## Switching on (PowerShell, from the repo root)

    $env:EMBEDDING_BACKEND = "sentence_transformers"
    $env:ROUTING_MODE      = "none"        # recommended with this model, see below
    python scripts\load_chromadb.py         # builds a NEW collection; the old one is untouched
    python evaluation\run_retrieval_eval.py --label prod_parity --retrievers baseline --modes unfiltered

`baseline` in the runner means "the production pipeline as configured by the
environment", so the last command checks the real code path. Expect Hit@5 close
to the `st:intfloat/multilingual-e5-small` unfiltered row (0.901). Exact
agreement is not guaranteed because Chroma's index is approximate.

## Rolling back

Remove the two environment variables (or set `EMBEDDING_BACKEND=chroma_default`).
The original collection `nyaymitra_legal` was never modified.

## Safety checks built in

* The new model gets its own collection (`nyaymitra_legal__intfloat_multilingual_e5_small`).
* The collection records which model built it; opening it with a different
  `EMBEDDING_MODEL` raises an error instead of silently mixing vector spaces.
* `EMBEDDING_BACKEND` and `ROUTING_MODE` are validated; a typo stops startup.
* With the external backend the model loads at startup (`warm_up`), not on the
  first user request.

## Why `ROUTING_MODE=none`

With this model the keyword router's hard filter *lowers* Hit@5 (0.859 versus
0.901 unfiltered on the full set; 0.818 versus 0.873 on the 55-query parallel
set). A perfect router would give 0.958, so a better router is still worth
building, but today's keyword router does not earn its keep.

## Cost: RAM and speed

Measured on a development PC (CPU): load about 10 s, process memory about
595 MB after loading and 685 MB after 20 queries, about 59 ms per query.

Render web services: Free and Starter have 512 MB; Standard has 2 GB
(https://render.com/docs/compute-plans, pricing page, checked 2026-11-05).
**The model alone does not fit in 512 MB**, so this needs at least the Standard
plan, or a smaller/quantised model, or a hosted embedding service; each of
those must be measured before relying on it. CPU on a hosted instance will be
slower than a development PC.

## Not done yet

* No held-out evaluation; no Awadhi or Bundeli measurement.
* No load or concurrency test; one model instance per process.
* Production `render.yaml` and the Render plan are unchanged.
* Stale or edited chunks are still not updated by the loader (audit F-09).
