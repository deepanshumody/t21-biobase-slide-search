"""
EXPERIMENT RUNNER: template reader vs prose-only reader, using the same rules.

    python3 prose_experiment.py              # dev diagnostics + per-criterion table (dev only)
    python3 prose_experiment.py --holdout    # final scores on the untouched holdout half
    python3 prose_experiment.py c04 c26      # dump dev errors for these criteria

Honest-evaluation setup:
  train is split by md5(id) into DEV (even) and HOLDOUT (odd).
  prose_card.py is developed by looking at DEV only; HOLDOUT is scored at the end.
"""
import hashlib
import json
import sys

from card import build_card
from evaluate import prf
from parse import load_jsonl, parse_report
from prose_card import build_prose_card
from rules import RULES

DATA = "pack_reports/"
FIELD_KEYS = ["organ", "histology", "nodes_pos", "n_major", "t_major", "size_mm", "lvi", "pni", "deposits",
              "vpi", "svi", "sarcomatoid", "epe", "multifocal", "nottingham", "grade_group", "isup",
              "scc_grade", "er", "pr", "her2", "margin_neg", "margin_mm"]


def is_holdout(rid):
    return int(hashlib.md5(rid.encode()).hexdigest(), 16) % 2 == 1


def score(cards, answers, ids):
    out = {}
    for cid, rule in RULES.items():
        pred = {rid for rid in ids if rule(cards[rid])}
        gold = set(answers[cid]) & ids
        out[cid] = prf(pred, gold)[3], pred - gold, gold - pred
    return out


def field_agreement(block, prose, ids):
    """How often the prose reader produces the same fact as the template reader (when the template has one)."""
    print("\nFIELD AGREEMENT prose vs template (dev, where template value is not None/''):")
    for k in FIELD_KEYS:
        pairs = [(block[i][k], prose[i][k]) for i in ids if block[i][k] not in (None, "")]
        if not pairs:
            continue
        if k == "histology":
            agree = sum(b.split(",")[0] in p for b, p in pairs)
        elif k == "t_major":
            agree = sum((b == 4) == (p == 4) for b, p in pairs)
        else:
            agree = sum(b == p for b, p in pairs)
        print(f"  {k:12} {agree / len(pairs):6.3f}  (n={len(pairs)})")


def main(args):
    holdout = "--holdout" in args
    focus = {a for a in args if a.startswith("c")}
    reports = load_jsonl(DATA + "train.jsonl")
    answers = json.load(open(DATA + "criteria_train_answers.json"))
    texts = {r["id"]: r["report_text"] for r in reports}
    ids = {rid for rid in texts if is_holdout(rid) == holdout}
    split = "HOLDOUT" if holdout else "DEV"

    block = {rid: build_card(parse_report(texts[rid])) for rid in ids}
    prose_a = {rid: build_prose_card(texts[rid], use_header=True) for rid in ids}
    prose_b = {rid: build_prose_card(texts[rid], use_header=False) for rid in ids}
    prose_m = {rid: build_prose_card(texts[rid], use_header=True, infer_morphology=True) for rid in ids}

    if not holdout:
        field_agreement(block, prose_a, ids)

    s_block, s_a, s_b, s_m = (score(c, answers, ids) for c in (block, prose_a, prose_b, prose_m))
    print(f"\n{split} (n={len(ids)})   F1 per criterion")
    print(f"{'id':4} {'template':>9} {'prose+hdr':>10} {'+morphology':>12} {'prose only':>11}")
    for cid in RULES:
        print(f"{cid:4} {s_block[cid][0]:9.3f} {s_a[cid][0]:10.3f} {s_m[cid][0]:12.3f} {s_b[cid][0]:11.3f}")
    mean = lambda s: sum(v[0] for v in s.values()) / len(s)
    print(f"MEAN {mean(s_block):9.4f} {mean(s_a):10.4f} {mean(s_m):12.4f} {mean(s_b):11.4f}")

    if holdout:
        return
    for cid in sorted(focus):
        _, fps, fns = s_a[cid]
        print(f"\n=== {cid} (prose+hdr) FP={len(fps)} FN={len(fns)}")
        for label, group in (("FP", fps), ("FN", fns)):
            for rid in sorted(group)[:4]:
                diff = {k: (block[rid][k], prose_a[rid][k]) for k in FIELD_KEYS if block[rid][k] != prose_a[rid][k]}
                print(f"  {label} {rid} template->prose diffs: {diff}")


if __name__ == "__main__":
    main(sys.argv[1:])
