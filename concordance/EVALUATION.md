# Cohort-search evaluation

## Review budget

For each criterion, rank predicted matches by descending confidence, breaking ties by patient ID.
Both the rules reader and naive baseline are evaluated, along with development-calibrated rules when a calibration table is available.
No gold values are used to break ranking ties.

The offline evaluation excludes candidates whose criterion-level gold answer is undetermined before ranking and reports their number in `excluded`.
This is an evaluation of the labeled subset, not the actual review effort for an incompletely labeled patient inventory.
Unknown gold is not treated as a negative label.

At each budget K = 10, 25, or 50:

| Field | Definition |
|---|---|
| `reviewed` | Number returned for review, at most K |
| `hits` | Reviewed patients whose gold answer is match |
| `positives` | All patients with gold match for that criterion, including missed and undetermined predictions |
| `P@K` | hits / reviewed; precision among the returned candidates |
| `R@K` | hits / positives; fraction of the known matching cohort found |
| `excluded` | All predicted matches excluded because their criterion-level gold is unknown |

A shortlist can contain fewer than K patients.
Precision uses the actual number reviewed and is `n/a` for an empty shortlist.
Recall is zero when positives exist but no matching patients were retrieved, and `n/a` when there are no known positives.
The output includes the denominators so these cases are distinguishable.

Example: 100 patients truly match, and 8 of the top 10 reviewed candidates match.
Precision@10 is 8/10 = 0.800, while recall@10 is 8/100 = 0.080.
Recall cannot decrease when the budget grows along the same ranking.

## Confidence and calibration

The evaluators produce three calibration tables:

1. All decided answers, pooling matches and exclusions.
2. Match decisions only, where observed accuracy measures shortlist precision within each confidence bin.
3. No-match decisions only, where observed accuracy measures the correctness of exclusions.

Unknown gold and undetermined predictions are excluded from calibration.
Confidence zero belongs in the first bin, and confidence one belongs in the last bin.
An empty population has `n/a` ECE, rather than a measured error of zero.
Each table reports its support count.

Calibration estimates decision correctness; it does not turn missing report information into an established fact.
A strong pooled calibration score can coexist with poor precision for matches, especially when most decisions are exclusions.
The shared regression tests include exactly this situation.

The committed calibration tables were fit on development patients.
The colon CLI rejects `--fit --holdout` and `--audit --holdout` so that these development actions cannot accidentally use holdout patients.
Readers and calibration tables were not retuned as part of the metric correction.

## Historical outputs

The committed `concordance_breast/results_*.txt` and `concordance_colon/results_*.txt` are output from the original evaluation.
They are retained unchanged as historical artifacts, rather than edited by hand.
Their sections titled `RECALL AT REVIEW BUDGET` used `hits / min(K, positives)` and are invalid as recall.
Their pooled calibration tables do not establish match-only precision.

The published F1 values use a separate calculation and are not changed by the review-budget denominator fix.
However, a fresh full-cohort run has not been completed: the linked TCGA inputs were absent and the public-data download failed in the restricted execution environment.
Corrected full-cohort P@K, R@K, and match-only calibration remain unmeasured here.

The unit and CLI tests demonstrate the corrected metric behavior on controlled fixtures.
They do not replace evaluation on the full real-report datasets.

## Reproduction

From the repository root:

```bash
python3 -m unittest discover -s concordance/tests -v
bash concordance/fetch_public_data.sh

# Generate new outputs using the frozen readers and committed calibration tables.
python3 concordance/concordance_breast/evaluate.py > /tmp/breast_dev_corrected.txt
python3 concordance/concordance_breast/evaluate.py --holdout > /tmp/breast_holdout_corrected.txt
python3 concordance/concordance_colon/evaluate.py > /tmp/colon_dev_corrected.txt
python3 concordance/concordance_colon/evaluate.py --holdout > /tmp/colon_holdout_corrected.txt
```

Check dataset patient counts against the historical runs before comparing results because the download script uses live public sources.
Regenerate result artifacts through these commands; do not modify generated numbers manually.
The original cohorts contained 1,034 breast patients and 580 colorectal patients, with 521 and 319 holdout patients respectively.
The four demo reports under `examples/` illustrate cohort-search behavior only.

## Limits of the open-idea prototype

The criteria are fixed report-level definitions and are not independently adjudicated clinical-trial eligibility labels.
The breast baseline has higher recorded mean F1 than the rules reader.
The colorectal rules reader has only a small recorded mean F1 improvement over its baseline.
No confidence interval or significance test establishes a broad performance advantage.
The colorectal age criterion takes age from structured clinical labels during evaluation and from explicit clinical metadata during search.

Audit verdicts remain unconfirmed.
The suggested breast disagreements were stratified by fact, so their raw proportions would not establish a population-wide label-error rate even after adjudication without accounting for sampling.
Trial matching and sample-inventory linkage are not implemented.
