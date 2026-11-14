# Criteria Search: Design

Task A of the Biobase challenge: for each of 30 plain-language criteria, list the
test reports that match it. Scored by mean F1 across criteria. Baseline (keyword
search) = 0.27.

## 1. Core idea

This is **select-all-that-apply**, not classification. Every report is checked
against every criterion independently; a report can match zero, one or many.

We do **not** train a model. The part of each report we need (title line,
SPECIMEN line, FINAL DIAGNOSIS block) is written by code from structured fields,
so its wording comes from a small fixed vocabulary. We:

1. **Parse** the report into labeled fields.
2. **Normalize** those fields into a simple "card" of typed facts
   (numbers, yes/no flags, short strings).
3. **Apply rules**: one small boolean function per criterion over the card.
4. **Validate** on the 9,010 labeled train reports against
   `criteria_train_answers.json`, fix mismatches, repeat.
5. **Run** on the 979 test reports and write the submission.

```
report_text
   │  parse.py      split title / SPECIMEN / FINAL DIAGNOSIS into {field: raw text}
   ▼
parsed report
   │  card.py       raw text → typed facts (er="positive", nodes_pos=3, lvi=False, size_mm=26 …)
   ▼
card
   │  rules.py      30 functions: card → True/False
   ▼
matches per criterion
   │  evaluate.py   (train) P/R/F1 per criterion + list of wrong ids + parser checks
   │  run.py        (test)  submission.json + vocabulary-drift report
```

## 2. Files

All code is in `criteria_search/`, and the data stays in `criteria_search/pack_reports/`.

| File | Responsibility | Change it when… |
|---|---|---|
| `parse.py` | Text → `{organ, sex, age_band, year, specimen, fields{}}` | a field is mis-split or missed |
| `card.py` | Fields → typed facts | a value is read wrong (e.g. a new wording for "absent") |
| `rules.py` | One rule per criterion, plus a note on each interpretation choice | a criterion is interpreted wrong |
| `evaluate.py` | Train scoring, error dump, parser self-checks | you want new diagnostics |
| `run.py` | Test → `submission.json`; flags wording never seen in train | — |

Standard library only. Python 3.9+.

## 3. Parsing (`parse.py`)

Report layout (fixed):

```
SURGICAL PATHOLOGY REPORT (SYNTHETIC; NOT A REAL PATIENT)
Patient: F, age band 50-59 | Report year: 2022
SPECIMEN: Breast, right, lumpectomy
FINAL DIAGNOSIS:  <block>
GROSS DESCRIPTION: ...          ← LLM prose, ignored
MICROSCOPIC DESCRIPTION: ...    ← LLM prose, ignored
```

- **Demographics** come from a regex on the `Patient:` line.
- **Organ** comes from keywords in the SPECIMEN line (`breast`, `colon`, `lung`, …), and is
  checked against `labels.organ` on train.
- **The FINAL DIAGNOSIS block** comes in two layouts: one field per line, or all fields
  on one line joined by `; `. Values themselves may contain `;`, as in Margins and
  Biomarkers, so we **do not split on `;`**. Instead:
  - We build a regex of every known field name from the README, with longest names
    first so that `Pathologic stage (AJCC 8th ed.)` wins over `Pathologic stage` and
    `Depth of invasion` wins over `Depth`.
  - A field starts where `<Name>:` appears at the start of the block, after a newline,
    or after `; `.
  - A field's value runs until the next field start.
  - Any text before the first labeled field is the unlabeled **Diagnosis** line, which
    skin reports have.
- **Self-check:** `evaluate.py` compares the parsed fields with `labels.diagnosis` on
  train and reports the exact-match rate.

## 4. The card (`card.py`)

| Fact | Source field | Normalization |
|---|---|---|
| `organ`, `sex`, `year` | title / SPECIMEN | as is |
| `age_min` | age band | `"70-79"`→70, `"90+"`→90 |
| `er`, `pr`, `her2` | Biomarkers (breast), HER2 (stomach) | `positive` / `negative` / `equivocal` / None |
| `nodes_pos` | Lymph nodes | int from `"X of Y positive"`; None if no nodes |
| `t_cat`, `n_cat` | Pathologic stage | `"pT4a pN1b"` → `t_cat="4a"`, `n_cat="1b"`; `t_major=4`, `n_major=1` |
| `size_mm` | Tumor size | cm×10 or mm |
| `lvi`, `pni`, `deposits`, `vpi`, `svi`, `sarcomatoid`, `epe` | the matching field | `present(...)` → True/False/None (see below) |
| `multifocal` | Tumor focality | starts with "multifocal" |
| `nottingham`, `grade_group`, `isup`, `scc_grade` | grade fields / skin Diagnosis | int |
| `histology` | Histologic type, or skin Diagnosis | lowercased string |
| `margins` | Margins | lowercased raw text, plus breast `margin_neg` and `margin_mm` |
| `depth`, `extent` | Depth of invasion / Extent of invasion | lowercased raw text |

**Present or absent.** `present()` reads a value as follows: `not identified` and
`absent` → False; `present` and `identified` → True; anything else, or a missing field →
None. Rules treat None as "does not match". The difference between None and False is
what lets rules tell "the report says no" apart from "the report doesn't say".

## 5. Rules (`rules.py`)

One function per criterion. Each one first checks the organ, then the conditions.
Choices that the criterion text leaves unclear are marked `# ASSUMPTION:` in the
code and settled by the train F1:

| Criterion | Open question | First guess |
|---|---|---|
| c01 | Does HER2 "equivocal, ISH not amplified" count as negative? | no, only "negative" |
| c05 | "within 3 mm": ≤3 or <3? | ≤3 |
| c06 | "under 60" with age bands | bands whose top is below 60 |
| c08 / c29 | node-positive = positive nodes ≥1, or pN ≥1 (includes pN1c deposits)? | pN ≥1 |
| c11 | "no positive lymph nodes" = 0 positive nodes, or pN0? | 0 positive nodes |
| c12 / c23 | pT4 from the stage line, or from the depth text? | stage line |
| c26 | Do segmental branches of the renal vein count? | yes (any "renal vein" text) |
| c27 | Deep margin involved, read from the Margins field only | Margins only |

## 6. Validation loop (`evaluate.py`)

```
python3 evaluate.py            # all criteria
python3 evaluate.py c05 c26    # details for selected criteria
```

It prints:
1. **Parser health**: organ accuracy, and the share of train reports whose parsed
   fields exactly match `labels.diagnosis`, with a few example differences.
2. **Score per criterion**: TP / FP / FN, precision, recall, F1, and the mean F1.
3. **Error dump** for the selected criteria (or any with F1 < 1): each FP and FN id
   with the card facts that rule uses, so you can see why it was wrong.

To improve: find the lowest F1 → read its dump → fix `card.py` (misread) or
`rules.py` (wrong interpretation) → rerun.

## 7. Submission (`run.py`)

```
python3 run.py                 # writes submission.json
```

- Writes `{"cNN": {"ids": [...], "count": N}}` for all 30 criteria. A count costs
  nothing to add, and it also scores on the count metric.
- **Drift check:** for each field, the value with digits replaced by `#` is compared
  against all values seen in train, and any test value never seen in train is
  printed. Those are the places where a rule could silently miss, so review them by
  hand.

## 8. Experiment: how much depends on the template?

`prose_card.py` builds the same card from the gross and microscopic prose only. The
FINAL DIAGNOSIS block is never read, and the same `rules.py` runs on the result.
`prose_experiment.py` splits train by md5(id) into dev and holdout halves. The prose
reader was developed on dev only; holdout was scored once at the end.

| Reader | Dev F1 | Holdout F1 |
|---|---|---|
| Template (main system) | 1.000 | 1.000 (not a clean holdout: rules were written with all of train in view) |
| Prose + header | 0.974 | **0.975** |
| Prose + header + 2 morphology rules | 0.991 | **0.987** |
| Prose only (no header) | 0.874 | **0.875** |

Findings:
- Nearly every fact the rules need is also stated in the prose, in free wording.
  Simple negation handling (`polarity()`) recovers lymphovascular invasion,
  perineural invasion and similar findings at over 98% agreement with the template.
- **Age, sex and year exist only in the code-written header.** Without it, c06, c29
  and c30 score 0.
- **Some prose describes cells without naming the tumor.** This happens for basal cell
  carcinoma (c27) and clear cell renal carcinoma (c24). Two morphology rules,
  "basaloid + palisading → BCC" and "kidney + clear cytoplasm → clear cell RCC",
  recover most of it.
- **Caveat:** the prose was written by a language model from the same structured fields, so
  its wording is narrower than real pathology reports. 0.975 is an upper bound for real data.

## 9. Known risks / future improvements

- **Wording found only in test** → caught by the drift check; extend `card.py`.
- **Fields missing from the block** → we could fall back to narrow regexes on the
  GROSS/MICROSCOPIC prose. Not built in the first try; add it only if the drift
  check or train errors show it's needed.
- **Unclear criteria** whose train answers look internally inconsistent → choose the
  reading with the highest train F1, and note it in `rules.py`.
