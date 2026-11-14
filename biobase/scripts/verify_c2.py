#!/usr/bin/env python3
"""Verify C2 hashes, baseline parity, and submission coverage."""
import csv
import hashlib
import json
from pathlib import Path

from c2_retrieval import validate_submission


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "output/c2"
    hashes = json.loads((output / "artifact_hashes.json").read_text())
    skipped = []
    for relative, expected_hash in hashes.items():
        path = root / relative
        if not path.exists() and relative.startswith(("pack_slides/", "tilepack/")):
            skipped.append(relative)
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"Hash mismatch: {relative}")
    with (root / "output/c1_improved/submission_organ.csv").open(newline="") as stream:
        expected = {row["slide_id"] for row in csv.DictReader(stream)}
    with (output / "submission_similar.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["query_slide_id", "rank", "result_slide_id"]:
            raise ValueError("Incorrect submission columns")
        rows = list(reader)
    manifest = root / "pack_slides/slides_manifest.json"
    valid_ids = ({row["id"] for row in json.loads(manifest.read_text())["slides"]} if manifest.exists()
                 else {row["result_slide_id"] for row in rows if row["result_slide_id"]})
    validate_submission(rows, expected, valid_ids)
    with (output / "baseline_similar.csv").open(newline="") as stream:
        baseline = list(csv.DictReader(stream))
    with (root / "output/c1/baseline/baseline_similar.csv").open(newline="") as stream:
        archived = list(csv.DictReader(stream))
    if baseline != archived:
        raise ValueError("Regenerated baseline differs from the supplied baseline")
    with (output / "retrieval_evidence.csv").open(newline="") as stream:
        evidence = list(csv.DictReader(stream))
    if [{key: row[key] for key in rows[0]} for row in evidence] != rows:
        raise ValueError("Retrieval evidence does not match submission")
    print(f"Verified {len(hashes) - len(skipped)} hashes, {len(expected)} queries, {len(rows)} results, and exact baseline parity.")
    if skipped:
        print(f"Skipped {len(skipped)} private input hashes because challenge packs are absent; candidate membership is verified when the manifest is available.")
    print("Official held-out accuracy is not assessed by this audit.")


if __name__ == "__main__":
    main()
