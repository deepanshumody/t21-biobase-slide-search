# Trial matching: Biobase train (9010 reports) x 10 recruiting trials

| Trial | Organ | Patients of that organ | Eligible on available data | Undetermined | Excluded | Mean completeness |
|---|---|---|---|---|---|---|
| [NCT06757621](https://clinicaltrials.gov/study/NCT06757621) Hypofractionated postoperative regional nodal irradiation, p | breast | 1290 | 93 | 15 | 1182 | 0.51 |
| [NCT07237256](https://clinicaltrials.gov/study/NCT07237256) Chemotherapy de-escalation in HR+/HER2- intermediate-risk ea | breast | 1290 | 185 | 109 | 996 | 0.49 |
| [NCT05797467](https://clinicaltrials.gov/study/NCT05797467) Adjuvant chemotherapy ± targeted therapy, pT3-4N2 colorectal | colon | 887 | 102 | 23 | 762 | 0.40 |
| [NCT05086614](https://clinicaltrials.gov/study/NCT05086614) Thymosin-alpha 1 after radical resection of high-risk stage  | colon | 887 | 345 | 121 | 421 | 0.40 |
| [NCT05487391](https://clinicaltrials.gov/study/NCT05487391) QL1706 + platinum chemotherapy as adjuvant therapy, resected | lung | 1265 | 411 | 0 | 854 | 0.40 |
| [NCT07477626](https://clinicaltrials.gov/study/NCT07477626) Radiotherapy after prostatectomy for node-positive prostate  | prostate | 1090 | 35 | 0 | 1055 | 0.33 |
| [NCT07366528](https://clinicaltrials.gov/study/NCT07366528) Adjuvant SOX vs DS, stage III gastric cancer after D2 gastre | stomach | 909 | 391 | 18 | 500 | 0.45 |
| [NCT04997837](https://clinicaltrials.gov/study/NCT04997837) Adjuvant chemotherapy ± PD-1 inhibitor ± chemoradiotherapy,  | stomach | 909 | 170 | 0 | 739 | 0.40 |
| [NCT06661720](https://clinicaltrials.gov/study/NCT06661720) Pembrolizumab ± tivozanib, adjuvant after nephrectomy for in | kidney | 855 | 42 | 149 | 664 | 0.35 |
| [NCT07581509](https://clinicaltrials.gov/study/NCT07581509) Adjuvant pembrolizumab biosimilar (Bmab1800) vs Keytruda, re | skin | 2714 | 21 | 74 | 2619 | 0.38 |

## Most common reasons for exclusion

- **NCT06757621**: pT1-2N1M0 … 1-3 [ALND] / 1-2 [SLNB] metastatic lymph nodes, at least 1 (1096); ≥45 years old (96)
- **NCT07237256**: pT2 pN0 Grade 3 or pT2 pN0 Grade 2 with Ki67≥20% or pT0-2 pN1 or pT3-4 (852); ER-positive (with tumor cells showing ≥10% ER staining) (299)
- **NCT05797467**: Pathologically confirmed pT3-4N2 stage colorectal adenocarcinoma after (724); aged 18-75 years (195)
- **NCT05086614**: Pathologically diagnosed with high-risk stage II or stage III (254); [age] 18 to 75 Years (195)
- **NCT05487391**: Stage II-IIIB according to the 8th edition of the AJCC (829); had received radical surgical resection (R0) (49)
- **NCT07477626**: Radical prostatectomy with pelvic lymph node dissection and pathologic (1055)
- **NCT07366528**: AJCC stage IIIA (T2N3a, T3N2, …) … IIIC (… T4bN3b) (467); achieved R0 resection (59)
- **NCT04997837**: Positive lymph nodes more than 7, stage pN3 (727); Patients after standard D2/R0 resection (59)
- **NCT06661720**: Intermediate-high risk: pT2 grade 4 or sarcomatoid, N0M0; pT3 any grad (664)
- **NCT07581509**: Histologically confirmed melanoma that is completely surgically resect (2604); Male or female patients aged ≥18 years (42)

## Validation: do the decisions change with how the profile was built?

| Profile source vs truth (labels) | Same verdict | Truth eligible → this profile eligible | Truth eligible → undetermined | Wrongly excluded |
|---|---|---|---|---|
| report | 100.0% of 12096 pairs | 1795/1795 | 0/1795 | 0/1795 |
| prose | 27.6% of 12096 pairs | 7/1795 | 1788/1795 | 0/1795 |

## Top candidates per trial (eligible first, then by completeness)

### NCT06757621: Hypofractionated postoperative regional nodal irradiation, pT1-2N1 breast cancer
- `SYN-015f98b196` **eligible** (completeness 0.60)
- `SYN-0210c40608` **eligible** (completeness 0.60)
- `SYN-08629964f0` **eligible** (completeness 0.60)
- `SYN-09b89284f0` **eligible** (completeness 0.60)
- `SYN-0ef180b7e4` **eligible** (completeness 0.60)
  - still to verify for every candidate: no distant metastasis (M0): imaging, not pathology; ASSUMPTION: 'choroidal tumour thrombus' read as lymphovascular invasion; stage = AJCC anatomic; prior malignancy history; consent
### NCT07237256: Chemotherapy de-escalation in HR+/HER2- intermediate-risk early breast cancer
- `SYN-0169dd6651` **eligible** (completeness 0.50)
- `SYN-01c8049db5` **eligible** (completeness 0.50)
- `SYN-0210c40608` **eligible** (completeness 0.50)
- `SYN-02816921bd` **eligible** (completeness 0.50)
- `SYN-057262237c` **eligible** (completeness 0.50)
  - still to verify for every candidate: known menopausal status; Ki-67 for pT2 pN0 grade 2 (not in reports); ECOG 0-1; blood counts, renal and hepatic function …
### NCT05797467: Adjuvant chemotherapy ± targeted therapy, pT3-4N2 colorectal cancer
- `SYN-08b3ca138f` **eligible** (completeness 0.43)
- `SYN-11a0c11255` **eligible** (completeness 0.43)
- `SYN-13e4c2ebbb` **eligible** (completeness 0.43)
- `SYN-177ebf61bf` **eligible** (completeness 0.43)
- `SYN-1788be6150` **eligible** (completeness 0.43)
  - still to verify for every candidate: ASA < IV and/or ECOG ≤ 2; no other malignancy; organ function; consent
### NCT05086614: Thymosin-alpha 1 after radical resection of high-risk stage II / stage III colorectal cancer
- `SYN-04aa439f29` **eligible** (completeness 0.43)
- `SYN-0647b170d1` **eligible** (completeness 0.43)
- `SYN-06c2dd99ea` **eligible** (completeness 0.43)
- `SYN-0814a945e3` **eligible** (completeness 0.43)
- `SYN-08b3ca138f` **eligible** (completeness 0.43)
  - still to verify for every candidate: no distant metastasis (M0): imaging, not pathology; ECOG 0-2; hepatic, renal and hematologic function; no prior immune-promoting drugs
### NCT05487391: QL1706 + platinum chemotherapy as adjuvant therapy, resected stage II-IIIB NSCLC
- `SYN-0094376db5` **eligible** (completeness 0.40)
- `SYN-01ea4ff121` **eligible** (completeness 0.40)
- `SYN-0265327578` **eligible** (completeness 0.40)
- `SYN-02f86e3942` **eligible** (completeness 0.40)
- `SYN-031f1ea661` **eligible** (completeness 0.40)
  - still to verify for every candidate: no distant metastasis (M0): imaging, not pathology; non-squamous: no EGFR-sensitizing mutation or ALK fusion (not in reports); enrolled ≤ 70 days after surgery; ECOG 0-1 …
### NCT07477626: Radiotherapy after prostatectomy for node-positive prostate cancer
- `SYN-076b909150` **eligible** (completeness 0.33)
- `SYN-178a54fc06` **eligible** (completeness 0.33)
- `SYN-1e72212e6e` **eligible** (completeness 0.33)
- `SYN-27c452ac2b` **eligible** (completeness 0.33)
- `SYN-2aceb5f41b` **eligible** (completeness 0.33)
  - still to verify for every candidate: ECOG 0-2; postoperative ADT < 1 year if given; organ function; no measurable pelvic recurrence on MRI …
### NCT07366528: Adjuvant SOX vs DS, stage III gastric cancer after D2 gastrectomy
- `SYN-00e31cbf25` **eligible** (completeness 0.46)
- `SYN-016ffd5140` **eligible** (completeness 0.46)
- `SYN-019b1dee6e` **eligible** (completeness 0.46)
- `SYN-01a4f4eb18` **eligible** (completeness 0.46)
- `SYN-01f5d6589a` **eligible** (completeness 0.46)
  - still to verify for every candidate: D2 lymphadenectomy (extent of dissection not in reports); no distant metastasis (M0): imaging, not pathology; ECOG 0-1; organ function …
### NCT04997837: Adjuvant chemotherapy ± PD-1 inhibitor ± chemoradiotherapy, resected pN3 gastric/GEJ
- `SYN-00e31cbf25` **eligible** (completeness 0.40)
- `SYN-040321ffe5` **eligible** (completeness 0.40)
- `SYN-063836c0e7` **eligible** (completeness 0.40)
- `SYN-08837046ac` **eligible** (completeness 0.40)
- `SYN-0b78b803be` **eligible** (completeness 0.40)
  - still to verify for every candidate: D2 lymphadenectomy; M0 or M1 with CY1P0 only; ECOG 0-1; expected survival > 6 months …
### NCT06661720: Pembrolizumab ± tivozanib, adjuvant after nephrectomy for intermediate-high / high-risk RCC
- `SYN-0458fc2872` **eligible** (completeness 0.36)
- `SYN-227781d7c1` **eligible** (completeness 0.36)
- `SYN-2441591dd7` **eligible** (completeness 0.36)
- `SYN-24527374a1` **eligible** (completeness 0.36)
- `SYN-26169e7cc9` **eligible** (completeness 0.36)
  - still to verify for every candidate: no distant metastasis (M0): imaging, not pathology (or resected cM1 NED); surgery 4-16 weeks before registration; no prior systemic therapy; ECOG ≤ 2 …
### NCT07581509: Adjuvant pembrolizumab biosimilar (Bmab1800) vs Keytruda, resected stage IIB-III melanoma (Phase 1)
- `SYN-062361707b` **eligible** (completeness 0.50)
- `SYN-078968633b` **eligible** (completeness 0.50)
- `SYN-0be363b807` **eligible** (completeness 0.50)
- `SYN-13ebcf2256` **eligible** (completeness 0.50)
- `SYN-5368f03fdc` **eligible** (completeness 0.50)
  - still to verify for every candidate: ECOG 0-1; resection ≥ 28 days before consent; randomization ≤ 12 weeks after surgery; disease-free on imaging; no brain metastases; autoimmune disease, steroids, prior checkpoint therapy
