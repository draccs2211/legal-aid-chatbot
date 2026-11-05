"""Sanity checks for evaluation/data/retrieval_parallel.json."""
import json
import os
import re

import pytest

BASE = os.path.join(os.path.dirname(__file__), "..", "evaluation", "data")
with open(os.path.join(BASE, "retrieval_labelled.json"), encoding="utf-8") as f:
    MAIN = {d["id"]: d for d in json.load(f)}
with open(os.path.join(BASE, "retrieval_parallel.json"), encoding="utf-8") as f:
    PAR = json.load(f)["translations"]

DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def test_every_parallel_id_exists_and_is_answerable():
    assert set(PAR) <= set(MAIN)
    assert all(MAIN[i]["answerable"] for i in PAR)


def test_covers_every_non_english_answerable_query():
    wanted = {i for i, d in MAIN.items() if d["answerable"] and d["lang"] in ("hinglish", "devanagari")}
    assert set(PAR) == wanted


@pytest.mark.parametrize("qid", sorted(PAR))
def test_entry_is_well_formed(qid):
    entry = PAR[qid]
    assert entry["en"].strip() and entry["hi"].strip()
    assert not DEVANAGARI.search(entry["en"]), "the English variant must not contain Devanagari"
    assert DEVANAGARI.search(entry["hi"]), "the Hindi variant must be in Devanagari"


def test_variants_differ_from_each_other():
    assert all(e["en"] != e["hi"] for e in PAR.values())
