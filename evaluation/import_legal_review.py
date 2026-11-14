"""Summarise a lawyer's filled-in review sheet.

    python evaluation/import_legal_review.py path/to/filled_legal_review.csv

Reads evaluation/templates/legal_review_template.csv after a lawyer has filled
the `accurate` column (YES / PARTLY / NO) and prints:
  * how much of each domain has been reviewed,
  * every chunk marked PARTLY or NO, with the reviewer's correction,
  * chunks marked outdated.
It changes no data. A person applies corrections to the JSON files, so that
every legal change stays a deliberate, reviewable edit.

Never treat the output as legal advice: it only records what a reviewer said.
"""
import csv
import sys
from collections import Counter, defaultdict

VALID = {"YES", "PARTLY", "NO"}


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalise(value):
    return (value or "").strip().upper()


def summarise(rows):
    """Return a dict: per-domain coverage, problems to fix, and input errors."""
    per_domain = defaultdict(Counter)
    problems, outdated, errors = [], [], []
    for row in rows:
        cid = (row.get("chunk_id") or "").strip()
        if not cid:
            continue
        domain = row.get("domain", "")
        verdict = normalise(row.get("accurate"))
        per_domain[domain]["total"] += 1
        if not verdict:
            per_domain[domain]["pending"] += 1
            continue
        if verdict not in VALID:
            errors.append(f"{cid}: 'accurate' must be YES, PARTLY or NO (got {row.get('accurate')!r})")
            per_domain[domain]["pending"] += 1
            continue
        reviewer = (row.get("reviewer_name") or "").strip()
        if not reviewer:
            errors.append(f"{cid}: reviewer_name is missing")
        per_domain[domain][verdict] += 1
        if verdict in ("PARTLY", "NO"):
            fix = (row.get("what_is_wrong_or_corrected_text") or "").strip()
            if not fix:
                errors.append(f"{cid}: marked {verdict} but nothing says what is wrong")
            problems.append({"chunk_id": cid, "verdict": verdict, "fix": fix,
                             "reference": (row.get("authoritative_reference") or "").strip(),
                             "reviewer": reviewer})
        if normalise(row.get("outdated_or_superseded")) == "YES":
            outdated.append(cid)
    return {"per_domain": {d: dict(c) for d, c in per_domain.items()},
            "problems": problems, "outdated": outdated, "errors": errors}


def format_summary(s):
    out = ["Review coverage by domain (reviewed = YES + PARTLY + NO):"]
    for d, c in sorted(s["per_domain"].items()):
        reviewed = c.get("YES", 0) + c.get("PARTLY", 0) + c.get("NO", 0)
        out.append(f"  {d:<13} {reviewed:>3}/{c['total']:<3} reviewed   YES {c.get('YES', 0)}  PARTLY {c.get('PARTLY', 0)}  NO {c.get('NO', 0)}")
    out.append("")
    out.append(f"Chunks to correct: {len(s['problems'])}")
    for p in s["problems"]:
        out.append(f"  [{p['verdict']}] {p['chunk_id']} (reviewer: {p['reviewer'] or '?'})")
        out.append(f"      {p['fix'] or '(no explanation given)'}")
        if p["reference"]:
            out.append(f"      reference: {p['reference']}")
    if s["outdated"]:
        out.append("")
        out.append("Marked outdated or superseded: " + ", ".join(s["outdated"]))
    if s["errors"]:
        out.append("")
        out.append("Problems in the sheet:")
        out += [f"  - {e}" for e in s["errors"]]
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python evaluation/import_legal_review.py filled_legal_review.csv")
    print(format_summary(summarise(read_rows(sys.argv[1]))))
