# C2: organ-aware slide retrieval

C2 rewards precision at 1, 5, and 10 based on shared organ group.
The strongest tested strategy is to reuse the C1 classifier, combine its organ evidence with visual similarity, and validate the resulting retrieval procedure with labels hidden for query slides.
The completed submission is [submission_similar.csv](../output/c2/submission_similar.csv), containing 670 rows for 67 queries.
The submission has been generated and checked locally; official challenge scoring has not been performed.

## Ranking method

The classifier uses the existing three C1 feature families: `anchor_dinov2_quantiles`, `anchor_hoptimus_quantiles`, and `giga_clip_0.75`.
Each family uses kernel ridge regression, with regularization selected using training-only leave-one-out predictions.
The three score vectors are averaged, then converted to softmax scores using a temperature selected to minimize training leave-one-out negative log likelihood.
These temperature-fitted scores represent model uncertainty; independent probability calibration has not been established.

For a gallery slide with a supplied organ label, its organ distribution is a one-hot vector.
For an unlabelled gallery slide, the distribution comes from the model.
Query distributions always come from a model fitted without the query's label.
The dot product of query and candidate organ distributions is an organ-agreement score.

```text
organ_agreement(q, r) = sum_c p(c | q) * p(c | r)
visual(q, r) = (GigaPath_cosine(q, r) + 1) / 2
score(q, r) = weight * organ_agreement(q, r) + (1 - weight) * visual(q, r)
```

The candidate weights are 0, 0.25, 0.5, 0.75, and 1.
Selection maximizes the unweighted mean of precision at 1, 5, and 10 because no combined weighting is specified in the provided challenge README.
Final repeated validation selected `weight = 0.75`.
Exact score ties use visual similarity, then slide ID for deterministic ordering.
Identifiers have no predictive role.
Queries are excluded from their own results, and every result list contains ten distinct slides.

The final classifier uses all 190 available organ labels and searches the full 263-slide collection.
The two gallery slides without GigaPath vectors retain their known organ evidence and receive zero visual cosine evidence.
Raw cosine values from different embedding models are not mixed because their scales are not comparable.
All 67 official queries have GigaPath vectors.
The provided GigaPath embeddings are reused directly; no new model download, image encoding, or GPU is required.
The underlying model is described in the [Prov-GigaPath paper](https://www.nature.com/articles/s41586-024-07441-w); this project does not reproduce its whole-slide pretraining pipeline.

## Validation

The comparison includes the same 188 labelled slides with GigaPath vectors for both methods.
Each outer fold hides roughly one quarter of gallery labels, approximating the labelled/unlabelled mixture in the official task.
Other hidden slides remain eligible gallery candidates, but their organ distributions are predicted.
Only visible training labels become one-hot gallery distributions.
True hidden labels are used solely for scoring and stratified fold construction.

Outer evaluation uses five repeated stratified four-fold runs with seeds 1201, 1301, 1409, 1511, and 1601.
Inside each outer training set, three repeated four-fold runs select the retrieval weight.
Inner seeds use the outer seed plus 100 plus fold number, with repeat offsets 0, 17, and 43.
Every inner fit independently selects regularization and temperature from its own training labels.
Final weight selection uses the same repeated inner procedure on the 188-slide development cohort, starting at seed 1801, before fitting the classifier on all 190 labels.

| Method | Precision at 1 | Precision at 5 | Precision at 10 |
| --- | ---: | ---: | ---: |
| GigaPath cosine baseline | 78.72% | 56.38% | 45.00% |
| Organ-aware retrieval | 87.87% | 84.47% | 81.35% |
| Improvement | +9.15 points | +28.09 points | +36.35 points |
| Best possible in this gallery | 100.00% | 96.91% | 93.51% |

The gallery ceilings account for rare organs with fewer than ten other examples.
Per-organ and per-supplier results, paired slide-bootstrap intervals, fold selections, and per-query rankings are recorded in the output files.
All 67 final query organ predictions match the completed C1 submission.
The regenerated official GigaPath baseline exactly matches all 670 rows of the archived baseline.

## Limits of the evidence

These are internal estimates rather than official challenge scores.
C1 feature families were previously explored on these same labelled slides, so new fold seeds do not make this an untouched external test.
There is no ground truth for the 73 currently unlabelled slides, so internal retrieval metrics use the 188-slide gallery rather than the full 263-slide gallery.
The larger final training set and gallery may behave differently.
Repeated predictions share slides, and the approximate slide-bootstrap intervals do not account for all model-selection uncertainty.
Patient identifiers were not provided, so patient-level overlap cannot be excluded.
Organ-group relevance does not establish matching diagnosis, cancer subtype, stage, or clinical suitability.
Very uncertain queries and rare organs should be inspected using the review queue.

## Reproduction and checks

Use Python 3.12 and NumPy 1.26.4 for the recorded C2 runtime.
Run these commands from the `biobase/` folder; use `cd biobase` first when starting at the repository root.

```bash
python3 -m pip install -r scripts/requirements_c2.txt
python3 scripts/test_c2.py
python3 scripts/c2_retrieval.py --out-dir output/c2_reproduced
python3 scripts/verify_c2.py
```

The behavioral tests cover hidden-label invariance, known versus uncertain candidate labels, deterministic ties, missing visual evidence, rare-class folds, precision calculations, and submission failures.
The audit verifies archived file hashes, exact baseline parity, evidence/submission agreement, query coverage, ranks, distinct results, and self-exclusion.
When the challenge manifest is available, it also verifies candidate membership against that manifest.
Input hashes are checked when the private packs are present and reported as skipped otherwise.
The original C1 snapshot and supplied challenge data remain unchanged.
