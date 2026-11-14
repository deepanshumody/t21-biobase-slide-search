# Filter Decision Review: Sequencing Signal QC

- **Team ID:** _add before submitting_
- **Sponsor prizes entered:** none

## Problem

Contamination filters decide which features of a sequencing run are kept as real signal and which are removed as contamination or noise. Two common filters disagree constantly. One compares each feature's signal in samples with its signal in negative controls. The other removes anything below a fixed abundance. When they disagree on a low-abundance feature, a researcher has no quick way to see why, or what to check before accepting either answer. In a biosecurity setting the costly mistake is silently dropping a rare organism that really is there.

A good result lets a researcher:
- see every feature's decision under both filters;
- see how much signal each filter keeps and removes;
- jump to the disagreements that matter most;
- inspect one feature's replicate-level evidence;
- record a decision with a reason that another reviewer can load and audit.

## What we built

`review_tool.py` runs the two filters that come with the starter, sorts every feature into a decision bucket, and writes one offline HTML report. It also writes a per-feature CSV. Python's standard library is all it needs.

| Bucket | Control-aware | Abundance-only | Meaning |
|---|---|---|---|
| Rare, recurring | keep | remove | Signal in ≥30% of sample replicates, weaker in controls. The rare real organism the cutoff would lose. |
| Rare, sparse | keep | remove | Signal in only one or two replicates. Likely noise or cross-talk. |
| Abundant but in controls | remove | keep | A reagent contaminant, or sample signal leaking into a control. |
| No sample signal | keep | remove | Zero signal in every sample. Control-aware keeps it only because 0 ÷ ~0 passes. |
| Agree: keep / Agree: remove | same | same | Low review priority. |

The report has:
- signal kept and removed per filter and cohort;
- bucket cards that filter the table;
- per-bucket accuracy on the labeled examples;
- a feature table sorted by review priority;
- an inspector with a plot of every sample and control replicate, a plain-language account of what each filter saw, and a "check next" list;
- Keep / Remove / Needs-more-evidence decisions with notes, exported to `decisions.csv` and loadable again;
- deep links (`report.html#<feature id>`), and a "What these data can and can't support" panel.

**Still incomplete:**
- Decisions live in the browser until exported. There is no shared server.
- The tool flags features for review but doesn't propose a better filter. We chose to compare only the two provided filters.

## Run or view the demo

**Quickest:** open [`docs/report.html`](docs/report.html) in any browser. It's prebuilt and works offline. Click **Open demo case**.

**To rebuild** (any Python 3, no installs):

```sh
python3 -I starter.py --route 03-qc --model baseline --output submission.json
python3 -I check_submission.py --route 03-qc --submission submission.json
python3 -I review_tool.py --route 03-qc --output docs/report.html
python3 -I test_review_tool.py -v
```

Add `--fixture` to `review_tool.py` for the 50-case trial set.

**Demo walkthrough:** feature `8900e5de778fde87`, cohort Rapid2 (`docs/report.html#8900e5de778fde87`).
1. Signal appears in 5 of 8 sample replicates and in 1 of 3 controls.
2. Control-aware: control mean 3.6e-3 vs sample mean 4.8e-3, ratio 0.74 is below 1, so **keep**.
3. Abundance-only: mean 4.8e-3 is 97% of the 0.005 cutoff, so **remove**.
4. The decision rests on a 3% abundance margin, and on one control replicate that could push the ratio past 1.
5. Check next: raw read counts, which control (extraction or PCR blank) carried the signal, and the sequence's taxonomy against the expected mixture.
6. On the labeled data, 13 of 15 features in this bucket are real. So "Needs more evidence", leaning keep, is the defensible call. Record that with a reason.

## Evidence and limitations

**Consistency with the starter.** `test_review_tool.py` passes 14 checks on both the fixture and the full set:
- both filters' keep decisions match `starter.py` for every feature;
- per-cohort retained and removed signal matches the `workflow.py` summary to 1e-9;
- every feature lands in exactly one bucket, and bucket counts sum to the case count;
- disagreement buckets really disagree, and the "No sample signal" bucket contains only zero-signal features.

**Held-out cases (3,425 features).**

| Bucket | Features |
|---|---|
| Rare, recurring | 442 |
| Rare, sparse | 2,485 |
| No sample signal | 237 |
| Agree: remove | 213 |
| Agree: keep | 35 |
| Abundant but in controls | 13 |

The filters disagree on 3,177 features (93%).

| Cohort | Control-aware keeps | Abundance-only keeps |
|---|---|---|
| Rapid1 | 99.9% of sample signal | 98.7% |
| Rapid2 | 70.5% | 90.5% |
| B | 90.1% | 88.8% |

**Which filter is right, by bucket.** 293 labeled features from cohort A, where 52 are real members of the known mixture.

| Bucket | Features | Real | Control-aware right | Abundance-only right |
|---|---|---|---|---|
| Rare, recurring | 15 | 13 | 13 (87%) | 2 (13%) |
| Rare, sparse | 218 | 17 | 17 (8%) | 201 (92%) |
| Abundant but in controls | 5 | 0 | 5 (100%) | 0 (0%) |
| Agree: keep | 32 | 21 | 21 (66%) | 21 (66%) |
| Agree: remove | 23 | 1 | 22 (96%) | 22 (96%) |
| **All** | 293 | 52 | 78 (27%) | 246 (84%) |

Neither filter is reliable on its own. Overall, abundance-only is right far more often. But in the "Rare, recurring" bucket, which is exactly the low-abundance disagreement this challenge is about, the control-aware filter is right 87% of the time. Replicate support is the clue that tells the two cases apart, so the tool puts it front and center.

**What this leaves unanswered:**
- **The labels cover only cohort A.** We have no ground truth for Rapid1, Rapid2 or B, so the accuracy table doesn't prove how the filters behave there.
- **The 30% "recurring" cutoff was chosen by looking at the labeled data.** It was not tuned on a held-out split. Cohort A has 23 sample replicates per feature, while the held-out cohorts have 8, so 30% means at least 3 of 8 there.
- **Feature IDs are hashed and there are no raw reads.** The tool can't name organisms, show read counts or show plate positions. The "check next" steps point to those sources but can't run them.
- **We did not usability-test the report with a researcher.**

## Data and permissions

- Processed feature tables from the [MicrobIEM known-mixture benchmark](https://doi.org/10.1186/s12915-023-01737-5) and [NASA OSD-890](https://doi.org/10.26030/2q5v-by72), as supplied in the DNAForge starter (`03-qc/`).
- The MicrobIEM article data and the NASA dataset are CC0. The MicrobIEM source repository is GPL-3.0 (`03-qc/GPL-3.0.txt`). See `03-qc/NOTICE.md`.
- No credentials, external services or network calls are used.

## Next step

Run the cohort A replicate analysis on a cohort with its own labels, holding out the cutoff choice. Specifically: measure whether "control-aware keep plus signal in ≥30% of replicates" still separates real from spurious low-abundance features when there are only 8 replicates. If it holds, replicate support should become a stated part of the review rule rather than just an inspector hint.
