# Team T21: Biobase Slide Search

- **Team ID:** T21
- **Sponsor prize:** Biobase only, as the team's intended entry.
- **Project folder:** [biobase/](biobase/)
- **Repository visibility:** Private, for the team, organizers, and assigned judges.

All project code, reports, results, and experiment records are grouped in [`biobase/`](biobase/).
Start with the [full project README](biobase/README.md).

The report-side work (Task A criteria search, cohort export with evidence, and TCGA validation) is in [`concordance/`](concordance/); start with its [README](concordance/README.md).

## Problem

Classify pathology slides by organ (C1) and retrieve similar slides using organ evidence and visual similarity (C2).

## What we built

The project includes 67 C1 organ predictions and 670 C2 retrieval results, with reproducible evaluation and methodology reports.
Browse the [code](biobase/scripts/), [results](biobase/output/), [documentation](biobase/docs/), and [experiment records](biobase/evidence/).

## Run or view the demo

Read the [C1 methods report](biobase/output/pdf/c1_methodology_report.pdf), [one-page C2 summary](biobase/output/pdf/c2_summary.pdf), and [C2 methods report](biobase/docs/C2_RETRIEVAL.md).
Run project commands from the project folder:

```bash
cd biobase
```

Follow the [reproduction instructions](biobase/docs/REPRODUCIBILITY.md) to run checks or regenerate results with authorized challenge access.

## Evidence and limitations

C1 and C2 have internal validation results and artifact checks; official held-out scores remain unknown.
See the [results and limitations](biobase/README.md#evidence-and-limitations).

## Data and permissions

Restricted input packs, images, embeddings, and model weights are excluded from Git.
See [data access and repository contents](biobase/docs/DATA_AND_ACCESS.md).

## Next step

Score the submissions using the official evaluator and complete the Biobase evaluation-question contribution.
The [event handoff](biobase/README.md#event-handoff) records the submission requirements and deadline.
