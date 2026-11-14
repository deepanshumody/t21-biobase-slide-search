"""Search a single-organ report cohort and export decisions with their evidence.

Example: python3 search.py --organ colon --criterion C7 \
    --input examples/colon_reports.jsonl --output /tmp/colon_candidates.json
"""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(organ, name):
    path = HERE / f"concordance_{organ}" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"cohort_{organ}_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def search(records, organ, criterion, limit=10, calibration=None):
    if organ not in ("breast", "colon"):
        raise ValueError("organ must be breast or colon")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    reader, rules = load_module(organ, "reader"), load_module(organ, "criteria")
    if criterion not in rules.CRITERIA:
        raise ValueError(f"Unknown criterion {criterion!r}; choose from {', '.join(rules.CRITERIA)}")
    results, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each input line must be a JSON object")
        rid, text = record.get("id"), record.get("report_text")
        if not isinstance(rid, str) or not rid.strip() or rid in seen:
            raise ValueError("Every report needs a nonempty, unique string id")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{rid}: report_text must be a nonempty string")
        if record.get("organ", organ) != organ:
            raise ValueError(f"{rid}: organ does not match the selected cohort")
        seen.add(rid)
        sheet = reader.read_report(text, calibration=calibration)
        if organ == "colon":
            clinical = record.get("clinical", {})
            if clinical is None:
                clinical = {}
            if not isinstance(clinical, dict):
                raise ValueError(f"{rid}: clinical must be an object")
            age = clinical.get("age")
            if age is not None and (isinstance(age, bool) or not isinstance(age, int) or age < 0):
                raise ValueError(f"{rid}: clinical.age must be a nonnegative integer")
            decision = rules.answers_from_sheet(sheet, age=age, age_source="clinical.age")[criterion]
        else:
            decision = rules.answers_from_sheet(sheet)[criterion]
        results.append({"id": rid, **decision, "facts": sheet})
    status_order = {"match": 0, "undetermined": 1, "no_match": 2}
    results.sort(key=lambda row: (status_order[row["answer"]], -(row["conf"] or 0), row["id"]))
    counts = {status: sum(row["answer"] == status for row in results) for status in status_order}
    return {
        "organ": organ,
        "criterion": {"id": criterion, "description": rules.CRITERIA[criterion][0]},
        "confidence_source": "supplied calibration" if calibration else "hand-set evidence confidence",
        "counts": counts,
        "shortlist_ids": [row["id"] for row in results if row["answer"] == "match"][:limit],
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organ", required=True, choices=("breast", "colon"))
    parser.add_argument("--criterion", required=True, help="B1-B8 for breast or C1-C8 for colon")
    parser.add_argument("--input", required=True, type=Path, help="JSONL reports from the selected organ")
    parser.add_argument("--output", required=True, type=Path, help="JSON decisions and evidence")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of shortlisted matches")
    parser.add_argument("--calibration", type=Path, help="Optional frozen calibration table")
    args = parser.parse_args()
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("output must differ from input")
        if args.calibration and args.calibration.resolve() == args.output.resolve():
            raise ValueError("output must differ from calibration")
        with args.input.open() as handle:
            records = [json.loads(line) for line in handle if line.strip()]
        calibration = json.loads(args.calibration.read_text()) if args.calibration else None
        result = search(records, args.organ, args.criterion, args.limit, calibration)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    print(f"{args.criterion}: {result['counts']}; shortlisted={len(result['shortlist_ids'])}")
    print(f"Wrote decisions, missing facts, and supporting evidence to {args.output}")


if __name__ == "__main__":
    main()
