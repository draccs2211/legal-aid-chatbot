# Outreach kit: native speakers and legal reviewers

Two things block the next stage and neither can be solved with code:
real Awadhi and Bundeli phrasings, and a qualified person checking the legal text.

## What we need (minimum useful amounts)

| Need | Who | How much | File to send |
|---|---|---|---|
| Awadhi phrasings | 2 to 3 native speakers from different districts | about 30 to 45 minutes each | `evaluation/templates/dialect_queries_template.csv` and `dialect_safety_template.csv` |
| Bundeli phrasings | 2 to 3 native speakers from different districts | same | same two files |
| Legal accuracy review | 1 to 2 qualified advocates (or a final-year law student reviewing under an advocate's supervision) | the 80 priority-1 passages first; a rough estimate is 2 to 3 minutes per passage, so about 3 to 4 hours (an estimate, not a measurement) | `evaluation/templates/legal_review_template.csv` |

Two independent writers per dialect matter more than one writer doing more rows:
people from different districts spell and phrase things differently.

## Where to look (suggestions, none verified)

* **Awadhi** is spoken across the Awadh region of Uttar Pradesh, including Lucknow,
  Barabanki, Sitapur, Raebareli, Sultanpur, Pratapgarh, Ayodhya and Unnao.
* **Bundeli** is spoken in Bundelkhand: Jhansi, Lalitpur, Jalaun, Hamirpur, Mahoba,
  Banda and Chitrakoot.
* Classmates and hostel-mates from those districts; the Hindi department; NSS or
  similar volunteer groups; family and neighbours.
* For lawyers: ask whether your law faculty runs a legal-aid clinic; young advocates
  at a district bar association; empanelled legal-services volunteers. Ask a
  faculty member to introduce you, because a student's cold message is easy to ignore.

## Message to dialect volunteers (WhatsApp, Hindi)

> नमस्ते [नाम] जी 🙏
> मैं [आपका नाम], लखनऊ विश्वविद्यालय में B.Tech (AI) का छात्र हूँ। मैं उत्तर प्रदेश के लोगों के लिए एक मुफ़्त कानूनी-जानकारी चैटबॉट (न्यायमित्र) बना रहा हूँ, जो हिंदी, अवधी और बुंदेली समझ सके।
> मुझे आपकी मदद चाहिए: एक शीट में कुछ आम सवाल दिए हैं। आपको बस उन्हें अपनी बोली (अवधी / बुंदेली) में वैसे लिखना है जैसे आपके गाँव-घर में लोग बोलते या लिखते हैं। लगभग 30–45 मिनट लगेंगे।
> कृपया किसी का असली नाम, फ़ोन नंबर, पता या अपना कोई निजी मामला न लिखें। जिन वाक्यों में हिंसा या दुखद बातें हैं, उन्हें आप छोड़ सकते हैं।
> अगर आप चाहें तो आपका नाम धन्यवाद-सूची में लिखा जाएगा।
> क्या आप मदद कर सकते हैं? 🙏

## Message to a lawyer or faculty member (email, English)

> Subject: Request for a legal accuracy review of a free legal-information chatbot for Uttar Pradesh
>
> Dear [Name],
>
> I am a final-year B.Tech (AI) student at the University of Lucknow. I am building NyayMitra, a free legal-information chatbot for citizens of Uttar Pradesh (RTI, FIR, tenancy, consumer, cyber, labour, family, women's safety, SC/ST and more). It gives general information, not legal advice, and points users to a lawyer or legal aid.
>
> Its answers come from 174 short passages that I compiled. I am not a lawyer, so before any pilot I want a qualified person to check them. Could you mark each passage, or only those in your area of practice, as accurate, partly accurate or inaccurate, and give the correct provision or source? The 80 passages on women's safety, FIR, SC/ST, cyber and family law matter most; a first pass on those should take a few hours.
>
> If you agree, I will credit you as a legal reviewer (or keep you anonymous, as you prefer). Nothing will be shown to the public as reviewed without your confirmation, and I will send you the corrected text. The sheet is attached; it opens in Excel.
>
> Thank you for considering this.
> [Your name, phone, university]

## Consent and privacy (say this in one minute)

* What you write will be used to test and improve a public-interest chatbot.
* Do not include real names, phone numbers, addresses or anyone's real case.
* Naming credit is optional; your answers are never published with your phone number.
* You can skip any row and stop at any time.
* Reviewers: your corrections are used as written; you can ask for your name to be removed.

## Running a session

1. Send the CSV (UTF-8, opens in Excel or Google Sheets) and the message above.
2. Fill `awadhi_by` / `bundeli_by` / `filled_by` / `reviewer_name` with the person's name.
3. Load the result:

       python evaluation\import_dialects.py path\to\filled_dialect_queries.csv
       python evaluation\import_legal_review.py path\to\filled_legal_review.csv

   The legal-review importer changes no data. It lists every passage marked PARTLY
   or NO with the reviewer's correction, and a person edits the JSON files.
4. Send the safety CSV back to the maintainer; its phrasings become labelled test
   cases in `tests/data/risk_labelled.json`.

## Tracking sheet (keep it simple)

| Person | Role | Dialect / district | Asked on | Sent file | Returned | Notes |
|---|---|---|---|---|---|---|

## Expectations

* Be honest about what the work is for, and do not promise payment or endorsement you
  cannot give.
* A reviewer's agreement to be credited is not an official endorsement by their
  institution.
