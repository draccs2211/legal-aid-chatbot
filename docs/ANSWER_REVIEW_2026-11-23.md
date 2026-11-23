# Answer review, 2026-11-23

**Reviewer:** the owner (not a lawyer). **Recorded by:** Claude Code.
**Answers reviewed:** `evaluation/results/smoke_answers/smoke_20261123_023112.json` (git-ignored, local only).
This file was produced by `scripts/smoke_test.py --save-answers` against a local server with real keys after A1.
All 8 model answers came from Sarvam `sarvam-105b-conversations`; 2 self-harm replies were the static message and
1 empty message was rejected.

## Status of every legal claim in this document

**No legal claim below is marked verified or wrong.** Each one is quoted from a model reply and has the status
**needs verification against the official text, then lawyer**. A wrong-looking claim may be right, and a
right-looking one may be outdated. Nothing here may be copied into the knowledge base or a prompt until a lawyer
has reviewed it (see `evaluation/templates/legal_review_template.csv`).

Hindi quotes are copied exactly; the English in brackets is a rough gloss by Claude Code, not a legal translation.

## How to read each finding

- **Owner finding:** what the owner saw.
- **Evidence:** what the saved reply says.
- **Claims to check:** each with the status above.
- **Observation from code (Claude Code):** a likely cause found by reading the code. Not yet tested.
- **Labelled case:** the matching entry in `evaluation/data/answer_quality_cases.json` (expected BEHAVIOUR only).

---

### 1. Out-of-scope question got traffic-challan content; no abstain

- **Case:** "Out-of-scope question", message `Weather in Lucknow today` (English).
- **Evidence:** the reply starts correctly ("I do not have access to live weather updates") and then gives about
  300 words of traffic rules, fines and a challan procedure, ending with "Today you should open the official
  traffic police website or app on your phone to check the live weather".
- **Claims to check** (all: needs verification against the official text, then lawyer):
  - speed limits "50 kmph" (city), "70 and 80 kmph" (highways), "up to 100 kmph" on UP expressways for cars,
    "80 kmph" for buses and trucks, "30 kmph" in school and hospital zones;
  - overspeeding fine "Rs 2000" (light vehicle) and "Rs 4000" (heavy vehicle) "under the Motor Vehicles Act 2019";
  - "Pay the fine within 60 days as required by the Motor Vehicles Amendment Act 2019".
- **Observation from code:** there is no abstain path. `generate_reply` always calls the model with whatever was
  retrieved, and the prompt requires a law, numbered steps, a helpline and a "today" step for every reply
  (`backend/config.py` SYSTEM_PROMPT rules 3, 4, 8; `backend/sarvam_client.py` `build_user_message` items 3-8).
  The reply ends with the `general` helpline string, so the domain detector returned `general`.
- **Labelled case:** `aq001`.

### 2. BNS rape punishment may be outdated ("minimum 7 years")

- **Case:** "Informational risk word", message `What is the rape law punishment under BNS?` (English).
- **Evidence:** "rape is covered under section 64 and carries a minimum punishment of 7 years in jail, which can
  extend to life imprisonment"; "penetrative sexual assault carries a minimum of 10 years imprisonment that can
  extend to life" (said of the POCSO Act 2012).
- **Claims to check** (needs verification against the official text, then lawyer):
  - BNS 2023 section 64 is the rape punishment section, and its minimum and maximum. Check the BNS text on
    https://www.indiacode.nic.in (owner's suggested source).
  - The POCSO minimum quoted above. Check the POCSO Act text on the same site.
- **Observation from code:** the prompt says "Always mention the specific law or section that applies", which pushes
  the model to state a section and a sentence even when the passages do not contain them. The `possible`-risk
  footer ("call 112") was added correctly.
- **Labelled case:** `aq002`.

### 3. Deposit answer treats the Model Tenancy Act 2021 s.11 as binding in UP; unexplained "Varanasi case"

- **Case:** "Hinglish deposit", message `Mera landlord deposit wapas nahi de raha` (Hinglish).
- **Evidence:**
  - "मॉडल टेनेंसी एक्ट 2021 की धारा 11 का सीधा उल्लंघन है, जिसके तहत घर खाली करने के 30 दिन के अंदर पूरा पैसा वापस
    करना जरूरी है" [it is a direct violation of Model Tenancy Act 2021 section 11, under which the full amount must be
    returned within 30 days of vacating];
  - "वाराणसी वाले मामले की तरह जिला उपभोक्ता आयोग में शिकायत दर्ज कराएं" [file at the district consumer commission
    "like the Varanasi case"]: the case is never explained;
  - "डिपॉजिट वापस न करना सेवा में कमी माना जाता है" [not returning a deposit counts as deficiency in service];
  - "यूपी शहरी भवन अधिनियम 1972 और ट्रांसफर ऑफ प्रॉपर्टी एक्ट" [UP Urban Buildings Act 1972 and the Transfer of
    Property Act].
- **Claims to check** (each: needs verification against the official text, then lawyer):
  - which tenancy law currently applies to residential tenancies in UP, and whether the Model Tenancy Act 2021
    applies there as binding law;
  - whether section 11 and the 30-day refund rule exist as quoted in the law that does apply;
  - whether an unrefunded deposit can go to a consumer commission as "deficiency in service";
  - whether the UP Urban Buildings Act 1972 is still in force for this situation;
  - what "the Varanasi case" refers to (it may come from a knowledge-base passage; trace it before judging it).
- **Labelled case:** `aq003`.

### 4. Eviction answer cites the Family Courts Act and UP Bhulekh; both look irrelevant

- **Case:** "Hindi tenant question", message `मकान मालिक ने बिना नोटिस घर खाली करने को कहा` (Devanagari Hindi).
- **Evidence:**
  - "फैमिली कोर्ट्स एक्ट 1984 के तहत" [under the Family Courts Act 1984], offered as a step "if the matter is a family
    or domestic dispute";
  - "यूपी भूलेख पोर्टल upbhulekh.gov.in पर जाकर अपनी खतौनी और केवाला की जानकारी चेक कर लें" [check your khatauni and
    kewala on the UP Bhulekh portal];
  - "सिविल कोर्ट से कानूनी आदेश लेना होगा" [the landlord must get a civil court order].
- **Claims to check** (needs verification against the official text, then lawyer): the eviction procedure and the
  forum the reply names; whether either the Family Courts Act or land records are relevant to a tenant's eviction.
- **Observation from code:** the reply ends with the `general` helpline (including 1076), not the `tenant` one, so the
  keyword detector returned `general` for this Devanagari message (it scored 0/55 on Devanagari Hindi in the
  retrieval evaluation). The detected domain still chooses the helpline even when `ROUTING_MODE=none`.
- **Labelled case:** `aq004`.

### 5. FIR answer may cite wrong sections (BNS 202 for refusal, BNSS 173(3) for the SP complaint)

- **Case:** "English FIR question", message `How do I file an FIR in UP?` (English).
- **Evidence:** "under BNSS Section 173 which replaced the old CrPC Section 154"; "as per BNSS Section 173(1)";
  "refusal is a punishable crime under BNS Section 202"; "file a written complaint to the SP under BNSS Section
  173(3)"; "approach a Judicial Magistrate under BNSS Section 175(3)".
- **Claims to check** (each: needs verification against the official text, then lawyer): every section number
  above against the BNS and BNSS texts on https://www.indiacode.nic.in, in particular BNS 202 (refusal to
  register) and BNSS 173(3) (complaint to the SP), which the owner flagged.
- **Labelled case:** `aq005`.

### 6. Awadhi domestic-violence message got FIR steps, not the domestic-violence passages

- **Case:** "Emergency (Awadhi, unreviewed)", message `हमार मनई हमका रोज मारत बाटै` (Awadhi; this sentence is in
  the smoke list and has NOT been reviewed by a native speaker).
- **Evidence:** the static emergency block came first (correct), then generic FIR filing steps and "इस मामले में
  बीएनएसएस धारा 173 175 और 176 लागू होती है" [BNSS sections 173, 175 and 176 apply]. It ends with the `general`
  helpline. The Hinglish domestic-violence case in the same run got Domestic Violence Act content and the
  `women_safety` helpline.
- **Claims to check** (needs verification against the official text, then lawyer): the BNSS sections quoted.
- **Observation from code:** the smoke test does not save which chunks were retrieved, so we cannot yet tell
  whether retrieval or generation went wrong. The `general` helpline shows the detector did not see this as
  women's safety. B6 should record retrieved chunk ids with every answer.
- **Labelled case:** `aq006`.

### 7. 1076 and "One Stop Centre: 181" appear in model replies; check them against the helpline registry

- **Evidence:**
  - "UP CM Helpline: 1076" (and the Hindi "यूपी सीएम हेल्पलाइन: 1076") appears in 3 replies: Hindi tenant, out-of-scope
    weather, Awadhi emergency.
  - "One Stop Centre: 181" (Hindi "वन स्टॉप सेंटर: 181") appears in 2 replies: the BNS question and the Hinglish
    emergency. In the Hinglish emergency reply, the static block a few lines earlier calls 181 "महिला हेल्पलाइन"
    [women helpline], so one reply gives 181 two different labels.
  - Landline numbers 0522-2308904 and 0522-2209457 also appear; `docs/verified-helplines.md` lists them as NOT verified.
- **Status:** needs verification against the official source, then lawyer, for number AND service label.
- **Observation from code:** the model did not invent these. They are copied from `DOMAIN_HELPLINES` in
  `backend/config.py` (`general` and `women_safety` entries), which the prompt tells the model to end with.
  `docs/verified-helplines.md` lists 181 as "UP Women Helpline (24x7)" (source: a news report, flagged for
  re-check), not "One Stop Centre". 1076 was added to the registry on 2026-11-23 as a grievance line from two
  UP government pages; the owner has not reviewed that entry yet.
- **Labelled case:** `aq007` (applies to every reply).

### 8. Answers are very long and end with a forced "today do this" line even when irrelevant

- **Evidence:** the 8 model replies are 175 to 389 words (median 257); the FIR reply is 389 words. All 8 end with a
  "today" action, including the weather reply ("Today you should open the official traffic police website or app
  ... to check the live weather").
- **Observation from code:** the prompt requires it in two places: SYSTEM_PROMPT rule 8 ("End every response with one
  practical next step the user can take TODAY") and `build_user_message` item 8 ("the user needs to take action
  today"), plus numbered steps whenever "a process or procedure is involved".
- **Labelled case:** `aq008` (applies to every reply).

---

## What happens next

- Roadmap: these findings are inputs to **B5** (grounding, abstain, citations, prompt) and **B6** (answer-quality
  evaluation). See `docs/ROADMAP.md`.
- Every claim above goes to the lawyer review only after it has been checked against the official text.
- The saved answers file is local and git-ignored; keep it until B6 has a reproducible run that replaces it.
