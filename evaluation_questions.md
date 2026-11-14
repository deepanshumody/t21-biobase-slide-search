# Team T21: proposed evaluation questions for the Biobase challenge

Each question can be scored on the Biobase packs as released. Each also tests something a
plain F1 or accuracy score can hide. Under each one is our own answer, with the evidence file.

---

## Reports (Task A and beyond)

**1. Does the system still work without the code-written summary block?**
Biobase reports end in a final-diagnosis block written by code from the same fields as the answer
key, so a parser can score 1.0 by reading the template back. *Test:* hide the final-diagnosis block
and answer the 30 criteria from the gross and microscopic prose only. Report the drop.
*Ours:* train F1 1.000 with the block, 0.975 on a held-out half from the prose plus the header line,
0.875 from the prose alone (age, sex and year exist only in the header).
→ `concordance/criteria_search/criteria_search_design.md` §8

**2. When a report doesn't state a fact a criterion needs, does the system say "undetermined", or does it guess?**
Answering every criterion as yes/no hides guessing. *Test:* for each criterion, report how many
reports were left undetermined, and score correctness on the decided ones separately.
*Ours:* we use three answers (match / no match / undetermined). A stress test found four rules that
treated a missing fact as a failing one, wrongly excluding 622 eligible patient–trial pairs. After the
fix, 0 were wrongly excluded.
→ `concordance/trial_matching/trial_matching_design.md` §2–3

**3. Is negation read correctly for the criteria that require something to be absent (c07, c11, c13, c20)?**
Keyword search matches "lymphovascular invasion" in "Lymphovascular invasion: not identified".
*Test:* F1 on those four criteria compared with the keyword baseline.
*Ours:* 1.00 on all four (synthetic). On real TCGA colon reports, a negation bug ("Not identified"
read as "identified") was caught on the development half; fixing it raised perineural invasion
accuracy from 47% to 97%.

**4. Are thresholds applied exactly as worded, including at the boundary?**
"Within 3 mm" (c05), "5 cm or larger" (c13), "larger than 20 mm" (c04), "under 60" and "70 or older"
with **age bands** (c06, c29). *Test:* score only reports sitting at or next to each boundary (3 mm,
50 mm, 20 mm, band 50–59 / 60–69). How does the system treat an age band that straddles a trial's
age limit?
*Ours:* boundaries resolved from the training answers (e.g. ≤ 3 mm). For trial matching, a straddling
band (e.g. 70–79 vs "age 18–75") is "undetermined", not a pass.

**5. How are equivocal biomarkers handled?**
Biobase stomach reports include "HER2 equivocal (score 2+), in situ hybridization not amplified".
*Test:* are equivocal results counted as positive, negative, or undetermined, and does an ISH result
override the IHC score?
*Ours:* ISH decides when reported; otherwise equivocal = undetermined.

## Slides (C1 / C2)

**6. Does organ accuracy hold for rare organs and minor suppliers?**
67 held-out slides over 15 groups, with most slides from one supplier. *Test:* report accuracy per
organ group and per supplier, not only overall.
*Ours (C1, 10× repeated cross-validation):*
- overall 86%
- organs with ≥ 13 slides 87%, with < 13 slides 78%
- weakest groups: "Other or mixed" 53%, bladder 66%
- by supplier: SUPP-02 87%, SUPP-01 86%, SUPP-04 **72%**, SUPP-03 **37%** (only 6 and 3 slides)

→ `biobase/output/c1_improved/validation_predictions.csv`

**7. When the report's organ and the slide-predicted organ disagree, which one is wrong, and should it go to a person?**
Only the 57 labelled slides that carry their own report allow this test. *Test:* compare the organ
read from the report text with the out-of-sample slide prediction.
*Ours:* they agree on 49/57 and all 49 are correct. Of the 6 disagreements, the report was right in
5 and the slide in 0. So disagreement is a strong "send to review" signal, and the report should
win the tie.

## Real trials (beyond the 30 criteria)

**8. How much of a real trial's eligibility can a pathology report settle?**
*Test:* take recruiting trials from ClinicalTrials.gov, encode their eligibility, and report per
trial the share of criteria decidable from the report (completeness), plus how many patients are
eligible, excluded or undetermined.
*Ours:* 10 recruiting post-surgery trials across all 7 organs; completeness 0.33–0.51. Examples of
what's never in a pathology report: ECOG, labs, metastasis imaging, EGFR/ALK, Ki-67. Patient
profiles built from the report give the same verdict as profiles built from the labels on all
12,096 patient–trial decisions.
→ `concordance/trial_matching/results/summary_train.md`

**9. Does the stated confidence mean what it says on reports the system has never seen?**
*Test:* bin answers by confidence and compare with observed accuracy (expected calibration error) on
held-out reports. Biobase reports are too clean to test this, so we used real TCGA reports.
*Ours:* after fitting on one half and testing on the other, calibration error 0.022 (breast) and
0.011 (colon); answers at ≥ 0.9 confidence were right 98% of the time.
→ `concordance/concordance_breast/`, `concordance/concordance_colon/`

---

**Not proposed, and why:** "find every slide for patients who meet a criterion" and "one combined
report + slide confidence score" can't be scored on Biobase. Its reports and slides aren't linked,
except for the 57 slides with their own reports used in question 7. We'd suggest Biobase add
report–slide links in a future release, since that's what makes those questions testable.
