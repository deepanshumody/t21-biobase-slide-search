"""
AUDIT: sample of DEV disagreements (reader vs TCGA gold) for a human to label.

    python3 audit.py            # -> audit/disagreements.csv (30 rows)

Fill in the `verdict` column with one of:
  reader_error   the report states the gold value; the reader got it wrong
  label_noise    the report clearly supports the reader; the TCGA label looks wrong
  not_in_report  the report doesn't settle it (e.g. receptor from a separate report)
  unclear        can't tell
The share of label_noise sets how much of the "error" rate is really the gold labels.
Sampling is stratified by fact (round-robin) so HER2 / margins don't crowd out the rest.
"""
import csv
import json
import os
import random
from collections import defaultdict

from calibrate import is_correct
from evaluate import DATA, FACTS, is_holdout
from reader import normalize, read_report

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "audit")
N = 30


def main():
    recs = [json.loads(l) for l in open(DATA)]
    dev = [r for r in recs if not is_holdout(r["id"])]
    by_fact = defaultdict(list)
    for r in dev:
        sheet = read_report(r["report_text"])
        for f in FACTS:
            s, g = sheet[f], r["gold"].get(f)
            if s is not None and g is not None and not is_correct(f, s["value"], g):
                by_fact[f].append((r, f, s))
    rng = random.Random(0)
    for v in by_fact.values():
        rng.shuffle(v)
    rows, i = [], 0
    while len(rows) < N and any(by_fact.values()):          # round-robin across facts
        f = FACTS[i % len(FACTS)]
        if by_fact[f]:
            rows.append(by_fact[f].pop())
        i += 1
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "disagreements.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "fact", "reader_value", "gold_value", "evidence_kind", "evidence", "verdict", "notes"])
        for r, f, s in rows:
            w.writerow([r["id"], f, s["value"], r["gold"][f], s["kind"], s["evidence"], "", ""])
    print(f"wrote {len(rows)} rows -> {path}")
    print({f: sum(1 for x in rows if x[1] == f) for f in FACTS})


if __name__ == "__main__":
    main()
