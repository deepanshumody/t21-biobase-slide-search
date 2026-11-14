# Reproduce the Biobase work

## Review without restricted inputs

The committed report and derived outputs are sufficient to inspect the method and its recorded results.
The numerical tests and repository-artifact audit do not require raw challenge data.

```bash
python3 -m pip install -r scripts/requirements_c1.txt
python3 scripts/test_c1.py
python3 scripts/verify_repository_artifacts.py
```

The artifact audit verifies the snapshot hashes and structural validity of the archived C1/C2 submissions.
It does not verify whether the held-out predictions are correct.

## Recompute the final classifier

With authorized Biobase access, obtain and extract the slide metadata pack and tile/embedding pack so the root contains:

```text
pack_slides/
  slides_manifest.json
  organ_groups.json
  submission_template_slides_organ.csv
  baseline_slides.py
tilepack/
  embeddings/
    gigapath/slide-vectors.json
    biomedclip/
    hoptimus/
    dinov2/
```

Keep all the original contents of each embedding directory, including its tile metadata and int8 tile vectors.
Then run:

```bash
python3 scripts/c1_evaluate_improved.py --out-dir output/c1_reproduced
```

This reads the preserved original submission for the prediction-difference report, selects regularization inside each outer training fold, evaluates ten three-fold repeats, fits on all 190 labelled slides, and writes a new submission.
The fixed feature families are `anchor_dinov2_quantiles`, `anchor_hoptimus_quantiles`, and `giga_clip_0.75`.
The alpha grid is 0.003, 0.01, 0.03, 0.1, 0.3, and 1.0.
The repeat seeds are 101, 211, 307, 401, 503, 607, 701, 809, 907, and 1009.
The source scripts and NumPy requirement are included; no PyTorch or scikit-learn dependency is needed for this default workflow.

The archived `artifact_hashes.json` files refer to original code, inputs, and outputs.
Input hashes can only be checked after obtaining the authorized packs.
The repository-specific `evidence/snapshot_manifest.json` covers the published snapshot and can be checked without those packs.

## Recompute the supplied C2 baseline

With the same packs available, use the baseline script supplied by Biobase:

```bash
python3 pack_slides/baseline_slides.py \
  --manifest pack_slides/slides_manifest.json \
  --vectors tilepack/embeddings/gigapath/slide-vectors.json \
  --out-dir output/c2_reproduced
```

The baseline ranks other slides by GigaPath cosine similarity and writes `baseline_similar.csv`.
Its candidate pool includes labelled and held-out slides, excludes the query itself, and returns ten matches per query when vectors are available.
The archived baseline contains all 67 queries.
The improved C2 submission is available at `output/c2/submission_similar.csv`.

## Recompute organ-aware C2 retrieval

With the authorized challenge packs available, use Python 3.12 and the C2 runtime pin:

```bash
python3 -m pip install -r scripts/requirements_c2.txt
python3 scripts/test_c2.py
python3 scripts/c2_retrieval.py --out-dir output/c2_reproduced
python3 scripts/verify_c2.py
```

The pipeline repeats four-fold outer validation five times and selects retrieval weight using three repeated four-fold inner runs.
It fits regularization and temperature using only training-fold labels, then fits the final classifier on all 190 labelled slides.
The comparison uses 188 labelled slides with GigaPath vectors; the final submission searches all 263 slides.
The original C1 outputs are not modified.
The artifact audit checks the archived `output/c2` files, their code hashes, exact baseline parity, and the 670-row submission contract.
It can run without private inputs, explicitly reporting skipped private-input checks.
The recorded C2 runtime is NumPy 1.26.4; C1's original runtime pin is retained separately.
See [C2 retrieval methods](C2_RETRIEVAL.md) for the score formula, limitations, and results.

## Optional development experiments

The original screening exports are archived under `evidence/experiments/`.
The PDF references their original workspace location, `tmp/c1_improved/`; the filenames are unchanged in the archive.

`c1_screen.py` explores ridge kernels and regularization values.
Create `tmp/c1_improved/` before rerunning screening scripts, since that was the original development output location.
`c1_screen_svm.py` and `c1_screen_logistic.py` also require scikit-learn; the recorded experiments used version 1.8.0.
Both screening scripts load the experimental 20x feature cache, so regenerate it first if those experiments are needed.

`c1_extract_20x.py` and `c1_extract_overview.py` require the authorized image packs, PyTorch, torchvision, Pillow, a locally available DINOv2 source checkout, and the matching pretrained checkpoint.
The recorded extraction used CPU execution and PyTorch 2.11.0.
The extractor defaults refer to local Torch Hub cache paths and do not download weights automatically.
Checkpoint hashes and preprocessing settings are recorded under `evidence/c1_20x_features/` and `evidence/c1_overview_features/`.
No checkpoint or extracted feature array is committed.

The supplied PDF can be viewed directly.
Rebuilding it with `scripts/build_c1_report.py` requires ReportLab and the macOS Arial/Courier font paths used by the original report builder.
Report generation is separate from classifier reproduction.

## Publish the prepared repository

The local repository is prepared on `main`.
From a terminal with an authenticated GitHub CLI and network access, run:

```bash
bash scripts/publish_private_repository.sh
```

This creates `t21-biobase-slide-search` in the authenticated user's GitHub account, sets it private, pushes the committed project, and sets `main` as its default branch.
It refuses to run from another branch, with uncommitted changes, or when an `origin` remote already exists.
It does not invite collaborators or submit the event form.
The command prints the repository URL, privacy setting, and default branch for verification.
