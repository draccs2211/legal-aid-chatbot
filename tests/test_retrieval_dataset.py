"""Validates evaluation/data/retrieval_labelled.json against the corpus.

These checks catch typos and over-generous labels. They do NOT prove the
labels are right: that needs a second reviewer and, for legal content, a lawyer.
"""
import glob
import json
import os
from collections import Counter

import pytest

from config import DATA_DIR, DOMAINS

PATH = os.path.join(os.path.dirname(__file__), "..", "evaluation", "data", "retrieval_labelled.json")
with open(PATH, encoding="utf-8") as f:
    DATASET = json.load(f)

CORPUS = {}
for _f in glob.glob(os.path.join(DATA_DIR, "*", "*_chromadb_chunks.json")):
    with open(_f, encoding="utf-8") as fh:
        for chunk in json.load(fh):
            CORPUS[chunk["id"]] = chunk["text"]

ANSWERABLE = [d for d in DATASET if d["answerable"]]
UNANSWERABLE = [d for d in DATASET if not d["answerable"]]


def test_query_ids_are_unique_and_fields_present():
    assert len({d["id"] for d in DATASET}) == len(DATASET)
    needed = {"id", "query", "lang", "expected_domain", "answerable", "relevant", "answer_keywords", "qtype"}
    assert all(needed <= set(d) for d in DATASET)


def test_queries_are_unique():
    assert len({d["query"].strip().lower() for d in DATASET}) == len(DATASET)


@pytest.mark.parametrize("item", ANSWERABLE, ids=lambda d: d["id"])
def test_answerable_item_is_well_formed(item):
    assert any(g == 2 for g in item["relevant"].values()), "needs at least one grade-2 chunk"
    assert set(item["relevant"].values()) <= {1, 2}
    assert item["answer_keywords"], "grade-2 chunks must be justified by a keyword"
    assert item["expected_domain"] in DOMAINS


@pytest.mark.parametrize("item", ANSWERABLE, ids=lambda d: d["id"])
def test_every_labelled_chunk_exists(item):
    missing = [c for c in item["relevant"] if c not in CORPUS]
    assert missing == []


@pytest.mark.parametrize("item", ANSWERABLE, ids=lambda d: d["id"])
def test_grade_two_chunks_contain_an_answer_keyword(item):
    for chunk_id, grade in item["relevant"].items():
        if grade == 2:
            text = CORPUS[chunk_id].lower()
            assert any(k.lower() in text for k in item["answer_keywords"]), (
                f"{chunk_id} is labelled grade 2 but contains none of {item['answer_keywords']}"
            )


@pytest.mark.parametrize("item", UNANSWERABLE, ids=lambda d: d["id"])
def test_unanswerable_item_has_no_relevant_chunks(item):
    assert item["relevant"] == {} and item["expected_domain"] == "general"


def test_dataset_is_broad_enough_to_be_useful():
    assert len(ANSWERABLE) >= 60 and len(UNANSWERABLE) >= 10
    assert {d["lang"] for d in DATASET} == {"en", "hinglish", "devanagari"}
    per_domain = Counter(d["expected_domain"] for d in ANSWERABLE)
    assert set(per_domain) == set(DOMAINS)
    assert min(per_domain.values()) >= 3
    assert {"direct", "situation", "cross_domain", "unanswerable"} <= {d["qtype"] for d in DATASET}
