# Goals: what we are trying to achieve

## The product
NyayMitra 1.0 is a legal INFORMATION assistant for citizens of Uttar Pradesh. It explains rights, procedures and where to
go (police, legal aid, helplines) in simple language. It is not a lawyer and must never present itself as one.
Languages: Hindi, Hinglish, English now. Awadhi and Bundeli are a hard requirement, currently unmeasured.

## The owner's goals
1. A flagship AI/ML project that Divyansh (final-year B.Tech CS-AI, Lucknow) can DEFEND line by line in interviews:
   every number is measured, every limitation is known, nothing is faked.
2. Long term: UP government recognition or a pilot. That requires trust: legal review by a lawyer, safe handling of
   emergencies, privacy, reliability, honest limits, and dialect support checked by native speakers.
3. Third-party services (Sarvam, Groq, OpenAI) are acceptable now. The end goal is a more self-dependent system.
   Do not lock in to one vendor: keep the provider layer swappable.
4. Hosting: Render Standard (2 GB).

## What "good" means (measurable targets, to be confirmed by measurement, not assumed)
- Retrieval: report Hit@5/10, MRR on a HELD-OUT set. Current dev-set numbers are optimistic (see PROJECT_STATE).
- Answers: grounded in retrieved sources, with sources shown; abstains when passages do not answer; no invented sections.
- Safety: alert recall on emergency/self-harm as high as possible; false negatives are worse than false alarms; every
  known gap is a documented xfail test until fixed.
- Reliability: no single provider outage takes the bot down; failures degrade to a safe, language-aware message.
- Security: no key or stack-trace leaks, bounded uploads, rate limits, no shared sessions.
- Languages: measured per language (Devanagari Hindi, Hinglish, English, Awadhi, Bundeli). No dialect claim without native-speaker data.
- Reproducible: one command runs tests; one command runs evals; CI is green; docs say how.

## Non-goals (for now)
- A rewrite or new architecture (the NyayMitra 2.0 multi-agent idea is separate). Improve 1.0 first.
- Fine-tuning a model, new vector DB, agent frameworks. Only if a measured limit demands it.
- Giving legal advice about a specific case.

## Pilot-readiness checklist (what a government or NGO partner will ask)
- [ ] Lawyer-reviewed legal content, with a source registry (law, section, URL, date checked)
- [ ] Clear disclaimer and escalation to real helplines (112, 1090, 181, 1098, 14416; verified list only)
- [ ] Privacy: what is stored, retention, no conversation logging to providers beyond the question and passages; ask a lawyer about applicable data-protection law
- [ ] Dialect evaluation by native speakers, with published numbers
- [ ] Held-out evaluation report, including failures
- [ ] Uptime, monitoring, backups; staging and production separated
- [ ] Accessibility: low-literacy, voice in and out, low-bandwidth mobile
- [ ] Threat model and security review
