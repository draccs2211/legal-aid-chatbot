# Roadmap (Claude Code: this is your work queue; update statuses here as you finish things)

Rule: one phase at a time, one task per branch commit group, tests with every change, push to `audit/phase1` only.
Status legend: [ ] todo  [~] in progress  [x] done (only after evidence: tests run, output shown)

## Phase A: fix what is broken (est. 2-3 days)
- [ ] A0 Orientation: confirm repo state, run tests, reconcile docs with code
- [ ] A1 Provider layer: replace deprecated `sarvam-30b` (check CURRENT Sarvam docs), env-configurable model names,
      verify Groq and OpenAI model names, log which provider answered, timeouts, bounded retries, fake-provider tests
- [ ] A2 `tests/conftest.py`: blank API keys, block network in all tests; prove it
- [ ] A3 Check GitHub Actions CI result for the branch; fix anything red (first real run of CI)
Acceptance: smoke test shows which provider answered; no test can reach a real API.

## Phase B: security and trust (est. 4-6 days)
- [ ] B1 Error handling: no `str(e)` in responses, no stack traces or key-like strings (tested)
- [ ] B2 Limits: size limits on `/stt` upload and `/tts` text; rate limiting on `/chat`, `/stt`, `/tts`
- [ ] B3 CORS configurable via env (no `*` in production); `/stats` no longer exposes server paths
- [ ] B4 Sessions: server-generated ids, no shared "default", eviction of old sessions
- [ ] B5 Grounding: return sources with each answer; prompt forces use of passages only; abstain when passages do not
      answer; stop invented section numbers (current system prompt says "always mention section")
- [ ] B6 Answer-quality evaluation: answerable vs unanswerable set, faithfulness, abstain accuracy, citation correctness,
      reply-language check; fake providers in CI, real providers on demand
Acceptance: threat-model doc lists each risk with its fix or status; answer eval report committed with honest numbers.

## Phase C: data and safety (est. 3-5 days)
- [ ] C1 Safe ingestion: idempotent loader with content hashes; add/update/unchanged/removed report; never touch another model's collection
- [ ] C2 Source registry for every chunk (law, section, URL, date checked, reviewer). Resolve stray `data/women_safety_chromadb_chunks.json` (20 chunks, not loaded) vs folder file (15): ASK the owner
- [ ] C3 Safety gaps (the 11 xfails): fire/medical emergencies, indirect suicidal phrasing, third-party crisis, being followed.
      Fix with labelled cases first; Hindi message wording reviewed by the owner
- [ ] C4 Frontend: self-harm reply must not show the red "EMERGENCY - Call 112" banner; loading and error states
- [ ] C5 Speech: migrate STT off deprecated `saarika:v2.5` (check current Sarvam docs; Saaras v4 recommended as of Nov 2026)
Acceptance: xfail count drops with each fix; ingestion tests use a temporary store.

## Phase D: deployment (est. 2-3 days)
- [ ] D1 Render STAGING service per `docs/render-staging-plan.md` (CPU-only torch, model cache, Python 3.10)
- [ ] D2 Readiness check endpoint, structured logs without user text
- [ ] D3 Run smoke test against staging; measure memory and latency
- [ ] D4 Only then: production switch to the multilingual embedder (`EMBEDDING_BACKEND=sentence_transformers`,
      `EMBEDDING_MODEL=intfloat/multilingual-e5-small`, `ROUTING_MODE=none`) via env change, with rollback plan. OWNER merges, never Claude Code.

## Phase E: make it defensible (est. 3-4 days)
- [ ] E1 README: what it is, how to run, how to test, limits
- [ ] E2 Architecture and request-flow diagrams
- [ ] E3 Benchmark report: baseline vs multilingual embedder, with the dev-set caveat; held-out numbers once the owner supplies questions
- [ ] E4 Optional measured experiments, only with a baseline: reranker (could rescue ~4 of 7 failing queries), BGE-M3 (unmeasured)
- [ ] E5 Release report: what works, what is unverified, known risks

## Blocked on the owner (do not fake these)
- 20-30 held-out questions (owner writes; never let the model write them and call them held-out)
- Native Awadhi/Bundeli speakers; templates in `evaluation/templates/`
- Lawyer review (`legal_review_template.csv`)
- Hindi review of `backend/safety.py` messages
- `backup/local-main` old-folder backup check
