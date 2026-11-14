# Third-party services: policy for now, plan for later

**Decision (2026-11-07):** depending on third-party services is fine for now; the
long-term goal is a system that does not depend on them.

## Used today

| Service | For | Notes |
|---|---|---|
| Sarvam | chat model (`sarvam-30b`), speech to text, text to speech, translation | speech-to-text model `saarika:v2.5` is listed as legacy |
| Groq, OpenAI | fallback chat models | OpenAI fallback is not in the README |
| Hugging Face | one-time download of the embedding model | the embedding model itself then runs on our server |
| Render | hosting | Standard plan (2 GB) planned |

## Rules while we depend on them

1. **Send the minimum:** the user's question and the retrieved passages. No other
   users' text, no IP addresses, no session identifiers.
2. **Do not log whole conversations by default.** Log metadata: provider used,
   latency, error category, retrieved chunk ids.
3. **Tell users** on first use that their question is processed by third-party AI
   services, not to type names, phone numbers or Aadhaar numbers, and which numbers to
   call in an emergency.
4. **Before any public pilot:** read each provider's current terms on data
   retention and use of inputs for training, and have a lawyer check the plan against
   the Digital Personal Data Protection Act. Neither has been done.
5. **Keep every provider behind a small interface** with a fake implementation for
   tests, so replacing one is a configuration change and not a rewrite.
6. **Every provider needs a defined failure path.** The chat chain already ends in a
   static emergency message; speech and translation do not yet have one.

## Path to a self-dependent system

Switch a component only when its replacement is measured on our own test sets and is
close enough in quality, with acceptable cost, speed and memory.

| Component | Now | Self-hosted direction (to be evaluated) | What to measure |
|---|---|---|---|
| Embeddings | e5-small on our server (once switched on) | larger multilingual models | Hit@5 on the labelled sets, memory, speed |
| Chat model | Sarvam API with fallbacks | an open-weight model on our own server | answer faithfulness to retrieved text, Hindi quality, cost per answer, GPU need |
| Speech to text | Sarvam | an open speech model | error rate on recorded Hindi and dialect audio |
| Text to speech | Sarvam | an open voice | listener rating, speed |
| Query rewriting | none | a small model or rules | does it beat plain embeddings on situation and dialect queries |
| Vector database | Chroma on disk | stays | restore and update safety |
| Hosting | Render Standard | own server or cloud | uptime, cost |

Nothing in this table has been tested yet except the embeddings.
