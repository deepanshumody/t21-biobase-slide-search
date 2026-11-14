"""
CALIBRATION: replace hand-set confidences with accuracies measured on DEV.

    python3 calibrate.py        # fits on DEV only -> calibration.json

For every (fact, evidence kind) pair, e.g. ("her2", "synoptic"), it counts how often the
reader's value matched TCGA gold on the DEV half. That accuracy becomes the confidence.
  - Laplace smoothing (correct + 1) / (n + 2), so a group of 3 doesn't get 100%.
  - Groups with fewer than MIN_N facts fall back to the kind-level accuracy across all facts.
reader.read_report(text, calibration=table) then uses these numbers. evaluate.py
reports ECE on HOLDOUT, which the fit never saw.
"""
import json
import os
from collections import defaultdict

from evaluate import DATA, FACTS, gold_cmp, is_holdout
from reader import read_report

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "calibration.json")
MIN_N = 15


def is_correct(fact, read_v, gold_v):
    if fact in ("nodes_pos", "n_major"):  # criteria only use node-negative vs node-positive
        return (read_v >= 1) == (gold_v >= 1)
    return read_v == gold_cmp(fact, gold_v)


def main():
    recs = [json.loads(l) for l in open(DATA)]
    dev = [r for r in recs if not is_holdout(r["id"])]
    by_pair, by_kind = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in dev:
        sheet = read_report(r["report_text"])
        for f in FACTS:
            s, g = sheet[f], r["gold"].get(f)
            if s is None or g is None:
                continue
            ok = is_correct(f, s["value"], g)
            for table, key in ((by_pair, f"{f}|{s['kind']}"), (by_kind, s["kind"])):
                table[key][0] += ok
                table[key][1] += 1
    smooth = lambda c, n: round((c + 1) / (n + 2), 3)
    cal = {"kind": {k: smooth(c, n) for k, (c, n) in by_kind.items()},
           "pair": {k: smooth(c, n) for k, (c, n) in by_pair.items() if n >= MIN_N},
           "counts": {k: v for k, v in by_pair.items()}}
    json.dump(cal, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}  (fit on DEV, n={len(dev)})")
    print(f"{'fact|kind':24} {'n':>5} {'accuracy':>9}")
    for k, (c, n) in sorted(by_pair.items()):
        used = cal["pair"].get(k, f"-> kind {cal['kind'][k.split('|')[1]]}")
        print(f"{k:24} {n:5} {c / n:9.2f}   conf used: {used}")


if __name__ == "__main__":
    main()
