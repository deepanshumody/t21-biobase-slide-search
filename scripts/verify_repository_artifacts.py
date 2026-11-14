#!/usr/bin/env python3
"""Verify the repository snapshot and submission structure without private inputs."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORGANS = {
    "Bladder", "Bone", "Bone marrow", "Breast", "Colon and rectum", "Esophagus",
    "Kidney", "Liver", "Lung", "Other or mixed", "Prostate", "Skin", "Stomach",
    "Thyroid", "Uterus",
}


def read_csv(relative_path, fields):
    with (ROOT / relative_path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != fields:
            raise ValueError(f"Unexpected columns in {relative_path}: {reader.fieldnames}")
        return list(reader)


def main():
    snapshot = json.loads((ROOT / "evidence/snapshot_manifest.json").read_text())
    for item in snapshot["files"]:
        path = ROOT / item["repository_path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise ValueError(f"Snapshot hash mismatch: {item['repository_path']}")

    query_ids = None
    for file in ["output/c1/submission_organ.csv", "output/c1_improved/submission_organ.csv"]:
        rows = read_csv(file, ["slide_id", "organ"])
        ids = {row["slide_id"] for row in rows}
        if len(rows) != 67 or len(ids) != 67 or any(row["organ"] not in ORGANS for row in rows):
            raise ValueError(f"Invalid C1 submission: {file}")
        if query_ids is not None and ids != query_ids:
            raise ValueError("Original and final C1 submissions cover different query IDs")
        query_ids = ids

    rows = read_csv("output/c1/baseline/baseline_similar.csv", ["query_slide_id", "rank", "result_slide_id"])
    groups = defaultdict(list)
    for row in rows:
        if not row["result_slide_id"] or row["query_slide_id"] == row["result_slide_id"]:
            raise ValueError("C2 baseline contains an empty result or self-match")
        groups[row["query_slide_id"]].append(row)
    if set(groups) != query_ids or len(rows) != 670:
        raise ValueError("C2 baseline must contain all 67 queries and 670 rows")
    for query, matches in groups.items():
        if sorted(int(row["rank"]) for row in matches) != list(range(1, 11)):
            raise ValueError(f"Invalid ranks for {query}")
        if len({row["result_slide_id"] for row in matches}) != 10:
            raise ValueError(f"Duplicate results for {query}")
    print(f"Verified {len(snapshot['files'])} snapshot hashes, 67 C1 query IDs, and 670 C2 baseline rows.")
    print("This verifies archived structure and provenance, not held-out prediction correctness.")


if __name__ == "__main__":
    main()
