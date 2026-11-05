# Collecting Awadhi and Bundeli data

The chatbot cannot be made to handle a language it has never been tested on.
Real phrasings from native speakers are the single most useful input.

## Two templates (in `evaluation/templates/`)

1. `dialect_queries_template.csv`: 55 ordinary legal questions, shown in Hindi
   and English. Write how a person from your area would **actually type or say
   it**, not a formal translation. Fill `awadhi` and/or `bundeli`, and put your
   name in `awadhi_by` / `bundeli_by`. Leave a cell empty to skip.
2. `dialect_safety_template.csv`: 15 situations (8 emergencies, 3 about not
   wanting to live, 4 ordinary legal questions). Give up to 3 different natural
   ways to say each, in each language. Spelling variants and short, broken,
   panicked sentences are welcome. **Some rows are distressing; skip any row.**

## Rules

* Devanagari or Roman script, whichever people really use. Mixed is fine.
* One person per column; the reviewer name matters because numbers from
  unreviewed text are marked provisional.
* **Privacy:** never include real names, phone numbers, addresses or anything
  from a real person's case. If you collect real messages from others, get their
  consent and remove identifying details first.
* Open the CSV in Excel or Google Sheets and save it as **CSV UTF-8**.

## Loading the filled file

    python evaluation\import_dialects.py path\to\filled_dialect_queries.csv
    python evaluation\run_retrieval_eval.py --label awadhi --quiet ^
        --parallel evaluation\data\retrieval_parallel.json --variant awa --modes oracle,unfiltered

Use `--variant bns` for Bundeli. Send the safety template back to the
maintainer; its phrasings become labelled test cases in `tests/data/risk_labelled.json`.
