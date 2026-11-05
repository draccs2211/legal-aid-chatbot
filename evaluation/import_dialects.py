"""Merge dialect phrasings from a filled-in CSV into retrieval_parallel.json.

    python evaluation/import_dialects.py path\\to\\filled_template.csv

CSV columns (see evaluation/templates/dialect_queries_template.csv):
    id, awadhi, awadhi_by, bundeli, bundeli_by   (other columns are ignored)

Only non-empty cells are merged. The `_by` cell records who wrote or reviewed
that phrasing; runs on entries without it print a warning. The CSV is read as
UTF-8 with or without a BOM (Excel on Windows adds one).
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PARALLEL = os.path.join(HERE, "data", "retrieval_parallel.json")
FIELDS = {"awa": ("awadhi", "awadhi_by"), "bns": ("bundeli", "bundeli_by")}


def merge_dialects(translations, rows):
    """Merge CSV rows into `translations` (modified in place). Returns a report."""
    report = {"added": {"awa": 0, "bns": 0}, "unknown_ids": [], "no_reviewer": 0}
    for row in rows:
        qid = (row.get("id") or "").strip()
        if not qid:
            continue
        if qid not in translations:
            report["unknown_ids"].append(qid)
            continue
        for key, (text_col, by_col) in FIELDS.items():
            text = (row.get(text_col) or "").strip()
            if not text:
                continue
            translations[qid][key] = text
            reviewer = (row.get(by_col) or "").strip()
            if reviewer:
                translations[qid][key + "_by"] = reviewer
            else:
                translations[qid].pop(key + "_by", None)
                report["no_reviewer"] += 1
            report["added"][key] += 1
    return report


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main(csv_path, json_path=PARALLEL):
    with open(json_path, encoding="utf-8") as f:
        payload = json.load(f)
    report = merge_dialects(payload["translations"], read_rows(csv_path))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"Added Awadhi: {report['added']['awa']}, Bundeli: {report['added']['bns']}")
    if report["no_reviewer"]:
        print(f"WARNING: {report['no_reviewer']} phrasings have no reviewer name; results will be marked provisional.")
    if report["unknown_ids"]:
        print(f"WARNING: ignored unknown ids: {report['unknown_ids']}")
    return report


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python evaluation/import_dialects.py filled_template.csv")
    main(sys.argv[1])
