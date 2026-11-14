# Concordance: cohort search with evidence and missing facts

Concordance is Team T21's open-idea prototype for finding report-defined cohorts.
It extracts facts from pathology reports, checks a selected criterion, and returns matches, exclusions, or undetermined cases with supporting text.
The working scope is report search; clinical-trial matching and specimen-inventory linkage are future work.

## Run the cohort-search demo

Python 3.9+, standard library only.
From the repository root:

```bash
python3 concordance/search.py --organ colon --criterion C7 \
  --input concordance/examples/colon_reports.jsonl \
  --output /tmp/concordance_candidates.json
```

The four invented demo reports produce one match, two exclusions, and one undetermined case for age at least 70 with positive nodes.
The JSON export contains a ranked shortlist, every patient's decision, supporting evidence, and facts the reader could not establish.
This demo illustrates behavior; it is not an accuracy benchmark.

For your own data, provide a JSONL file of reports from one selected organ with `id` and `report_text` fields.
An optional `organ` field must agree with `--organ`.
For the colon age criterion, provide age explicitly as `clinical.age`; its provenance appears in the explanation.
The search command never reads `gold` or `labels` fields to fill missing facts.
Choose B1-B8 for breast or C1-C8 for colon, and use `--limit` to set the shortlist size.
The criteria are fixed definitions, not arbitrary natural-language queries.

Confidence is hand-set by default.
Use `--calibration concordance/concordance_colon/calibration.json` to apply the frozen development-fit table for colon, or the corresponding breast table for breast.
A confidence value is not proof of trial eligibility.

## What is implemented

| Folder or file | Working capability | Evidence and scope |
|---|---|---|
| [`criteria_search/`](criteria_search/) | Task A: synthetic reports to facts to 30 fixed rules | Training mean F1 1.000; rules were developed against the training answers |
| [`concordance_breast/`](concordance_breast/) | Real-report reader, eight criteria, evidence, uncertainty, calibration | Recorded holdout F1 0.523 versus naive 0.557, on 521 patients |
| [`concordance_colon/`](concordance_colon/) | Same workflow for eight colorectal criteria | Recorded holdout F1 0.680 versus naive 0.671, on 319 patients |
| [`search.py`](search.py) | Ranked cohort export with match, no_match, and undetermined decisions | Runnable using the included invented demo reports |
| [`evaluation_metrics.py`](evaluation_metrics.py) | Shared review-budget and decision-specific calibration metrics | Covered by unit tests and both evaluator CLIs |
| [`trial_twins/`](trial_twins/) | Trial-fetch script, downloaded records, and a design | No encoded trial rules, matcher, or trial-eligibility validation yet |

The real-report scores above are historical results from the committed output files.
The linked TCGA inputs were unavailable during the metric correction, and the public-data download failed in the restricted execution environment.
Full-cohort corrected results have not been regenerated.
The old sections titled `RECALL AT REVIEW BUDGET` use an incorrect denominator and must not be cited as recall.
See [evaluation definitions and reproduction](EVALUATION.md).

## What the evidence supports

- The synthetic template parser recorded zero fact coverage on the real breast reports; the real-report readers recover useful evidence from less structured text.
- Breast rules underperform the naive reader on mean F1; the small colorectal improvement has no uncertainty estimate and should not be presented as a demonstrated general advantage.
- Historical calibrated ECE was 0.022 for breast and 0.011 for colon, pooling match and no_match decisions.
  The reported 98% correctness at high confidence includes exclusions and is not shortlist precision.
  Updated evaluators report match-only and exclusion-only calibration separately.
- Missing facts constrain retrieval, and imperfect extraction also loses information that is present in the text.
- Audit suggestions have not been confirmed by a person.
  Neither the label-error rate nor an adjusted reader accuracy has been established.
- The colon age criterion uses age from TCGA clinical labels in evaluation, so it is not a report-only extraction result.

## Evaluate and reproduce

```bash
python3 -m unittest discover -s concordance/tests -v

# Download public data, then evaluate the frozen readers and calibration tables.
bash concordance/fetch_public_data.sh
python3 concordance/concordance_breast/evaluate.py
python3 concordance/concordance_breast/evaluate.py --holdout
python3 concordance/concordance_colon/evaluate.py
python3 concordance/concordance_colon/evaluate.py --holdout
```

The regression tests use invented fixtures and require no network or TCGA download.
Changes to extraction rules after inspecting holdout results require a new untouched evaluation set.
Correcting metric code does not create a new holdout or justify retuning the readers on it.

Task A requires the authorized Biobase report pack at `criteria_search/pack_reports/`:

```bash
cd concordance/criteria_search
python3 evaluate.py
python3 run.py
```

## Data and permissions

Biobase challenge inputs are excluded from Git; see [`biobase/docs/DATA_AND_ACCESS.md`](../biobase/docs/DATA_AND_ACCESS.md).
Task A submission artifacts contain report identifiers and predictions.
The included demo records are invented examples with no patient data.
Public TCGA inputs are also excluded from Git for size; the fetch script downloads TCGA-Reports and cBioPortal clinical labels.
Trial records are dated snapshots, not confirmation of current recruitment status.
This prototype retrieves report-defined cohorts and does not establish clinical enrollment eligibility or sample availability.
