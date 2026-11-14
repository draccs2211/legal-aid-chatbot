"""Legal review sheet and its summary tool."""
import csv
import glob
import importlib.util
import json
import os

import pytest

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
spec = importlib.util.spec_from_file_location("import_legal_review", os.path.join(ROOT, "evaluation", "import_legal_review.py"))
rev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rev)

TEMPLATE = os.path.join(ROOT, "evaluation", "templates", "legal_review_template.csv")


def corpus():
    out = {}
    for f in glob.glob(os.path.join(ROOT, "data", "*", "*_chromadb_chunks.json")):
        with open(f, encoding="utf-8") as fh:
            for c in json.load(fh):
                out[c["id"]] = c
    return out


def test_template_has_one_row_per_chunk_with_the_real_text():
    rows = rev.read_rows(TEMPLATE)
    chunks = corpus()
    assert len(rows) == len(chunks) == 174
    assert {r["chunk_id"] for r in rows} == set(chunks)
    assert all(r["text_to_review"] == chunks[r["chunk_id"]]["text"] for r in rows)


def test_template_review_columns_start_empty():
    rows = rev.read_rows(TEMPLATE)
    for col in ("accurate", "what_is_wrong_or_corrected_text", "authoritative_reference",
                "outdated_or_superseded", "reviewer_name", "review_date"):
        assert all(r[col] == "" for r in rows)


def test_highest_risk_domains_come_first():
    rows = rev.read_rows(TEMPLATE)
    priorities = [int(r["priority"]) for r in rows]
    assert priorities == sorted(priorities)
    assert {r["domain"] for r in rows if r["priority"] == "1"} == {"women_safety", "fir", "sc_st", "cyber", "family"}


def test_template_uses_the_router_domain_name_for_cyber():
    assert not any(r["domain"] == "cyber_law" for r in rev.read_rows(TEMPLATE))


def test_template_opens_in_excel_with_a_utf8_bom():
    with open(TEMPLATE, "rb") as f:
        assert f.read(3) == b"\xef\xbb\xbf"


# --- summary tool ------------------------------------------------------------------
def row(cid, domain="fir", accurate="", fix="", reviewer="Adv. A", outdated=""):
    return {"chunk_id": cid, "domain": domain, "accurate": accurate,
            "what_is_wrong_or_corrected_text": fix, "authoritative_reference": "BNSS s.173" if fix else "",
            "reviewer_name": reviewer, "outdated_or_superseded": outdated}


def test_coverage_counts_pending_and_reviewed_per_domain():
    s = rev.summarise([row("a", accurate="YES"), row("b"), row("c", "rti", "no", "wrong fee")])
    assert s["per_domain"]["fir"] == {"total": 2, "YES": 1, "pending": 1}
    assert s["per_domain"]["rti"]["NO"] == 1


def test_partly_and_no_are_listed_with_the_correction():
    s = rev.summarise([row("a", accurate="partly", fix="section number is wrong")])
    assert s["problems"] == [{"chunk_id": "a", "verdict": "PARTLY", "fix": "section number is wrong",
                              "reference": "BNSS s.173", "reviewer": "Adv. A"}]


def test_outdated_chunks_are_collected():
    assert rev.summarise([row("a", accurate="YES", outdated="yes")])["outdated"] == ["a"]


def test_sheet_errors_are_reported_not_silently_accepted():
    s = rev.summarise([row("a", accurate="MAYBE"), row("b", accurate="NO", fix=""), row("c", accurate="YES", reviewer="")])
    text = " ".join(s["errors"])
    assert "'accurate' must be" in text and "nothing says what is wrong" in text and "reviewer_name is missing" in text


def test_summary_text_and_a_full_blank_template(tmp_path):
    s = rev.summarise(rev.read_rows(TEMPLATE))
    assert not s["problems"] and not s["errors"]
    assert all(c["pending"] == c["total"] for c in s["per_domain"].values())
    assert "0/" in rev.format_summary(s)


def test_the_tool_never_modifies_the_data_files():
    import hashlib
    files = sorted(glob.glob(os.path.join(ROOT, "data", "*", "*_chromadb_chunks.json")))
    before = [hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files]
    rev.format_summary(rev.summarise(rev.read_rows(TEMPLATE)))
    assert before == [hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files]
