# Concordance: trial matching from pathology reports

Team T21's report-side work for the Biobase challenge: Task A (criteria search over the
synthetic pathology reports), plus validation of the same approach on **real** TCGA
pathology reports and a first step towards matching patients to real clinical trials.

> Trial matches you can trust, and know when not to.

## What's here

| Folder | What it is | Headline result |
|---|---|---|
| [`criteria_search/`](criteria_search/) | **Task A.** Biobase reports → fact card → 30 criterion rules. Writes `submission.json`. | Train mean F1 **1.000** (keyword baseline 0.27). Prose-only robustness check: 0.975 on a held-out half. |
| [`concordance_breast/`](concordance_breast/) | External validation on **1,034 real TCGA breast reports** with curated labels (ER/PR/HER2, pT/pN, nodes, margin, histology) | Holdout F1 0.52; accurate when it answers (82–98%); **ECE 0.097 → 0.022** after calibration |
| [`concordance_colon/`](concordance_colon/) | Same framework on **580 real TCGA colorectal reports**; criteria mirror the challenge's colon criteria | Holdout F1 **0.68**; 95–100% accurate when it answers; **ECE 0.011** |
| [`trial_twins/`](trial_twins/) | Digital twins (the fact card) matched against **real recruiting trials** from ClinicalTrials.gov | Design + trial fetch done; matching not built yet |

Each folder has a `*_design.md` covering how it works, its results and its limits. Start with
[`criteria_search/criteria_search_design.md`](criteria_search/criteria_search_design.md).

Key findings:
- **The template parser** reaches 1.0 on Biobase but **0 on real reports**: the
  synthetic summary block is written by code.
- **A reader built for real reports** generalises back: run unchanged on Biobase it scores
  **0.94** mean F1 on 8 overlapping criteria (0.99 without c13, which needs a size fact it lacks).
- **On real reports, confidence is calibrated.** Answers given ≥ 0.9 confidence were right
  **98%** of the time on held-out patients, in both organs. Recall is limited mostly by
  facts the report doesn't contain (e.g. ER/PR are mentioned in only ~65% of breast reports).
- **About half of audited disagreements look like TCGA label errors.** The verdicts in
  `*/audit/disagreements.csv` are suggestions until a person confirms them.

## Running it

Python 3.9+, standard library only.

```bash
cd concordance

# Task A: needs the Biobase report pack (restricted; see below) at criteria_search/pack_reports/
cd criteria_search && python3 evaluate.py && python3 run.py && cd ..

# TCGA validation: download the public data first (~100 MB, not in Git)
bash fetch_public_data.sh
cd concordance_breast && python3 calibrate.py && python3 evaluate.py && cd ..   # add --holdout for the held-out half
cd concordance_colon  && python3 evaluate.py --fit && python3 evaluate.py && cd ..

# Trial twins: refresh candidate trials from ClinicalTrials.gov (public API, generic queries only)
cd trial_twins && python3 fetch_trials.py
```

## Data and permissions

- **Biobase challenge data is not in this repository**, following
  [`biobase/docs/DATA_AND_ACCESS.md`](../biobase/docs/DATA_AND_ACCESS.md). To run Task A,
  unzip the report pack so that `criteria_search/pack_reports/` exists.
  `criteria_search/submission.json` and `cross_check.json` are derived records: report ids
  and predictions only.
- **The TCGA data is public but not committed** (size). `fetch_public_data.sh` recreates it:
  - TCGA-Reports (Kefeli & Tatonetti, *Patterns* 2024, MIT licence)
  - cBioPortal `brca_tcga` / `coadread_tcga` clinical data
  
  The audit CSVs quote short snippets of those public reports.
- **`trial_twins/trials/raw/`** holds ClinicalTrials.gov records as fetched on 2026-11-14.
  Trial text changes over time, so each record carries its fetch date.
- Synthetic and research data only. Nothing here is for clinical or enrollment decisions.
