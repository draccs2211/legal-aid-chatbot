"""Print risk-classifier metrics on tests/data/risk_labelled.json.

Run from the repo root:  python scripts/eval_risk.py

IMPORTANT: the dataset was written by the same person who wrote the rules and
the rules were tuned while looking at it, so these numbers are optimistic. Use
this as a regression check, not as an accuracy claim. A held-out set written
(or reviewed) by someone else is still needed.
"""
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "backend"))

from safety import ALERT_LEVELS, assess_risk  # noqa: E402

LEVELS = ["none", "possible", "emergency", "self_harm"]


def main():
    with open(os.path.join(ROOT, "tests", "data", "risk_labelled.json"), encoding="utf-8") as f:
        data = json.load(f)

    confusion = Counter()
    per_lang = defaultdict(lambda: [0, 0])
    gaps = []
    for d in data:
        got = assess_risk(d["text"])["level"]
        confusion[(d["label"], got)] += 1
        ok = got == d["label"]
        per_lang[d["lang"]][0] += ok
        per_lang[d["lang"]][1] += 1
        if not ok:
            gaps.append((d, got))

    print(f"{len(data)} labelled messages\n")
    print("Confusion matrix (rows = label, columns = predicted)")
    print(" " * 12 + "".join(f"{lv:>11}" for lv in LEVELS))
    for lab in LEVELS:
        print(f"{lab:<12}" + "".join(f"{confusion[(lab, lv)]:>11}" for lv in LEVELS))

    alert_total = sum(1 for d in data if d["label"] in ALERT_LEVELS)
    alert_hit = sum(n for (lab, got), n in confusion.items() if lab in ALERT_LEVELS and got in ALERT_LEVELS)
    predicted_alert = sum(n for (lab, got), n in confusion.items() if got in ALERT_LEVELS)
    true_alert = sum(n for (lab, got), n in confusion.items() if got in ALERT_LEVELS and lab in ALERT_LEVELS)
    print(f"\nAlert recall    (emergency/self_harm caught): {alert_hit}/{alert_total}")
    print(f"Alert precision (alerts that were real):      {true_alert}/{predicted_alert}")

    print("\nExact-level accuracy by language")
    for lang, (ok, total) in sorted(per_lang.items()):
        print(f"  {lang:<11} {ok}/{total}")

    print("\nMismatches")
    for d, got in gaps:
        tag = "known gap" if d.get("known_gap") else "UNEXPECTED"
        print(f"  [{tag}] label={d['label']} got={got} | {d['text']}")
        if d.get("note"):
            print(f"      note: {d['note']}")


if __name__ == "__main__":
    main()
