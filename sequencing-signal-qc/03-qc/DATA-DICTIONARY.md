# Sequencing signal QC data dictionary

`data.json.gz` contains 293 labeled development examples in `train` and 3,425 held-out examples in `cases`. Each row describes one feature in one cohort.

| Field | Meaning |
| --- | --- |
| `id` | Feature record ID |
| `cohort` | Benchmark cohort |
| `sample_mass`, `control_mass` | Mean normalized feature signal in samples and controls |
| `sample_count`, `control_count` | Number of sample and control measurements |
| `sample_signals`, `control_signals` | Individual normalized measurements with record IDs |
| `target` | Reference label, included in the development set |

The review export includes signal retained and removed by the control-aware filter, its control ratio and status, a low-abundance flag, and the abundance-only filter’s keep decision.
