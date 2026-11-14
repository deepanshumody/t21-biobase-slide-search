"""
VALIDATION LOOP (train only). See criteria_search_design.md section 6.

    python3 evaluate.py            # parser health + scores; dumps errors for any F1 < 1
    python3 evaluate.py c05 c26    # also dump errors for these criteria

Improve loop: lowest F1 -> read its FP/FN dump -> fix card.py (misread value)
or rules.py (wrong interpretation) -> rerun.
"""
import json
import sys
from collections import Counter

from parse import load_jsonl, parse_report
from pipeline import cards_for, match_all

DATA = "pack_reports/"
MAX_DUMP = 8  # errors shown per criterion

# Card keys worth showing in an error dump, per organ.
SHOW = {
    "breast": ["er", "pr", "her2", "nodes_pos", "lvi", "size_mm", "margin_neg", "margin_mm",
               "multifocal", "age_band", "nottingham"],
    "colon": ["histology", "t_cat", "n_cat", "nodes_pos", "lvi", "pni", "deposits", "size_mm", "age_band"],
    "lung": ["histology", "vpi", "nodes_pos", "margins", "sex", "year"],
    "prostate": ["grade_group", "svi", "epe", "margins", "pni", "lvi"],
    "stomach": ["histology", "her2", "t_cat", "nodes_pos"],
    "kidney": ["histology", "isup", "sarcomatoid", "extent"],
    "skin": ["histology", "scc_grade", "margins"],
}


def prf(pred, gold):
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return tp, p, r, f


def parser_health(reports):
    """Compare parse.py against the train labels."""
    organ_ok = fields_ok = 0
    diffs = Counter()
    for r in reports:
        p = parse_report(r["report_text"])
        organ_ok += p["organ"] == r["labels"]["organ"]
        gold = r["labels"]["diagnosis"]
        if p["fields"] == gold:
            fields_ok += 1
        else:
            for k in set(p["fields"]) | set(gold):
                if p["fields"].get(k) != gold.get(k):
                    diffs[k] += 1
    n = len(reports)
    print(f"PARSER  organ {organ_ok}/{n}   diagnosis fields exact {fields_ok}/{n}")
    for k, v in diffs.most_common(5):
        print(f"   mismatched field: {k!r} x{v}")


def main(focus):
    reports = load_jsonl(DATA + "train.jsonl")
    answers = json.load(open(DATA + "criteria_train_answers.json"))
    criteria = {c["id"]: c["text"] for c in json.load(open(DATA + "criteria.json"))}

    parser_health(reports)

    cards = cards_for(reports)
    preds = match_all(cards)

    print(f"\n{'id':4} {'TP':>4} {'FP':>4} {'FN':>4} {'P':>6} {'R':>6} {'F1':>6}  criterion")
    f1s, to_dump = [], []
    for cid, text in criteria.items():
        pred, gold = set(preds.get(cid, [])), set(answers.get(cid, []))
        tp, p, r, f = prf(pred, gold)
        f1s.append(f)
        print(f"{cid:4} {tp:4} {len(pred)-tp:4} {len(gold)-tp:4} {p:6.3f} {r:6.3f} {f:6.3f}  {text[:70]}")
        if f < 1 or cid in focus:
            to_dump.append((cid, pred - gold, gold - pred))
    print(f"\nMEAN F1 = {sum(f1s)/len(f1s):.4f}   (baseline 0.27)")

    # ---- error dump: why did each FP / FN happen? --------------------------
    for cid, fps, fns in to_dump:
        print(f"\n=== {cid}: {criteria[cid]}")
        for label, ids in (("FP", fps), ("FN", fns)):
            for rid in sorted(ids)[:MAX_DUMP]:
                c = cards[rid]
                facts = {k: c.get(k) for k in SHOW.get(c["organ"], [])}
                print(f"  {label} {rid} [{c['organ']}] {facts}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
