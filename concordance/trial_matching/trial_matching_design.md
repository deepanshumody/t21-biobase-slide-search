# Trial matching: Design

**Goal:** match each patient to **real** recruiting clinical trials using a *patient profile*:
the structured facts the pathology report establishes. Every patient × trial pair gets:
- a verdict: **eligible on available data**, **excluded**, or **undetermined**
- the trial lines it rests on: passed, failed, or unknown, each quoting the trial's own words
- a **completeness** figure: how much of the trial the pathology report alone can settle
- the **to-verify** list: what no pathology report contains (ECOG, labs, imaging, consent…)

Clinicians get a ranked list of candidates per trial.

*Naming:* this was first called "trial twins". It was renamed because "digital twin" usually
means a continuously updated model of a real patient, and this is a static profile built from
one report. On Biobase the patients are synthetic; only the trials are real.

Phase 1: Biobase synthetic patients (built, this doc). Phase 2: TCGA real reports. Phase 3:
Project Data Sphere enrolled patients as real positives, subject to its data terms.
Nothing here is for real enrollment decisions.

## 1. Pieces

```
report ──(patient_profile.py)──────────────────────▶ PROFILE  {organ, age band, sex, histology, pT/pN (+sub-letters),
                                                 nodes +/examined, grade, ER/ER%/PR/HER2, margin, LVI, PNI,
                                                 perforation, sarcomatoid, neoadjuvant, Lauren, Breslow, ulceration}
Paperclip search ─▶ candidates ─▶ Paperclip ctgov SQL (recruiting, interventional, adjuvant) ─▶ 10 trials
ClinicalTrials.gov API ─▶ eligibility text (trials/selected/) ─▶ hand-encoded rules (trials.py, quoted)
                                                  │
                         match.py: profile × trial → verdict + completeness + why + to-verify; ranked lists
```

- **Profile** (`patient_profile.py`): three builders with the same keys:
  - `report_profile`: from the report's final-diagnosis block, using `criteria_search/parse.py`.
    This is the profile we match with.
  - `truth_profile`: from the Biobase labels; used for validation.
  - `prose_profile`: from the gross and microscopic prose only. This is the stress test without the template.
- **Trial retrieval** (Paperclip, GXL's sponsor tool, connected as an MCP server):
  - `search` over `trials/us` with queries describing a **type of patient**, such as "adjuvant
    therapy HER2-positive gastric adenocarcinoma after D2 gastrectomy R0". There is one query per
    patient type (organ + stage + biomarkers), never per patient, and no report text is ever sent.
  - Paperclip also exposes the full **ClinicalTrials.gov relational database (AACT, schema
    `ctgov`)**. A SQL filter keeps trials that are `overall_status='Recruiting'`, interventional,
    Phase 2/3, and post-surgery: titles matching adjuvant / resected / postoperative, excluding
    neoadjuvant, metastatic, advanced and perioperative.
  - The search-plus-SQL combination fixed the first approach (keyword API fetch), which mostly
    returned metastatic and pre-surgery trials.
- **Trial rules** (`trials.py`; Python instead of the planned JSON, because some criteria are
  computed scores or stage tables). Each trial has:
  - `include` / `exclude`: (quote, rule), where the rule returns True, False, or None (the profile can't tell)
  - `needs`: items no pathology report can settle, shown as "to verify"

## 2. Verdict logic (same three-valued logic as Concordance)

- **excluded:** an inclusion rule fails, or an exclusion rule is met. The answer names the line.
- **eligible on available data:** every inclusion rule passes and no exclusion is met; the
  `needs` items remain to verify.
- **undetermined:** some rule can't be decided from the profile (e.g. pNX when the trial needs N0).
- **completeness** = rules decided ÷ (all rules + needs).
- **ranking** within a trial: eligible first, then by completeness, then fewest unknowns.

**Absence is not evidence.** A missing fact must give None, never False. Building the prose
profile exposed four places where my rules broke this, and each one wrongly excluded truly eligible
patients:
1. An unknown ER % was treated as 0%.
2. A node-positive status without the count was rounded down to N1.
3. An unknown specimen type was treated as "not a prostatectomy".
4. Prose describing cells without naming the tumor was treated as "not a carcinoma".

The fixes:
- `histology_has()` fails only when a **different** tumor type is named.
- The prose profile derives the N category from the positive-node count with AJCC cut-offs per organ.
- Stage tables try every sub-letter (pT4 → 4a and 4b) and decide only when all agree.

## 3. Validation on Biobase (train, 9,010 reports; `results/summary_train.md`)

1. **Extraction → decision.** Same verdict as the truth profile, over 12,096 patient × trial pairs:

   | Profile | Same verdict | Truth-eligible pairs kept eligible | Became undetermined | Wrongly excluded |
   |---|---|---|---|---|
   | report (template) | **100%** | 1,795 / 1,795 | 0 | 0 |
   | prose only | 27.6% | 7 / 1,795 | 1,788 | **0** (was 622 before the fixes above) |

   - The report profile is exact on Biobase, because the summary block is code-written. The number to
     re-measure is the same table on TCGA, where it won't be 100%.
   - The prose profile **fails safe**: it never wrongly excludes, but it can rarely decide, because the
     prose lacks T/N sub-letters, ER %, tumor site and the like.
2. **Trial encoding.** Every rule quotes its source line; the texts are in `trials/selected/`.
   An automatic-encoding check with Paperclip `map` is in `paperclip_map_check.md`: it recovered
   9 of 10 hand-encoded rules, missed 1, and made 1 unsupported claim (n = 2 trials). So
   automatic encoding needs a verbatim-quote check plus human review before use.

## 4. Trials (fetched 2026-11-14, all Recruiting)

| NCT | Organ | Pathology hinge | Eligible on available data (train) |
|---|---|---|---|
| NCT06757621 | breast | pT1-2 N1 (1–3 nodes), negative margins, **computed risk score ≤ 2** (inner quadrant, 2–3 nodes, LVI, stage) | 93 / 1,290 |
| NCT07237256 | breast | pT/pN/grade combinations, **ER ≥ 10%**, HER2− | 185 / 1,290 |
| NCT05797467 | colon | **pT3-4 N2** adenocarcinoma, age 18–75 | 102 / 887 |
| NCT05086614 | colon | high-risk stage II or stage III (ASSUMPTION: standard high-risk features) | 345 / 887 |
| NCT05487391 | lung | **AJCC 8th stage II–IIIB** from pT/pN, R0 | 411 / 1,265 |
| NCT07477626 | prostate | **pN1** after prostatectomy | 35 / 1,090 |
| NCT07366528 | stomach | **exact stage III T/N list**, R0, no neoadjuvant, Lauren | 391 / 909 |
| NCT04997837 | stomach | **pN3 with > 7 positive nodes**, R0 | 170 / 909 |
| NCT06661720 | kidney | clear cell; pT2 G4 / sarcomatoid / pT3 / pT4 N0, or N+ | 42 / 855 (149 undetermined: pNX) |
| NCT07581509 | skin | melanoma **stage IIB/IIC/III** (Breslow, ulceration, sentinel nodes); Phase 1, the only recruiting adjuvant trial for cutaneous melanoma found | 21 / 2,714 |

Mean completeness is 0.33–0.51: the pathology report settles about a third to a half of each
trial's criteria. The rest is the to-verify list.

## 5. Files

| File | Responsibility |
|---|---|
| `fetch_trials.py` | First-pass ClinicalTrials.gov keyword fetch → `trials/raw/` (kept for comparison) |
| `trials/selected/<NCT>.json` | The 10 chosen trials' eligibility text, status and fetch date |
| `trials.py` | Hand-encoded rules with quotes; stage tables; risk score |
| `patient_profile.py` | `report_profile`, `truth_profile`, `prose_profile` |
| `match.py` | Verdicts, completeness, validation table, ranked lists → `results/` (`--test` for the 979 test reports) |
| `paperclip_map_check.md` | Automatic eligibility extraction vs hand encoding |
| `trec/` | TREC CT 2021/22 topics + judgments (downloaded; not used: only 2 relevant patients) |

## 6. Risks and limits

- **Most trial criteria aren't in a pathology report** (ECOG, labs, imaging M0, prior therapy),
  so completeness stays below about 0.5. The to-verify list makes that explicit.
- **Biobase lacks Ki-67, PD-L1, EGFR/ALK, and M category.** Those criteria are always "to verify";
  Ki-67 makes pT2 pN0 grade 2 breast cases undetermined for NCT07237256.
- **Interpretation choices are marked ASSUMPTION** in `trials.py`: colon "high-risk stage II";
  "choroidal tumour thrombus" read as LVI; anatomic rather than prognostic breast stage.
- **No ground-truth eligibility exists for Biobase patients.** Validation covers extraction →
  decision and the encoding, not clinical eligibility. TREC has only 2 usable patients;
  Project Data Sphere is the real-positive source to pursue.
- **Hand encoding doesn't scale.** The path is Paperclip `map` drafts with quotes, an automatic
  verbatim-quote check, then human review.
