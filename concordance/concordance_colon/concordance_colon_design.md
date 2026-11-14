# Concordance (colon): Design

The second organ for the Concordance validation. It uses the **same framework as
`../concordance_breast/`** (read that design first); this doc covers only what differs.

**Goal:** show that the approach (rule reader → three-valued criteria → calibrated
confidence) carries over to a second cancer type. The colon criteria mirror the synthetic
challenge's colon criteria, so we can compare synthetic and real results directly.

## 1. What's shared and what's new

| Kept from breast | New for colon |
|---|---|
| Three-valued answers: match / no_match / undetermined | Criteria C1–C8 (below) |
| Evidence kinds + confidence; calibration fit on DEV per (fact, kind) | Facts: lvi, pni, mucinous, residual tumor |
| Metrics: coverage, accuracy when found, P/R/F1, ECE (10 bins), recall@K | Colon-specific phrasings (e.g. "angiolymphatic invasion", "R0") |
| Shared machinery: OCR normalization, boilerplate filter, resolve, stage/node finders | Labels from cBioPortal `coadread_tcga` |
| Dev/holdout split by md5(id); holdout scored once; 30-row audit | — |

**Code reuse:** `reader.py` here imports the shared machinery from
`../concordance_breast/reader.py` and adds colon finders, so there's one copy of each
technique. If this grows to a third organ, move the shared parts into a `concordance_core/` module.

## 2. Data

`data/brca`-style linked file: `data/coadread_linked.jsonl`, built by `build_linked.py`.
- **580 colorectal patients** with one TCGA-Reports report each, plus cBioPortal labels.
- The reports CSV is symlinked from the breast folder, not copied.

| Gold fact | Source | Known |
|---|---|---|
| `t_major` | AJCC_TUMOR_PATHOLOGIC_PT | ~100% |
| `n_major` | AJCC_NODES_PATHOLOGIC_PN | ~100% |
| `nodes_pos` | LYMPH_NODES_EXAMINED_HE_COUNT | 95% |
| `mucinous` | HISTOLOGICAL_DIAGNOSIS contains "Mucinous" | 98% |
| `lvi` | LYMPHOVASCULAR_INVASION_INDICATOR | 93% |
| `pni` | PERINEURAL_INVASION | **39%** (small sample) |
| `residual` | RESIDUAL_TUMOR: R0 = clear; R1/R2 = tumor left | 85% (RX → unknown) |
| `age`, `site` | AGE; SITE_OF_TUMOR_TISSUE (colon / rectum) | ~100% |

How often each fact is mentioned anywhere in the report: pT 87%, nodes 86%, margin 88%,
**LVI 38%, PNI 26%, mucin 17%**. As with breast receptors, this caps achievable coverage.

**Caveat:** R2 in TCGA often means residual disease elsewhere (for example liver metastases
left behind), not an involved margin on this specimen. So the margin criterion (C8) is
reported, but flagged as weak gold.

## 3. Criteria

| id | Criterion | Synthetic analogue |
|---|---|---|
| C1 | Node positive (pN ≥ 1) | c08 |
| C2 | Mucinous adenocarcinoma | c09 |
| C3 | No positive nodes (pN0) and LVI present | c11 |
| C4 | pT4 (penetrates visceral peritoneum / invades adjacent organs) | c12 |
| C5 | Perineural invasion present | c13 (no size label in TCGA, so PNI alone) |
| C6 | Lymphovascular invasion present | new |
| C7 | Age ≥ 70 and node positive | c29 (age comes from labels, since TCGA reports are de-identified) |
| C8 | Tumor left at resection (R1/R2) | new, weak gold (see above) |

## 4. Colon finders (new)

- **lvi:** "lymphovascular / angiolymphatic / lymphatic / vascular / venous (small or large
  vessel) invasion" with the shared present/absent logic (negation before the mention, cue
  word after). Also synoptic "LYMPH-VASCULAR INVASION: Present / Not identified".
- **pni:** "perineural invasion" with the same logic.
- **mucinous:** "mucinous adenocarcinoma" or "with mucinous features / >50% mucin" →
  mucinous. Plain "adenocarcinoma" with no mucinous mention → **not** mucinous, but only when a
  histology statement exists (so absence of mention ≠ evidence).
- **residual:** "margins negative / uninvolved / free" → R0; "margin involved / positive" →
  R1. Also an explicit "R0" / "R1" code.
- **t_major / n_major / nodes_pos:** shared finders. Colon reports often give "12/15 lymph
  nodes" or "(0/23)", so the breast lesson is applied: **sum** node counts across
  specimens instead of taking the max.

## 5. Evaluation

Same metrics as breast. Also reported here, for the write-up:
- the synthetic → real comparison: train F1 on the synthetic challenge (1.0) next to holdout
  F1 on TCGA, criterion by criterion
- a breast vs colon table: does calibration hold on both organs?

## 6. Files

| File | Responsibility |
|---|---|
| `build_linked.py` | Reports + labels → `data/coadread_linked.jsonl` |
| `reader.py` | Colon fact finders on top of the shared breast machinery |
| `criteria.py` | C1–C8, three-valued |
| `evaluate.py` / `calibrate.py` / `audit.py` | Same roles as breast |

## 7. Results: first frozen run (2026-11-14)

The reader was frozen after dev work, calibration was fit on dev (`evaluate.py --fit`), and
holdout was scored once. Full output is in `results_dev.txt` and `results_holdout.txt`.

| Holdout (n=319) | rules | naive |
|---|---|---|
| Mean F1, C1–C8 | **0.680** | 0.671 |
| ECE, hand-set confidences | 0.092 | — |
| ECE, dev-fit confidences | **0.011** | — |
| Recall@10 (top 10 by confidence that are true matches) | 1.00 on 7 of 8 criteria | — |

| Criterion | Holdout F1 | Synthetic analogue (train F1) |
|---|---|---|
| C1 node positive | 0.89 | c08 (1.0) |
| C2 mucinous | 0.49 | c09 (1.0) |
| C3 pN0 + LVI | 0.57 | c11 (1.0) |
| C4 pT4 | 0.86 | c12 (1.0) |
| C5 PNI present | 0.75 | ~c13 (1.0) |
| C6 LVI present | 0.72 | — |
| C7 age ≥ 70 + node positive | 0.91 | c29 (1.0) |
| C8 R1/R2 (weak gold) | 0.25 | — |

Findings:
- **The approach transfers to a second organ, and colon scores higher than breast**
  (0.68 vs 0.52). Colon facts (stage, nodes, LVI, PNI) are written in the pathology report
  itself; breast receptors often are not.
- **Calibration generalizes again:** holdout ECE is 0.011, and 1,513 answers at 0.9–1.0
  confidence were right 98% of the time.
- **Accuracy when decided is 95–100%** on every criterion. The F1 gap is recall:
  LVI is mentioned in only about 75% of reports, and residual-tumor status is often unstated.
- **One dev bug was worth recording:** "Not identified" was read as filler + "identified"
  because an optional filler word was allowed before the cue. Fixing it lifted PNI accuracy
  from 47% to 97% and LVI from 76% to 95%. A slip like this is why the error dumps and audit exist.
- **Mucinous recall fell on holdout** (0.56 dev → 0.34). Likely causes: "with mucinous
  features" cases that TCGA labels mucinous, and Latin or non-standard phrasing. Look at
  this next, on dev.
- **C8 has weak gold.** TCGA R2 usually means metastases left behind, which the
  specimen report can't show.
- `audit/disagreements.csv` (30 rows) is ready for a person to label.
