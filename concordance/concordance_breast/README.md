# Concordance (breast): trial matches you can trust, and know when not to

This is the breast-cancer validation of Concordance, on real TCGA pathology reports with curated labels.
The goal is to check whether the trial-matching extractor in `../criteria_search/`
also works on **real** pathology reports, not just the synthetic challenge data.

## Data (all public)

| File | Source | Licence |
|---|---|---|
| `data/raw/TCGA_Reports.csv` | TCGA-Reports, 9,523 OCR'd TCGA pathology reports (Kefeli & Tatonetti, *Patterns* 2024), [github.com/tatonetti-lab/tcga-path-reports](https://github.com/tatonetti-lab/tcga-path-reports) | MIT |
| `data/raw/brca_tcga_clinical_patient.json` | cBioPortal study `brca_tcga`, patient clinical data (public API) | TCGA open access |
| `data/brca_linked.jsonl` | Built by `scripts/build_linked.py`: **1,034 breast-cancer patients**, each with one report plus labels | — |

Each record in `brca_linked.jsonl` has the following fields:
- `id`: the TCGA patient barcode
- `report_text`
- `labels`: the raw TCGA fields
- `gold`: normalized facts `er, pr, her2, t_major, n_major, nodes_pos, margin, histology, age, sex`.
  HER2 is called positive on IHC 3+ or FISH positive, and negative on IHC 0/1+ or on IHC 2+ with FISH negative.

## What the real reports look like (findings so far)

- They're messy OCR from many hospitals. Typos ("carcinuna"), broken lines, no fixed layout.
  The synthetic reports' **template parser will not work** here.
- **The labels are not always in the report.** ER and PR are mentioned in only about 40% of
  reports and HER2 in about 60%, because receptor status is often in a separate report. Node
  counts (81%), margins (85%) and size (96%) are mentioned much more often.
  → Score each fact as **coverage** (did the reader find a value?) and **accuracy when
  found**. Missing information should come out as "unknown", never as a guess.
- TCGA labels come from clinical forms, not directly from this text, so a few apparent
  "errors" will be label noise. Hand-check a sample before blaming the reader.

## Plan

1. Split into dev and holdout halves by md5(id). Develop on dev only and score holdout once.
2. Readers to compare:
   - the synthetic template reader (expected to fail)
   - a regex + negation reader built for real text (the `prose_card.py` approach)
   - optionally, a language-model extractor
3. Score each field (coverage and accuracy), then criteria with TCGA equivalents:
   HER2− and node+ (c01), ER+ PR− (c02), triple negative (c03), plus pT ≥ 2,
   node-positive, positive margin, lobular histology.
4. Feed the confidence score: does low confidence actually predict the wrong answers?
