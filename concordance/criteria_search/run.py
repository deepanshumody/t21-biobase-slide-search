"""
SUBMISSION (test). See criteria_search_design.md section 7.

    python3 run.py                      # -> submission.json
    python3 run.py out.json             # custom output path

Also prints two safety checks (they never change the submission):
  DRIFT CHECK  : field wordings seen in test but never in train.
  CROSS CHECK  : re-answers every criterion from the prose only (prose_card.py) and
                 lists reports where prose and template disagree -> cross_check.json.
                 Most disagreements are prose misreads; review them for template misparses.
"""
import json
import re
import sys
from collections import defaultdict

from parse import load_jsonl, parse_report
from pipeline import cards_for, match_all
from prose_card import build_prose_card
from rules import RULES

DATA = "pack_reports/"


def shape(value):
    """Wording 'shape' for drift checks: digits -> '#'."""
    return re.sub(r"\d+(?:\.\d+)?", "#", value)


def drift_check(train, test):
    seen = defaultdict(set)
    for r in train:
        p = parse_report(r["report_text"])
        for k, v in p["fields"].items():
            seen[k].add(shape(v))
    new = defaultdict(set)
    for r in test:
        p = parse_report(r["report_text"])
        if p["organ"] is None:
            new["<organ unknown>"].add(p["specimen"] or "<no SPECIMEN line>")
        for k, v in p["fields"].items():
            if k in ("Specimen", "Tumor site"):  # site/specimen variety is harmless
                continue
            if shape(v) not in seen[k]:
                new[k].add(shape(v))
    print("\nDRIFT CHECK (test wordings never seen in train):")
    if not new:
        print("  none")
    for k, vals in sorted(new.items()):
        for v in sorted(vals)[:5]:
            print(f"  {k}: {v[:140]}")


def cross_check(test, template_cards, preds, out_path="cross_check.json"):
    """Second opinion: same rules on prose-built cards. Template answers stay in the submission."""
    prose_cards = {r["id"]: build_prose_card(r["report_text"], use_header=True, infer_morphology=True)
                   for r in test}
    report = {}
    for cid, rule in RULES.items():
        tmpl = set(preds[cid])
        prose = {rid for rid, c in prose_cards.items() if rule(c)}
        rows = []
        for rid, side in [(i, "template_only") for i in sorted(tmpl - prose)] + \
                         [(i, "prose_only") for i in sorted(prose - tmpl)]:
            t, p = template_cards[rid], prose_cards[rid]
            diffs = {k: [t[k], p[k]] for k in p if k in t and t[k] != p[k]
                     and k not in ("histology", "margins", "depth", "extent", "t_cat", "n_cat")}
            rows.append({"id": rid, "side": side, "template_vs_prose": diffs})
        if rows:
            report[cid] = rows
    with open(out_path, "w") as f:
        json.dump(report, f, indent=1, default=str)
    total = sum(len(v) for v in report.values())
    print(f"\nCROSS CHECK (prose vs template on test): {total} disagreements -> {out_path}")
    for cid, rows in report.items():
        sides = defaultdict(int)
        for r in rows:
            sides[r["side"]] += 1
        print(f"  {cid}: {dict(sides)}")


def main(out_path):
    test = load_jsonl(DATA + "test.jsonl")
    cards = cards_for(test)
    preds = match_all(cards)
    submission = {cid: {"ids": ids, "count": len(ids)} for cid, ids in preds.items()}
    with open(out_path, "w") as f:
        json.dump(submission, f, indent=1)
    print(f"wrote {out_path}")
    print("counts:", {cid: len(ids) for cid, ids in preds.items()})
    drift_check(load_jsonl(DATA + "train.jsonl"), test)
    cross_check(test, cards, preds)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "submission.json")
