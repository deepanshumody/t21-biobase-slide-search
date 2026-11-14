# Biobase Slide Search

- **Team ID:** T21
- **Sponsor prize:** Biobase only, as the team's intended entry.
- **Project status:** C1 classifier and submission completed; C2 retrieval baseline available, with improved retrieval still exploratory.
- **Repository visibility:** Keep this repository private and limit access to the team, organizers, and assigned judges.

## Problem

Finding pathology slides from the right organ is a useful first step in building a searchable tissue collection.
Biobase's Find the Right Patients challenge provides a small collection of de-identified slides with incomplete organ labels.
We address organ classification for held-out slides (C1) and establish a similar-slide retrieval baseline (C2).
A successful result assigns an organ group to every query slide and retrieves relevant slides with evidence that the method generalizes beyond its training examples.

## What we built

### C1: organ classification

We built a reproducible ensemble of three ridge classifiers using frozen GigaPath and BiomedCLIP slide embeddings, plus DINOv2 and H-optimus tile-distribution features.
The final fit uses all 190 slides with organ labels and produces predictions for all 67 held-out slides.
Tile-level quantiles preserve variation that an averaged slide embedding can lose.
The three classifiers' organ scores are averaged equally.

The repository includes the final and original submissions, numerical tests, per-slide validation predictions, experiment summaries, and a methods report.
The original submission is preserved for comparison.

### C2: similar-slide retrieval

The supplied GigaPath cosine-similarity baseline has produced 10 ranked matches for each of the 67 held-out queries: 670 rows in total.
The archived baseline has been checked for valid rank sequences, duplicate results, and self-matches.
Using C1 organ scores to rerank visually similar candidates is a promising next experiment, but an improved C2 system has not yet been finalized or independently validated.

### Biobase prize scope

The event README describes the Biobase prize as an award for contributed evaluation questions, submitted through a dedicated field.
C1/C2 prediction results alone do not demonstrate completion of that prize submission.
Evaluation-question contributions and the event submission form are still to be completed by the team.

## Run or view the demo

Start with the [seven-page methods report](output/pdf/c1_methodology_report.pdf).
It explains the model, the experiments we rejected, the validation protocol, and the limitations.
For a quick evidence review, open the [validation summary](output/c1_improved/validation_summary.json) and [experiment report](output/c1_improved/experiment_report.json).

### Run checks without restricted data

Prerequisites: Python 3.12, pip, and NumPy 2.3.5.

```bash
python3 -m pip install -r scripts/requirements_c1.txt
python3 scripts/test_c1.py
python3 scripts/verify_repository_artifacts.py
```

### Reproduce C1 with authorized challenge access

Obtain the packs through the Biobase onboarding process and extract `pack_slides/` and `tilepack/` into the repository root.
These directories are excluded from Git.
Then run:

```bash
python3 scripts/c1_evaluate_improved.py --out-dir output/c1_reproduced
```

The command recomputes the paired validation and writes a separate reproduction of the 67-row submission.
The default final method needs no model download or GPU.
See [reproduction details](docs/REPRODUCIBILITY.md) for the optional image-feature experiments and the C2 baseline command.

### Submission artifacts

| Artifact | Purpose |
| --- | --- |
| [C1 candidate](output/c1_improved/submission_organ.csv) | 67 organ predictions |
| [Original C1 submission](output/c1/submission_organ.csv) | Preserved comparison |
| [C2 baseline](output/c1/baseline/baseline_similar.csv) | 10 results for each of 67 queries |
| [Changed C1 predictions](output/c1_improved/submission_changes.csv) | One changed prediction, not a verified correction |
| [C1 review queue](output/c1_improved/review_queue.csv) | Alternatives, score margins, and nearby labelled examples |

## Evidence and limitations

We compared methods on the same 188 labelled slides with GigaPath vectors using ten repeated stratified three-fold validation runs.
Regularization selection occurs inside each outer training fold using leave-one-out validation.
The final fit includes two additional labelled slides with missing GigaPath features, represented by zero-valued missing blocks.

| Method | Mean internal validation accuracy |
| --- | ---: |
| Original model-selection procedure | 85.00% |
| Original fixed GigaPath/BiomedCLIP ridge classifier | 85.27% |
| Final three-model ensemble | 85.64% |

The gain over the original selection procedure is 0.64 percentage points.
Its approximate paired slide-bootstrap 95% interval is -0.27 to +1.60 percentage points, so the evidence does not establish a clear improvement.
Feature families were explored on the same labelled dataset; these results are internal estimates, not an untouched external test.
Repeated folds reuse slides, and patient-level overlap cannot be ruled out because patient identifiers were not supplied.
Rare organs have very few examples, and most slides come from one supplier.
The official held-out answer key was not used, and the official C1/C2 scores remain unknown.

We also tested 6,893 nonblank 20x tiles, 1,315 thumbnail views, support-vector classifiers, multinomial logistic classifiers, and broader feature searches.
These alternatives did not provide enough validation benefit to enter the final model.
The [experiment archive](evidence/experiments/) preserves their screening results.

## Data and permissions

The input slides, thumbnails, embeddings, labels, and templates come from the Biobase hackathon challenge packs.
Access is provided to confirmed teams through Biobase's onboarding process, as described in the [event's Biobase note](https://github.com/humic-labs/hackathon-2026-11-14-resources#dnaforge--mtc-berkeley-ai--biology-hackathon).
Obtain restricted data through that approved route.

Raw images, input manifests, input embeddings, source archives, model checkpoints, and local feature caches are not distributed in this repository.
This private repository contains project code, derived prediction/validation artifacts, and the project report.
Derived artifacts include de-identified challenge slide identifiers and organ labels, so reviewer access should remain limited.
No credentials or private access codes are included.
Model and dataset rights remain governed by their respective providers; this repository does not grant additional rights to redistribute sponsor data or pretrained weights.
See [data access and repository contents](docs/DATA_AND_ACCESS.md).

## Next step

Evaluate organ-aware C2 reranking with a realistic mixture of labelled and unlabelled gallery slides, using out-of-fold organ predictions and an untouched validation partition.
Compare precision at 1, 5, and 10 against the GigaPath baseline before changing the C2 submission.
Use the resulting failure cases to draft concrete evaluation questions for the Biobase prize.

## Event handoff

This README follows the [event project template](https://github.com/humic-labs/hackathon-2026-11-14-resources/blob/main/PROJECT-README-TEMPLATE.md).
The event requires the judged work on a private repository's `main` branch by **5 PM Pacific on November 14, 2026**.
Verify organizer and assigned-judge access, submit the repository URL once for Team T21, and keep `main` at the cutoff commit until judging ends.
The repository setup does not submit the event form or invite reviewers automatically.
