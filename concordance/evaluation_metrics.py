"""Shared cohort-search metrics, with explicit denominators and missing-gold handling."""
import math


def _confidence(answer):
    value = answer["conf"]
    if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Decided answers require a finite confidence between 0 and 1")
    return value


def review_budget(recs, answers, gold, criteria, ks=(10, 25, 50)):
    """Precision and recall among candidates with known criterion-level gold.

    Unknown-gold candidates are excluded before ranking and counted explicitly.
    Precision uses the actual number reviewed, which may be smaller than K.
    Recall uses every known positive, including patients the reader missed or abstained on.
    Ties are broken by patient ID, independently of input order or gold values.
    Undefined ratios are None, not a perfect score or a measured zero.
    """
    ks = tuple(ks)
    if any(isinstance(k, bool) or not isinstance(k, int) or k <= 0 for k in ks):
        raise ValueError("Review budgets must be positive integers")
    ids = [r["id"] for r in recs]
    if len(ids) != len(set(ids)):
        raise ValueError("Review-budget evaluation requires unique patient IDs")
    result = {}
    for cid in criteria:
        known = {rid for rid in ids if gold[rid][cid] != "undetermined"}
        positives = {rid for rid in known if gold[rid][cid] == "match"}
        candidates = [rid for rid in ids if answers[rid][cid]["answer"] == "match"]
        ranked = sorted(
            (rid for rid in candidates if rid in known),
            key=lambda rid: (-_confidence(answers[rid][cid]), rid),
        )
        rows = []
        for k in ks:
            reviewed = ranked[:k]
            hits = len(set(reviewed) & positives)
            rows.append({
                "budget": k,
                "reviewed": len(reviewed),
                "true_positives": hits,
                "total_positives": len(positives),
                "precision": hits / len(reviewed) if reviewed else None,
                "recall": hits / len(positives) if positives else None,
                "excluded_unknown_gold": len(candidates) - len(ranked),
            })
        result[cid] = rows
    return result


def calibration_metrics(recs, answers, gold, criteria, bins=10, decision=None):
    """Calibration of decision correctness, optionally restricted to match or no_match.

    For match decisions, observed correctness is shortlist precision.
    For no_match decisions, it is the correctness of exclusions.
    A pooled result must not be interpreted as match-only precision.
    """
    if decision not in (None, "match", "no_match"):
        raise ValueError("decision must be match, no_match, or None")
    if isinstance(bins, bool) or not isinstance(bins, int) or bins <= 0:
        raise ValueError("bins must be a positive integer")
    points = []
    for record in recs:
        rid = record["id"]
        for cid in criteria:
            answer, truth = answers[rid][cid], gold[rid][cid]
            if truth == "undetermined" or answer["answer"] == "undetermined":
                continue
            if decision is not None and answer["answer"] != decision:
                continue
            points.append((_confidence(answer), answer["answer"] == truth))
    if not points:
        return None, [], 0
    table, ece = [], 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        selected = [(c, ok) for c, ok in points if lo < c <= hi or (b == 0 and c == 0)]
        if selected:
            confidence = sum(c for c, _ in selected) / len(selected)
            accuracy = sum(ok for _, ok in selected) / len(selected)
            ece += len(selected) / len(points) * abs(accuracy - confidence)
            table.append((f"{lo:.1f}-{hi:.1f}", len(selected), confidence, accuracy))
    return ece, table, len(points)


def format_rate(value):
    return "n/a" if value is None else f"{value:.3f}"


def print_calibration(recs, answers, gold, criteria, reader_name):
    for decision, label in (
        (None, "all decided; matches and exclusions pooled"),
        ("match", "match decisions only; observed accuracy is precision"),
        ("no_match", "no_match decisions only; observed accuracy is exclusion correctness"),
    ):
        ece, table, count = calibration_metrics(recs, answers, gold, criteria, decision=decision)
        print(f"\nCALIBRATION [{reader_name}] {label}: n={count}, ECE={format_rate(ece)}")
        print(f"  {'bin':9} {'n':>5} {'mean conf':>10} {'accuracy':>9}")
        for bin_name, n, confidence, accuracy in table:
            print(f"  {bin_name:9} {n:5} {confidence:10.3f} {accuracy:9.3f}")


def print_review_budget(recs, answers, gold, criteria, reader_name):
    print(f"\nREVIEW BUDGET [{reader_name}]; confidence descending, patient ID breaks ties")
    print("  Known-gold candidates only; excluded = candidates without a known criterion label.")
    print("  Precision = hits/reviewed; recall = hits/all known positives; n/a = undefined.")
    print(f"  {'id':3} {'K':>4} {'reviewed':>8} {'hits':>5} {'positives':>9} "
          f"{'P@K':>7} {'R@K':>7} {'excluded':>8}")
    for cid, rows in review_budget(recs, answers, gold, criteria).items():
        for row in rows:
            print(f"  {cid:3} {row['budget']:4} {row['reviewed']:8} {row['true_positives']:5} "
                  f"{row['total_positives']:9} {format_rate(row['precision']):>7} "
                  f"{format_rate(row['recall']):>7} {row['excluded_unknown_gold']:8}")
