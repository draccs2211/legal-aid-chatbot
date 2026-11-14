"""Dialect variants, CSV importer and templates."""
import csv
import json
import os

import pytest

from evaluation import import_dialects as imp
from evaluation import run_retrieval_eval as R

BASE = os.path.join(os.path.dirname(__file__), "..", "evaluation")
DATASET = [{"id": "a", "query": "orig a", "lang": "hinglish"}, {"id": "b", "query": "orig b", "lang": "hinglish"},
           {"id": "c", "query": "orig c", "lang": "hinglish"}]
TR = {"a": {"en": "A", "hi": "ए", "awa": "अवधी ए", "awa_by": "Ram"},
      "b": {"en": "B", "hi": "बी", "awa": "  "},
      "c": {"en": "C", "hi": "सी", "bns": "बुंदेली सी"}}


def test_dialect_variant_keeps_only_filled_entries_and_labels_the_language():
    out = R.apply_variant(DATASET, TR, "awa")
    assert [d["id"] for d in out] == ["a"] and out[0]["query"] == "अवधी ए" and out[0]["lang"] == "awadhi"
    out = R.apply_variant(DATASET, TR, "bns")
    assert [d["id"] for d in out] == ["c"] and out[0]["lang"] == "bundeli"


def test_original_variant_still_returns_all_parallel_ids():
    assert [d["id"] for d in R.apply_variant(DATASET, TR, "original")] == ["a", "b", "c"]


def test_unreviewed_count_only_applies_to_dialect_variants():
    used = R.apply_variant(DATASET, TR, "bns")
    assert R.unreviewed_count(TR, used, "bns") == 1
    assert R.unreviewed_count(TR, R.apply_variant(DATASET, TR, "awa"), "awa") == 0
    assert R.unreviewed_count(TR, DATASET, "hi") == 0


# --- importer ----------------------------------------------------------------
def test_merge_adds_text_and_reviewer_and_ignores_blank_cells():
    tr = {"q1": {"en": "x", "hi": "y"}, "q2": {"en": "x", "hi": "y"}}
    rows = [{"id": "q1", "awadhi": "अवधी", "awadhi_by": "Sita", "bundeli": "", "bundeli_by": ""},
            {"id": "q2", "awadhi": "", "bundeli": "बुंदेली", "bundeli_by": ""}]
    report = imp.merge_dialects(tr, rows)
    assert tr["q1"]["awa"] == "अवधी" and tr["q1"]["awa_by"] == "Sita" and "bns" not in tr["q1"]
    assert tr["q2"]["bns"] == "बुंदेली" and "bns_by" not in tr["q2"]
    assert report["added"] == {"awa": 1, "bns": 1} and report["no_reviewer"] == 1


def test_merge_reports_unknown_ids_and_keeps_other_fields():
    tr = {"q1": {"en": "x", "hi": "y"}}
    report = imp.merge_dialects(tr, [{"id": "zzz", "awadhi": "t", "awadhi_by": "a"}, {"id": "", "awadhi": "t"}])
    assert report["unknown_ids"] == ["zzz"] and tr == {"q1": {"en": "x", "hi": "y"}}


def test_csv_with_excel_bom_is_read(tmp_path):
    path = tmp_path / "filled.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "awadhi", "awadhi_by"])
        w.writerow(["q1", "हमार मनई", "Sita"])
    rows = imp.read_rows(str(path))
    assert rows[0]["id"] == "q1" and rows[0]["awadhi"] == "हमार मनई"


def test_main_round_trip_preserves_note_and_other_entries(tmp_path):
    jpath = tmp_path / "par.json"
    jpath.write_text(json.dumps({"_note": "keep me", "translations": {"q1": {"en": "x", "hi": "y"}}}), encoding="utf-8")
    cpath = tmp_path / "f.csv"
    cpath.write_text("id,awadhi,awadhi_by\nq1,अवधी,Sita\n", encoding="utf-8")
    imp.main(str(cpath), str(jpath))
    out = json.loads(jpath.read_text(encoding="utf-8"))
    assert out["_note"] == "keep me" and out["translations"]["q1"]["awa"] == "अवधी"


# --- templates -----------------------------------------------------------------
def _read(name):
    return imp.read_rows(os.path.join(BASE, "templates", name))


def test_query_template_covers_every_parallel_entry_with_empty_dialect_cells():
    with open(os.path.join(BASE, "data", "retrieval_parallel.json"), encoding="utf-8") as f:
        ids = set(json.load(f)["translations"])
    rows = _read("dialect_queries_template.csv")
    assert {r["id"] for r in rows} == ids
    assert all(not r["awadhi"] and not r["bundeli"] for r in rows)
    assert all(r["hindi"] and r["english"] for r in rows)


def test_safety_template_has_the_expected_columns_and_sections():
    rows = _read("dialect_safety_template.csv")
    assert len(rows) == 15
    assert {"awadhi_1", "awadhi_3", "bundeli_1", "bundeli_3", "filled_by"} <= set(rows[0])
    assert sum("ordinary legal question" in r["situation_english"] for r in rows) == 4


def test_the_shipped_parallel_file_has_no_unreviewed_dialect_text_yet():
    """Dialect text must come from native speakers, never from the drafter."""
    with open(os.path.join(BASE, "data", "retrieval_parallel.json"), encoding="utf-8") as f:
        tr = json.load(f)["translations"]
    assert not any(("awa" in e or "bns" in e) for e in tr.values())
