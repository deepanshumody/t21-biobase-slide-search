# Concordance breast cohort search

This folder implements a real-report reader and eight fixed cohort criteria with evidence and three-valued decisions.
It is an open-idea report-search prototype; clinical-trial eligibility matching is not implemented.
See the [project README](../README.md) for the runnable cohort-search command and [evaluation definitions](../EVALUATION.md) for the corrected metrics.

## Data

| File | Source | Scope |
|---|---|---|
| `data/raw/TCGA_Reports.csv` | TCGA-Reports | Public OCR pathology reports |
| `data/raw/brca_tcga_clinical_patient.json` | cBioPortal `brca_tcga` | Structured clinical labels |
| `data/brca_linked.jsonl` | `scripts/build_linked.py` | Original run: 1,034 linked patients |

Each linked record contains `id`, `report_text`, raw `labels`, and normalized `gold` facts.
The raw labels come from clinical forms and can contain facts absent from the selected pathology report.
Unknown report facts are returned as undetermined rather than inferred from those labels.

## Recorded evidence

The historical 521-patient holdout run scored mean F1 0.523 for rules and 0.557 for the naive baseline.
ER and PR were mentioned in about 65% of these reports, but the rules reader extracted values in only 43% and 38% of cases with known gold respectively.
Both absent information and missed extraction limit recall.
Historical ECE fell from 0.097 to 0.022 after development-fit calibration, pooling matches and exclusions.
The high-confidence pooled accuracy does not measure shortlist precision.

The original review-budget output has an incorrect recall denominator.
Corrected full-cohort results require a new run with the public inputs; the existing output files have not been edited by hand.
Audit suggestions are not confirmed label errors, and no adjusted reader accuracy is established.
