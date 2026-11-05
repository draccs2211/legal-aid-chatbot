# Language support: requirement, status and acceptance criteria

**Requirement (project owner):** the chatbot must be able to handle **Hindi,
Hinglish, Awadhi and Bundeli**.

Status below is honest as of 2026-11-05. "Not measured" means we have no
evidence either way; it does not mean "works".

## What "handle" should mean (proposal, to be confirmed)

1. **Understand**: a user writes or speaks in the language and retrieval finds
   the right legal chunk.
2. **Stay safe**: emergency and self-harm phrases in that language trigger the
   safety path (`backend/safety.py`).
3. **Reply**: in simple Hindi that Awadhi and Bundeli speakers understand.
   Writing replies *in* Awadhi or Bundeli is a separate, optional step that
   needs native-speaker review, because a fluent but wrong legal sentence is
   worse than a plain Hindi one.
4. **Speech**: spoken input is transcribed well enough to be understood; spoken
   output is in Hindi.

## Status

| Capability | Hindi (Devanagari) | Hinglish (Roman) | Awadhi | Bundeli |
|---|---|---|---|---|
| Retrieval (Hit@5, baseline) | 0.20 (5 queries, rough) | 0.78 (50 queries) | not measured | not measured |
| Safety phrases | tested | tested | best-effort patterns, unreviewed | best-effort patterns, unreviewed |
| Language detection | by script: works | marker words: works | Devanagari: works; **Roman: detected as English** | Devanagari: works; **Roman: detected as English** |
| Speech to text | Sarvam, **legacy model in use** | same | not measured | not measured |
| Speech output | Hindi voice | Hindi voice | Hindi voice only | Hindi voice only |

## Evidence and limits

* The app transcribes with `saarika:v2.5`. Sarvam's docs list it as a legacy
  model; the current one is Saaras (v3/v4).
* Sarvam's speech-to-text, Sarvam Translate and the chat model are documented
  for the 22 official Indian languages plus English. In the pages I found,
  **Awadhi and Bundeli are not mentioned**. Bulbul v3 text-to-speech lists 11
  languages (10 Indian plus English).
* Research describes Hindi-belt dialects, including Awadhi and Bundeli, as
  under-resourced, with very little text and speech data.
* Awadhi and Bundeli vary by district and have no standard spelling, so typed
  (especially Roman-script) text is highly variable.
* The dialect safety patterns were written by a non-native drafter to match the
  drafter's own example sentences. They prove nothing about real speech until
  native speakers supply real phrasings (see `docs/dialect-data-collection.md`).

## Acceptance criteria (proposal; revisit after the first measurements)

* **Safety:** on native-reviewed dialect cases, no missed emergency or
  self-harm message outside documented gaps, and no benign message alarmed.
* **Retrieval:** Hit@5 on the reviewed dialect set within 10 points of the
  English phrasing of the same questions, on at least 40 queries per dialect
  written by at least 2 native speakers.
* **Reply quality:** native reviewers rate at least 80% of 30 sampled replies
  per dialect as understandable and faithful in meaning. Legal accuracy remains
  a lawyer's review.
* **Speech:** transcription error rate measured on at least 50 recorded
  utterances per dialect from at least 3 speakers; the target is set after the
  first measurement.

## Sources (checked 2026-11-05)

* Sarvam models overview: https://docs.sarvam.ai/api-reference-docs/getting-started/models
* Sarvam speech-to-text quickstart: https://docs.sarvam.ai/api-reference-docs/asr/quickstart
* Hindi dialect resources (ACL WAT 2025): https://preview.aclanthology.org/ingest-ijcnlp-aacl/2025.wat-1.5.pdf
* Saarika deprecation note (third party): https://docs.livekit.io/reference/agents-js/modules/plugins_agents_plugin_sarvam.html
