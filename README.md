# Team T21: Concordance

**Connecting patients to clinical trials through their pathology.**

- **Team ID:** T21
- **Sponsor prize:** Biobase ("Find the Right Patients"). Trial sourcing uses Paperclip by GXL, also a hackathon sponsor.
- **Repository visibility:** Private, for the team, organizers, and assigned judges.
- **Presentation:** [Concordance slides](https://claude.ai/artifact/XY5hSRqBuFLd6cMcEySKfF)
- **Evaluation questions (Biobase prize):** [`evaluation_questions.md`](evaluation_questions.md)

## Problem

Patients who could benefit from a clinical trial are often never offered one, and trial teams struggle
to enrol the patients they need. Matching is largely manual: staff read pathology reports and trial
criteria by hand, and much depends on who knows which trial. Most eligibility criteria for
post-surgery cancer trials (histology, stage, nodes, margins, receptors) are written in the pathology
report. We set out to read that pathology automatically, say clearly what it does and does not
establish, and match patients to trials that are recruiting now.

## What we built

| Part | Folder | What it does |
|---|---|---|
| 1. Criteria search (Task A) | [`concordance/criteria_search/`](concordance/criteria_search/) | Reads Biobase pathology reports into a structured fact card, then checks 30 plain-language criteria. Rule-based, so every answer traces back to a sentence in the report. |
| 2. Validation on real reports | [`concordance/concordance_breast/`](concordance/concordance_breast/), [`concordance/concordance_colon/`](concordance/concordance_colon/) | Tests the approach on 1,614 public TCGA pathology reports with curated labels. A reader rebuilt for real text answers "match", "no match" or "undetermined", with a calibrated confidence. |
| 3. Pathology slides (C1, C2) | [`biobase/`](biobase/) | C1 classifies each slide's organ from the supplied foundation-model embeddings (ensemble of three ridge classifiers). C2 finds similar slides by combining C1's organ evidence with GigaPath visual similarity. |
| 4. Trial matching | [`concordance/trial_matching/`](concordance/trial_matching/) | Finds recruiting trials on ClinicalTrials.gov with Paperclip (search plus SQL over the registry), encodes their eligibility as rules that quote the trial text, and matches each Biobase patient profile: eligible on available data, excluded (with the reason), or undetermined, plus a list of what remains to verify. |

Each folder has its own README or design document with methods, results and limitations.

## Results

All results below are internal estimates. Official challenge scores are pending.

| Part | Result |
|---|---|
| Task A | Mean F1 **1.00** over all 30 criteria on 9,010 labelled reports (keyword baseline 0.27). Test answers for 979 reports submitted. |
| Real reports (TCGA) | The Task A parser finds **0%** of facts on real reports, because it relies on Biobase's code-written summary block. The real-report reader, scored once on held-out patients, is right 82–98% (breast) and 95–100% (colon) of the time when it answers (mean F1 0.52 and 0.68; recall is limited by facts missing from the reports). Its confidence is calibrated: answers at ≥ 0.9 confidence were right 98% of the time. Run unchanged on Biobase, it scores **0.94** on 8 overlapping criteria. |
| C1 | **85.6%** organ accuracy (10× repeated cross-validation, 188 labelled slides). Strongest on colon and kidney (98%) and prostate (95%); weakest on "Other or mixed" (53%), bladder (66%) and small suppliers. |
| C2 | Precision at 1/5/10: **87.9 / 84.5 / 81.4%**, against 78.7 / 56.4 / 45.0% for GigaPath similarity alone. |
| Trial matching | 10 recruiting trials across all 7 Biobase organs; **1,795** patient–trial pairs eligible on available data from 9,010 reports. Profiles built from reports give the same verdict as profiles built from labels on all 12,096 decisions. A pathology report settles 33–51% of each trial's criteria. |

The nine evaluation questions in [`evaluation_questions.md`](evaluation_questions.md) test what these
headline numbers can hide: template dependence, guessing on missing facts, negation, thresholds,
equivocal biomarkers, rare organs and suppliers, report–slide disagreement, trial coverage, and
calibration. Each comes with our own answer and evidence.

## Run or view the demo

- **Presentation:** [Concordance slides](https://claude.ai/artifact/XY5hSRqBuFLd6cMcEySKfF), with two worked examples of a Biobase report matched to a recruiting trial.
- **Reports and trials:** see [`concordance/README.md`](concordance/README.md). Python 3 standard library only:

  ```bash
  cd concordance
  bash fetch_public_data.sh        # public TCGA and cBioPortal data (~100 MB, not in Git)
  ```

- **Slides (C1, C2):** see [`biobase/README.md`](biobase/README.md), the [C1 methods report](biobase/output/pdf/c1_methodology_report.pdf) and the [C2 methods report](biobase/docs/C2_RETRIEVAL.md).

## Limitations

- Biobase patients are synthetic, so there is no ground truth for trial eligibility. Trial matching demonstrates the method, not clinical eligibility, and is not for enrollment decisions.
- Biobase reports and slides are linked for only 57 slides.
- On real reports, recall is limited by facts the report never states (for example ER/PR in about 35% of breast reports).
- All scores above are internal; official challenge scores are pending.

## Data and permissions

Biobase challenge packs, slide images, embeddings and model weights are excluded from Git. See
[`biobase/docs/DATA_AND_ACCESS.md`](biobase/docs/DATA_AND_ACCESS.md). TCGA reports (TCGA-Reports, MIT
licence) and cBioPortal labels are public and re-downloadable with
[`concordance/fetch_public_data.sh`](concordance/fetch_public_data.sh). Trial records come from
ClinicalTrials.gov via Paperclip.

## Also in this repository

[`sequencing-signal-qc/`](sequencing-signal-qc/) is a separate entry: a filter decision review tool for
sequencing contamination QC. See its [README](sequencing-signal-qc/README.md).

## Event handoff

The [event handoff](biobase/README.md#event-handoff) records the submission requirements and deadline.
