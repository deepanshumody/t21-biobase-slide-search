"""
EVALUATION against TCGA gold. See concordance_breast_design.md, section 5.

    python3 -I evaluate.py                 # DEV half: all metrics, three readers
    python3 -I evaluate.py --holdout       # HOLDOUT half: run once, at the end
    python3 -I evaluate.py --errors er     # DEV: show disagreements for one fact

Readers compared:
  rules     reader.read_report            (this project)
  naive     reader.read_report(naive=True) first keyword hit, no boilerplate filter, no conflicts
  template  criteria_search/card.py       the synthetic-challenge reader (expected ~0 coverage)
"""
import hashlib
import json
import os
import random
import sys

from criteria import CRITERIA, answers_from_gold, answers_from_sheet
from reader import read_report

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "brca_linked.jsonl")
FACTS = ["er", "pr", "her2", "t_major", "n_major", "nodes_pos", "margin", "histology"]
MENTION = {  # does the text mention the fact at all? (upper bound on coverage)
    "er": r"estrogen|\bER\b", "pr": r"progesterone|\bPR\b", "her2": r"HER-?\s?2|\bneu\b",
    "t_major": r"\bp?T[0-4is]", "n_major": r"\bp?N[0-3X]|lymph node", "nodes_pos": r"lymph node|\bnodes?\b",
    "margin": r"margin", "histology": r"ductal|lobular|mucinous|carcinoma"}


def is_holdout(pid):
    return int(hashlib.md5(pid.encode()).hexdigest(), 16) % 2 == 1


def gold_cmp(fact, gold_v):
    """Gold value in the reader's vocabulary (margin 'close' counts as not positive -> negative)."""
    if fact == "margin" and gold_v == "close":
        return "negative"
    return gold_v


# ---------------------------------------------------------------------------
# Template reader (synthetic challenge) wrapped into a fact sheet.
# ---------------------------------------------------------------------------
def template_sheet(text):
    import sys as _s
    _s.path.insert(0, os.path.join(HERE, "..", "criteria_search"))
    from card import build_card
    from parse import parse_report
    c = build_card(parse_report(text))
    out = {}
    for f, k in (("er", "er"), ("pr", "pr"), ("her2", "her2"), ("t_major", "t_major"),
                 ("n_major", "n_major"), ("nodes_pos", "nodes_pos")):
        out[f] = {"value": c[k], "conf": 1.0, "kind": "template", "evidence": ""} if c.get(k) is not None else None
    out["margin"] = None
    out["histology"] = None
    return out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def fact_metrics(recs, sheets):
    import re
    rows = []
    for f in FACTS:
        known = [r for r in recs if r["gold"].get(f) is not None]
        mention = sum(bool(re.search(MENTION[f], r["report_text"], re.I)) for r in known) / max(1, len(known))
        found = [r for r in known if sheets[r["id"]][f] is not None]
        if f in ("nodes_pos", "n_major"):  # criteria use node-negative vs node-positive only
            correct = sum((sheets[r["id"]][f]["value"] >= 1) == (r["gold"][f] >= 1) for r in found)
        else:
            correct = sum(sheets[r["id"]][f]["value"] == gold_cmp(f, r["gold"][f]) for r in found)
        rows.append((f, len(known), mention, len(found) / max(1, len(known)), correct / max(1, len(found))))
    return rows


def criterion_metrics(recs, answers, gold_answers):
    rows = []
    for cid in CRITERIA:
        scored = [r for r in recs if gold_answers[r["id"]][cid] != "undetermined"]
        pos = {r["id"] for r in scored if gold_answers[r["id"]][cid] == "match"}
        pred = {r["id"] for r in scored if answers[r["id"]][cid]["answer"] == "match"}
        decided = [r for r in scored if answers[r["id"]][cid]["answer"] != "undetermined"]
        dec_ok = sum((answers[r["id"]][cid]["answer"] == "match") == (r["id"] in pos) for r in decided)
        tp = len(pred & pos)
        p = tp / len(pred) if pred else 0
        rc = tp / len(pos) if pos else 0
        f1 = 2 * p * rc / (p + rc) if p + rc else 0
        rows.append((cid, len(scored), len(pos), len(decided) / max(1, len(scored)),
                     dec_ok / max(1, len(decided)), p, rc, f1))
    return rows


def calibration(recs, answers, gold_answers, bins=10):
    """Pool decided answers; confidence vs observed correctness. Returns (ECE, table)."""
    pts = []
    for r in recs:
        for cid in CRITERIA:
            g, a = gold_answers[r["id"]][cid], answers[r["id"]][cid]
            if g == "undetermined" or a["answer"] == "undetermined":
                continue
            pts.append((a["conf"], a["answer"] == g))
    table, ece = [], 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [ok for c, ok in pts if lo < c <= hi or (b == 0 and c == 0)]
        if sel:
            conf = sum(c for c, _ in pts if lo < c <= hi) / len(sel)
            acc = sum(sel) / len(sel)
            ece += len(sel) / len(pts) * abs(acc - conf)
            table.append((f"{lo:.1f}-{hi:.1f}", len(sel), conf, acc))
    return ece, table, len(pts)


def recall_at_budget(recs, answers, gold_answers, ks=(10, 25, 50)):
    """Rank 'match' answers by confidence; share of all true matches in the top K."""
    out = {}
    for cid in CRITERIA:
        pos = {r["id"] for r in recs if gold_answers[r["id"]][cid] == "match"}
        ranked = sorted((r["id"] for r in recs if answers[r["id"]][cid]["answer"] == "match"),
                        key=lambda i: -answers[i][cid]["conf"])
        out[cid] = [len(set(ranked[:k]) & pos) / max(1, min(k, len(pos))) for k in ks]
    return out


# ---------------------------------------------------------------------------
def main(args):
    holdout = "--holdout" in args
    recs = [json.loads(l) for l in open(DATA)]
    recs = [r for r in recs if is_holdout(r["id"]) == holdout]
    split = "HOLDOUT" if holdout else "DEV"
    gold_answers = {r["id"]: answers_from_gold(r["gold"]) for r in recs}

    cal_path = os.path.join(HERE, "calibration.json")
    cal = json.load(open(cal_path)) if os.path.exists(cal_path) else None
    readers = {"rules": lambda t: read_report(t), "naive": lambda t: read_report(t, naive=True),
               "template": template_sheet}
    if cal:
        readers["rules+cal"] = lambda t: read_report(t, calibration=cal)
    results = {}
    for name, fn in readers.items():
        sheets = {r["id"]: fn(r["report_text"]) for r in recs}
        answers = {i: answers_from_sheet(s) for i, s in sheets.items()}
        results[name] = (sheets, answers)

    print(f"===== {split}  n={len(recs)} patients =====")
    print("\nFACTS: coverage (found a value) / accuracy when found   [mention = fact appears in text at all]")
    print(f"{'fact':10} {'n':>5} {'mention':>8} | " + " | ".join(f"{n:^15}" for n in readers))
    rows = {n: fact_metrics(recs, results[n][0]) for n in readers}
    for i, f in enumerate(FACTS):
        _, n, men, _, _ = rows["rules"][i]
        cells = " | ".join(f"{rows[k][i][3]:5.0%} / {rows[k][i][4]:5.0%}  " for k in readers)
        print(f"{f:10} {n:5} {men:8.0%} | {cells}")

    print("\nCRITERIA (patients with known gold): decided = not 'undetermined'; P/R/F1 count undetermined as no flag")
    for name in ("rules", "naive"):  # rules+cal has identical answers, only confidences differ
        print(f"\n  reader: {name}")
        print(f"  {'id':3} {'n':>4} {'pos':>4} {'decided':>8} {'acc|dec':>8} {'P':>6} {'R':>6} {'F1':>6}  criterion")
        crows = criterion_metrics(recs, results[name][1], gold_answers)
        for cid, n, npos, dec, acc, p, rc, f1 in crows:
            print(f"  {cid:3} {n:4} {npos:4} {dec:8.0%} {acc:8.0%} {p:6.2f} {rc:6.2f} {f1:6.2f}  {CRITERIA[cid][0]}")
        print(f"  MEAN F1 = {sum(r[-1] for r in crows) / len(crows):.3f}")

    for name in [n for n in ("rules", "rules+cal") if n in results]:
        ece, table, npts = calibration(recs, results[name][1], gold_answers)
        note = "  (confidences fit on DEV)" if name == "rules+cal" else "  (hand-set confidences)"
        print(f"\nCALIBRATION [{name}]{note}: {npts} decided answers, ECE = {ece:.3f}")
        print(f"  {'bin':9} {'n':>5} {'mean conf':>10} {'accuracy':>9}")
        for b, n, c, a in table:
            print(f"  {b:9} {n:5} {c:10.2f} {a:9.2f}")

    best = "rules+cal" if "rules+cal" in results else "rules"
    print(f"\nRECALL AT REVIEW BUDGET ({best}; top-K by confidence)   K=10 / 25 / 50")
    for cid, vals in recall_at_budget(recs, results[best][1], gold_answers).items():
        print(f"  {cid}  " + "  ".join(f"{v:5.2f}" for v in vals))

    if "--errors" in args and not holdout:
        fact = args[args.index("--errors") + 1]
        sheets = results["rules"][0]
        errs = [r for r in recs if r["gold"].get(fact) is not None and sheets[r["id"]][fact] is not None
                and sheets[r["id"]][fact]["value"] != gold_cmp(fact, r["gold"][fact])]
        random.Random(0).shuffle(errs)
        print(f"\nERRORS for {fact}: {len(errs)} (showing 8)")
        for r in errs[:8]:
            s = sheets[r["id"]][fact]
            print(f"  {r['id']} gold={r['gold'][fact]} read={s['value']} kind={s['kind']} :: {s['evidence'][:200]}")


if __name__ == "__main__":
    main(sys.argv[1:])
