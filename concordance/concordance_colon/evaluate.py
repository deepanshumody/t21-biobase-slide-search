"""
EVALUATION (colon): same metrics and protocol as ../concordance_breast/evaluate.py.

    python3 evaluate.py               # DEV: all metrics (rules / naive / rules+cal)
    python3 evaluate.py --errors lvi  # DEV: disagreements for one fact
    python3 evaluate.py --fit         # fit calibration on DEV -> calibration.json
    python3 evaluate.py --audit       # DEV: 30 stratified disagreements -> audit/disagreements.csv
    python3 evaluate.py --holdout     # HOLDOUT: run once, after freezing
"""
import csv
import hashlib
import json
import os
import random
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from criteria import CRITERIA, answers_from_gold, answers_from_sheet
from evaluation_metrics import calibration_metrics, print_calibration, print_review_budget, review_budget
from reader import read_report

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "coadread_linked.jsonl")
CAL = os.path.join(HERE, "calibration.json")
FACTS = ["t_major", "n_major", "nodes_pos", "mucinous", "lvi", "pni", "residual"]
MENTION = {"t_major": r"\bp?T\s?[0-4]", "n_major": r"\bp?N\s?[0-3]|lymph node", "nodes_pos": r"lymph node|\bnodes?\b",
           "mucinous": r"adenocarcinoma|mucin", "lvi": r"vascular|lymphatic|venous|\bL[01]\b",
           "pni": r"perineural|\bPn[01]\b", "residual": r"margin|\bR[012]\b"}


def is_holdout(pid):
    return int(hashlib.md5(pid.encode()).hexdigest(), 16) % 2 == 1


def is_correct(fact, read_v, gold_v):
    if fact in ("nodes_pos", "n_major"):
        return (read_v >= 1) == (gold_v >= 1)
    return read_v == gold_v


def run(recs, reader):
    sheets = {r["id"]: reader(r["report_text"]) for r in recs}
    answers = {r["id"]: answers_from_sheet(sheets[r["id"]], r["gold"].get("age"),
                                          age_source="TCGA clinical labels") for r in recs}
    return sheets, answers


def fact_rows(recs, sheets):
    out = []
    for f in FACTS:
        known = [r for r in recs if r["gold"].get(f) is not None]
        men = sum(bool(re.search(MENTION[f], r["report_text"], re.I)) for r in known) / max(1, len(known))
        found = [r for r in known if sheets[r["id"]][f] is not None]
        ok = sum(is_correct(f, sheets[r["id"]][f]["value"], r["gold"][f]) for r in found)
        out.append((f, len(known), men, len(found) / max(1, len(known)), ok / max(1, len(found))))
    return out


def crit_rows(recs, answers, gold):
    out = []
    for cid in CRITERIA:
        scored = [r for r in recs if gold[r["id"]][cid] != "undetermined"]
        pos = {r["id"] for r in scored if gold[r["id"]][cid] == "match"}
        pred = {r["id"] for r in scored if answers[r["id"]][cid]["answer"] == "match"}
        dec = [r for r in scored if answers[r["id"]][cid]["answer"] != "undetermined"]
        dok = sum((answers[r["id"]][cid]["answer"] == "match") == (r["id"] in pos) for r in dec)
        tp = len(pred & pos)
        p, rc = (tp / len(pred) if pred else 0), (tp / len(pos) if pos else 0)
        f1 = 2 * p * rc / (p + rc) if p + rc else 0
        out.append((cid, len(scored), len(pos), len(dec) / max(1, len(scored)), dok / max(1, len(dec)), p, rc, f1))
    return out


def ece(recs, answers, gold, bins=10):
    return calibration_metrics(recs, answers, gold, CRITERIA, bins=bins)


def recall_at(recs, answers, gold, ks=(10, 25, 50)):
    rows = review_budget(recs, answers, gold, CRITERIA, ks)
    return {cid: [row["recall"] for row in values] for cid, values in rows.items()}


def fit(dev):
    pair, kind = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in dev:
        s = read_report(r["report_text"])
        for f in FACTS:
            if s[f] is None or r["gold"].get(f) is None:
                continue
            ok = is_correct(f, s[f]["value"], r["gold"][f])
            for tab, key in ((pair, f"{f}|{s[f]['kind']}"), (kind, s[f]["kind"])):
                tab[key][0] += ok
                tab[key][1] += 1
    def sm(c, n):
        return round((c + 1) / (n + 2), 3)
    cal = {"kind": {k: sm(*v) for k, v in kind.items()}, "pair": {k: sm(*v) for k, v in pair.items() if v[1] >= 15},
           "counts": dict(pair)}
    with open(CAL, "w") as handle:
        json.dump(cal, handle, indent=1)
    print(f"wrote {CAL}")
    for k, (c, n) in sorted(pair.items()):
        print(f"  {k:22} n={n:4} acc={c / n:.2f}")


def audit(dev, n=30):
    by = defaultdict(list)
    for r in dev:
        s = read_report(r["report_text"])
        for f in FACTS:
            if s[f] is not None and r["gold"].get(f) is not None and not is_correct(f, s[f]["value"], r["gold"][f]):
                by[f].append((r["id"], f, s[f]["value"], r["gold"][f], s[f]["kind"], s[f]["evidence"]))
    rng = random.Random(0)
    for v in by.values():
        rng.shuffle(v)
    rows, i = [], 0
    while len(rows) < n and any(by.values()):
        f = FACTS[i % len(FACTS)]
        if by[f]:
            rows.append(by[f].pop())
        i += 1
    os.makedirs(os.path.join(HERE, "audit"), exist_ok=True)
    path = os.path.join(HERE, "audit", "disagreements.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "fact", "reader_value", "gold_value", "evidence_kind", "evidence", "verdict", "notes"])
        w.writerows(list(x) + ["", ""] for x in rows)
    print(f"wrote {len(rows)} rows -> {path}")
    return rows


def main(args):
    if "--holdout" in args and ("--fit" in args or "--audit" in args):
        raise SystemExit("Calibration fitting and disagreement audits are DEV only; remove --holdout.")
    with open(DATA) as handle:
        recs = [json.loads(line) for line in handle]
    holdout = "--holdout" in args
    split = [r for r in recs if is_holdout(r["id"]) == holdout]
    if "--fit" in args:
        return fit(split)
    if "--audit" in args:
        return audit(split)
    gold = {r["id"]: answers_from_gold(r["gold"]) for r in split}
    cal = None
    if os.path.exists(CAL):
        with open(CAL) as handle:
            cal = json.load(handle)
    readers = {"rules": lambda t: read_report(t), "naive": lambda t: read_report(t, naive=True)}
    if cal:
        readers["rules+cal"] = lambda t: read_report(t, calibration=cal)
    res = {k: run(split, fn) for k, fn in readers.items()}

    print(f"===== {'HOLDOUT' if holdout else 'DEV'}  n={len(split)} =====")
    print("\nFACTS  coverage / accuracy-when-found")
    rows = {k: fact_rows(split, res[k][0]) for k in ("rules", "naive")}
    print(f"{'fact':10} {'n':>4} {'mention':>8} | {'rules':^15} | {'naive':^15}")
    for i, f in enumerate(FACTS):
        _, n, men, _, _ = rows["rules"][i]
        print(f"{f:10} {n:4} {men:8.0%} | " + " | ".join(f"{rows[k][i][3]:5.0%} / {rows[k][i][4]:5.0%}  " for k in rows))
    for name in ("rules", "naive"):
        cr = crit_rows(split, res[name][1], gold)
        print(f"\nCRITERIA [{name}]\n  {'id':3} {'n':>4} {'pos':>4} {'decided':>8} {'acc|dec':>8} {'P':>6} {'R':>6} {'F1':>6}")
        for cid, n, npos, d, a, p, rc, f1 in cr:
            print(f"  {cid:3} {n:4} {npos:4} {d:8.0%} {a:8.0%} {p:6.2f} {rc:6.2f} {f1:6.2f}  {CRITERIA[cid][0]}")
        print(f"  MEAN F1 = {sum(x[-1] for x in cr) / len(cr):.3f}")
    for name in [k for k in ("rules", "rules+cal") if k in res]:
        print_calibration(split, res[name][1], gold, CRITERIA, name)
    for name in ("rules", "naive", "rules+cal"):
        if name in res:
            print_review_budget(split, res[name][1], gold, CRITERIA, name)
    if "--errors" in args and not holdout:
        f = args[args.index("--errors") + 1]
        s = res["rules"][0]
        errs = [r for r in split if s[r["id"]][f] is not None and r["gold"].get(f) is not None
                and not is_correct(f, s[r["id"]][f]["value"], r["gold"][f])]
        print(f"\nERRORS {f}: {len(errs)}")
        for r in errs[:10]:
            x = s[r["id"]][f]
            print(f"  {r['id']} gold={r['gold'][f]} read={x['value']} {x['kind']} :: {x['evidence'][:170]}")


if __name__ == "__main__":
    main(sys.argv[1:])
