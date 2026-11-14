# Concordance (breast): Design

**Goal:** match real breast-cancer pathology reports to trial-style eligibility criteria.
Every answer gets a confidence score, and on real labelled data we check two things:

1. **Accuracy:** are the matches right?
2. **Calibration:** do matches given 0.8 confidence turn out right about 80% of the time?

This is the external validation of the approach built on synthetic reports in
`../criteria_search/`. There, a template parser scored 1.0 because the reports followed a
fixed template. Here the reports are real OCR text from many hospitals, so the template
trick is gone.

## 1. Core idea

Three changes from the synthetic system:

| Synthetic (criteria_search) | Real (concordance_breast) |
|---|---|
| Every fact is in the report | Many facts are **missing** (ER/PR in about 40% of reports) |
| Yes / no per criterion | **Match / no match / undetermined**, plus a confidence score |
| Score = F1 | Score = **coverage**, **accuracy when decided**, **calibration**, **recall at a review budget** |

"Undetermined" is a correct answer when the report doesn't contain the fact. A system
that guesses there looks good on coverage and fails clinically.

```
report_text
   │  reader.py     text → facts, each with {value, evidence snippet, evidence type, confidence}
   ▼
fact sheet
   │  criteria.py   facts → per criterion: match / no_match / undetermined + confidence + "why"
   ▼
answers
   │  evaluate.py   vs TCGA gold: fact coverage + accuracy, criterion metrics, calibration, recall@budget
   │  audit.py      sample of disagreements → CSV for hand-checking (reader error or label noise?)
```

## 2. Data

`data/brca_linked.jsonl`, built by `scripts/build_linked.py`: 1,034 TCGA-BRCA patients,
one report each.

- **Reports:** TCGA-Reports (Kefeli & Tatonetti 2024, MIT): OCR'd and partly cleaned.
- **Labels:** cBioPortal `brca_tcga` patient clinical data.

| Gold fact | Source field(s) | Known |
|---|---|---|
| `er`, `pr` | ER/PR_STATUS_BY_IHC | 96% / 95% |
| `her2` | IHC_HER2 + HER2_FISH_STATUS (IHC 3+ or FISH+ → positive; IHC 0/1+, or 2+ with FISH− → negative) | 84% |
| `t_major` | AJCC_TUMOR_PATHOLOGIC_PT | 100% |
| `n_major` | AJCC_NODES_PATHOLOGIC_PN | 98% |
| `nodes_pos` | LYMPH_NODES_EXAMINED_HE_COUNT | 87% |
| `margin` | PATH_MARGIN (negative / close / positive) | 94% |
| `histology` | HISTOLOGICAL_DIAGNOSIS (ductal / lobular / mucinous / other) | 100% |
| `age`, `sex` | AGE, SEX | 100% |

**Known limits of the gold labels:**
- They come from clinical forms, not from this text. Receptor status often came from a
  separate report, so the gold value can be right while the report says nothing.
- Some labels will be wrong, which is why `audit.py` exists.
- There's no lymphovascular invasion, grade, multifocality or margin distance, so
  criteria c04–c07 from the synthetic set can't be validated here.

**Split:** md5(id), even = **dev** (develop, look at errors), odd = **holdout** (scored
once at the end, never inspected). This is the same protocol as the prose experiment.

## 3. Reader (`reader.py`)

Text in, facts out. Every fact carries the evidence behind it:

```
"her2": {"value": "negative", "evidence": "HER2/neu: Negative (1+)", "kind": "synoptic", "conf": 0.95}
```

**Techniques**, building on `criteria_search/prose_card.py`:
- **Normalize OCR** before matching: rejoin words broken across lines, fix common OCR
  confusions in key terms (`carcinuna` → carcinoma, `HER-2/neu`, `estrogen`/`oestrogen`),
  collapse whitespace.
- **Find the synoptic lines first:** many real reports contain a CAP-style checklist
  ("HISTOLOGIC TYPE:", "MARGINS:", "pT2 pN1a"). These are the most reliable evidence.
- **Fall back to narrative sentences,** using the clause-bounded negation reader
  (`polarity()`).
- **Detect conflicts:** collect every candidate value. If two different values appear
  (biopsy vs resection, for example), keep the most specific one or the one from the
  final diagnosis, and lower the confidence.

**Facts:** er, pr, her2, t_major, n_major, nodes_pos, margin, histology. Age and sex are
usually redacted from TCGA reports, so they come from the labels. That gets noted
wherever it's used.

**Evidence types and starting confidence** (to be recalibrated, see section 5):

| kind | example | start conf |
|---|---|---|
| `synoptic` | "ESTROGEN RECEPTOR: POSITIVE (95%)" | 0.95 |
| `stage_code` | "pT2 N1a" → t_major, n_major | 0.90 |
| `narrative` | "tumor cells are negative for HER2" | 0.80 |
| `derived` | node count "3/14" → n_major ≥ 1 | 0.75 |
| `conflict` | two different values found | × 0.5 |
| `none` | fact not found → value = unknown | — |

## 4. Criteria (`criteria.py`)

These are trial-style criteria with a TCGA gold answer. Each returns **match / no_match /
undetermined**, a confidence, and a "why": the facts used plus their evidence snippets.

| id | Criterion | Synthetic analogue |
|---|---|---|
| B1 | HER2 negative with ≥1 positive lymph node (pN ≥ 1) | c01 |
| B2 | ER positive and PR negative | c02 |
| B3 | Triple negative | c03 |
| B4 | HR positive (ER+ or PR+) and HER2 negative (the most common trial cohort) | new |
| B5 | Tumor pT2 or higher | new |
| B6 | Node positive (pN ≥ 1) | c08-style |
| B7 | Positive surgical margin | new |
| B8 | Invasive lobular carcinoma | new |

**Three-valued logic:**
- A criterion is **match** only if every required fact is known and passes.
- It is **no_match** if any known fact fails. One failing fact is enough, so "ER
  negative" settles B4 even when HER2 is unknown.
- Otherwise it is **undetermined**.

**Confidence** for a match = min(confidence of the required facts). For no_match it is the
confidence of the deciding fact. The minimum is used because a match is only as strong as
its weakest fact.

## 5. Evaluation (`evaluate.py`)

Patients whose **gold** value is unknown for a fact or criterion are excluded from that
metric.

1. **Fact level, per fact:**
   - *coverage:* the share of patients where the reader gave a value
   - *accuracy when found*
   - *mention rate:* how often the fact appears anywhere in the text, which is the
     realistic upper limit on coverage
2. **Criterion level, per criterion:**
   - *decided rate:* match or no_match rather than undetermined
   - precision, recall and F1 on decided cases
   - *end-to-end recall:* the share of true matches we flagged, counting undetermined
     as missed
3. **Calibration:**
   - pool all decided answers and bin them by confidence (10 bins)
   - report observed accuracy per bin, a reliability chart, and **ECE**
   - the starting confidences are hand-set; if needed, fit a per-evidence-kind mapping on
     **dev** and report ECE on **holdout**
4. **Recall at review budget:** rank each criterion's candidates by confidence. If a
   clinician reviews only the top K (K = 10, 25, 50), what share of true matches do they
   see? This is the clinician-facing number.
5. **Baselines** for the same metrics:
   - keyword search (the challenge-style baseline)
   - the synthetic template reader, `criteria_search/card.py`, expected to be near 0 coverage

## 6. Audit (`audit.py`)

Draws a random sample of 30 dev disagreements and writes them to `audit/disagreements.csv`
with these columns: id, fact, reader value, gold value, evidence snippet, and the report
passage. A person marks each row as *reader error*, *label noise* or *not in report*. The
result goes into the write-up: "X% of apparent errors were label noise."

## 7. Files

| File | Responsibility | Status |
|---|---|---|
| `scripts/build_linked.py` | Reports + labels → `data/brca_linked.jsonl` | done |
| `reader.py` | OCR normalization, fact extraction with evidence and confidence | first pass (dev mean F1 0.52) |
| `criteria.py` | B1–B8, three-valued, with "why" | built |
| `evaluate.py` | All metrics in section 5; `--holdout` for the final run; `--errors <fact>` for dev error dumps | built (holdout not yet run) |
| `audit.py` | Disagreement sample for hand-checking | to build |

Standard library only, to match `criteria_search/`.

## 8. Results: first frozen run (2026-11-14)

Reader and calibration were frozen after dev work; holdout was scored once. Full output is in
`results_dev.txt` and `results_holdout.txt`.

| Holdout (n=521) | rules | naive | template |
|---|---|---|---|
| Mean F1, B1–B8 | 0.523 | **0.557** | ~0 |
| Accuracy when decided | 82–98% | 89–99% | — |
| ECE, hand-set confidences | 0.097 | — | — |
| ECE, DEV-fit confidences | **0.022** | — | — |

Findings:
- **Calibration generalizes.** Confidences fit on dev cut holdout ECE from 0.097 to 0.022.
  Answers in the 0.9–1.0 bin (1,466 of them) were right 98% of the time.
- **Fact reliability differs a lot.** ER, PR, stage and nodes are right 92–97% of the time
  when found; HER2 only 78%. Calibration exposes this automatically.
- **Recall is limited by coverage.** Receptors are mentioned in about 65% of reports, and
  extractable in about 40%.
- **The boilerplate filter and conflict handling cost more recall than they gain in
  precision.** The naive first-hit reader beats rules on F1 on both dev (0.534 vs 0.519) and
  holdout. Rules wins only where its derived logic matters: B6 node-positive (0.82 vs 0.72)
  and margin precision.
- **Audit** of 30 dev disagreements (suggested verdicts, not yet confirmed by a person):
  14 label noise, 11 reader errors, 2 metric artifacts, 1 threshold difference
  (old 10% ER cut-off), 1 not in report, 1 unclear. **About half of apparent errors are TCGA
  label noise**, so true reader accuracy is higher than reported.
- Reader errors cluster in three places:
  1. per-node "(0/1)" lines hiding a positive node elsewhere
  2. HER2 headings and cut-off text read as results
  3. mixed ductal/lobular histology

Next iteration (on dev; note that holdout has now been seen once):
- Loosen the boilerplate filter to skip only true definition clauses.
- Sum node counts across specimens.
- Handle mixed histology explicitly.
- Then the language-model reader behind the same interface.

## 9. Risks and open decisions

- **Language-model reader (open decision).** A model-based extractor would probably raise
  coverage and accuracy a lot on messy OCR. It needs an API key, and it means sending report
  text to an outside service. These are public, de-identified TCGA reports, but check
  hackathon rules and cost first. If it's added, it goes behind the same reader interface
  so it gets the same metrics and calibration.
- **Multiple specimens** (core biopsy plus resection, bilateral cancers): prefer the
  resection or final diagnosis; count conflicts.
- **Neoadjuvant cases (ypT/ypN):** gold pT may be clinical or pre-treatment, so flag these
  and report them separately.
- **Small classes:** only 79 positive margins and 197 lobular cases, so give each
  criterion's support count next to its metrics.
- **Generalization:** this is breast only, from one consortium's mix of hospitals. Don't
  claim beyond that.
