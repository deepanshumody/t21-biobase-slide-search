# Trial twins: planned extension

**Implementation status:** only `fetch_trials.py` and dated raw trial records are present.
Encoded trial rules, `twin.py`, `match.py`, and `validate.py` have not been implemented.
The working cohort-search prototype is documented in [the project README](../README.md).

**Goal:** match each patient to **real** recruiting clinical trials using a *digital twin*, a structured profile of what the pathology report establishes.
Every patient × trial pair gets:

- a verdict: **pathology criteria supported**, **excluded**, or **undetermined**
- the criteria it rests on, each with its evidence
- a **completeness** figure: how many of the trial's criteria the twin could check
- a confidence

Clinicians get, per trial, a ranked list of candidates, along with what's still to verify for each.

Phase 1: Biobase synthetic patients (this doc).
Phase 2: TCGA real reports.
Phase 3 (later): Project Data Sphere enrolled patients as real positives, subject to its data terms.

## 1. Pieces

```
report ──(criteria_search reader)──▶ TWIN  {organ, histology, pT, pN, nodes, ER/PR/HER2, LVI, margins, age, sex, ...}
                                                  │
ClinicalTrials.gov ──▶ TRIAL TEXT ──(hand-encoded, quoted)──▶ TRIAL RULES
                                                  │
                                    MATCH: twin × trial → verdict + completeness + why
```

- **Twin:** the existing fact card (`criteria_search/card.py`) plus demographics.
  Each fact keeps its source: report-derived or label-derived (for validation only).
- **Trials:** public ClinicalTrials.gov API v2.
  Only generic queries are sent (condition, status = recruiting, interventional); no patient data ever leaves the machine.
- **Trial rules** (`trials/<NCT id>.json`): each eligibility line becomes one of
  - **checkable** from the twin, e.g. `{"fact": "her2", "op": "==", "value": "negative", "quote": "<the trial's own sentence>"}`
  - **not checkable from pathology**, e.g. ECOG, prior therapy, lab values, consent.
    It is kept as `{"needs": "ECOG 0-1", "quote": ...}` and shown to the clinician as "to verify".

## 2. Verdict logic (same three-valued logic as Concordance)

- **excluded:** any checkable inclusion criterion fails, or an exclusion criterion is met.
  The answer names the failing line.
- **pathology criteria supported:** at least one pathology criterion is checkable and every checkable criterion passes.
  This is a partial evidence verdict, not confirmed trial eligibility.
  All "needs" items remain explicitly listed for verification.
- **undetermined:** a needed pathology fact is missing, or no pathology criteria can be checked, and no known criterion excludes the candidate.
- **completeness** = checkable criteria the twin could evaluate ÷ all criteria, including "needs".
  This tells the clinician how much of the trial the pathology report alone can settle.
- **ranking** within a trial: candidates with supported pathology criteria first, ordered by completeness, then confidence.

## 3. Validation on Biobase

Biobase has no trial-eligibility labels, so validation runs in two layers:

1. **Extraction → decision:** build each twin twice, from the report (reader) and from the labels (truth).
   Compare verdicts for every patient × trial pair, and report how many decisions change because of an extraction error.
   (We expect close to 0 on Biobase; this is the number to repeat on TCGA, where it won't be 0.)
2. **Trial encoding:** every rule carries the trial's quoted sentence.
   A person checks a sample of encodings against the trial text and reports how many are correct.

Clinical correctness of the trial choice itself is out of scope.
These are synthetic patients, and nothing here is for real enrollment decisions.

## 4. Trial selection (phase 1)

About 2 recruiting interventional trials per Biobase organ (breast, colon, lung, prostate, stomach, kidney, skin/melanoma).
Prefer trials whose inclusion criteria lean on **pathology** facts the twin holds, such as receptor status, stage, nodes or histology, so matching is meaningful.
Record the NCT id and the date fetched, since trial text changes over time.

## 5. Files

| File | Responsibility |
|---|---|
| `fetch_trials.py` | ClinicalTrials.gov API → `trials/raw/<NCT>.json` (eligibility text, status, date) |
| `trials/<NCT>.json` | Hand-encoded rules with quotes (reviewed) |
| `twin.py` | Report → twin (reuses `criteria_search`); labels → truth twin |
| `match.py` | Twin × trial → verdict, completeness, why; ranked list per trial |
| `validate.py` | Report-twin vs label-twin decision agreement; encoding-audit sample |

## 6. Risks

- **Most trial criteria aren't in a pathology report** (ECOG, labs, prior therapy).
  Expect low completeness.
  That's a real finding and the point of the "to verify" list, not a bug.
- **Biobase lacks fields some trials need**, e.g. PD-L1, Ki-67, mutation status (per the README).
  Those criteria become "needs".
- **Hand encoding doesn't scale.**
  A language-model encoder (with quotes, then human review) is the scale-up path.
  It's measured against the hand-encoded set.
