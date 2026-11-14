# Can Paperclip `map` replace hand encoding of trial eligibility?

A small check (2026-11-14). We asked Paperclip's `map` (one LLM read per trial) to pull out the
pathology-verifiable eligibility items from a saved search: the gastric adjuvant result set
`s_665fc7ac`, top 4. Two of those trials are hand-encoded in `trials.py`, so they can be scored.
Paperclip map result id: `m_c8b80299`.

## Scored against the hand encodings

| Trial | Hand-encoded pathology rule | `map` output | Verdict |
|---|---|---|---|
| NCT07366528 | Age 18–80 | `age_min 18, age_max 80` | ✅ |
| | Adenocarcinoma of stomach / GEJ | quoted correctly | ✅ |
| | R0 resection | `R0` | ✅ |
| | No neoadjuvant therapy | `neoadjuvant_therapy_allowed: false` | ✅ |
| | Stage III: exact T/N list | full list quoted | ✅ |
| | "has Lauren classification" | **missing** | ❌ missed |
| NCT04997837 | D2/R0 resection | `R0` | ✅ |
| | Adenocarcinoma of stomach / GEJ | quoted correctly | ✅ |
| | > 7 positive nodes, pN3 | `pN3`, `more than 7` | ✅ |
| | Age ≥ 18 | `age_min 18` | ✅ |
| | (not in the trial text) | `neoadjuvant_therapy_allowed: false` | ⚠️ **unsupported**: the eligibility text never mentions neoadjuvant therapy |

**9 of 10 hand-encoded rules were recovered. 1 was missed, and 1 claim was made that the source doesn't support.**

Other observations from the same run:
- **NCT03961373 is itself a neo-adjuvant trial**: patients *receive* neoadjuvant chemotherapy.
  `map` still returned `neoadjuvant_therapy_allowed: false`, which is the wrong reading of a
  trial whose design depends on the opposite.
- The free-text fields mix pathology and non-pathology items (age shows up in both lists), and
  "min_positive_nodes" was answered with a stage list rather than a number. The output needs a
  strict schema before a matcher can consume it.

## Conclusion

`map` is fast (4 trials in 2.4 s) and gets most criteria right. It is **not safe to use
unreviewed**: one omission and one unsupported or contradictory claim per few trials is too many
for eligibility decisions. A workable scale-up path:
1. `map` drafts the rules, with quotes required.
2. Automatically reject any field whose quote isn't found verbatim in the eligibility text.
   That would have caught the unsupported NCT04997837 claim.
3. A person reviews the remaining rules, as we did by hand here.

The sample is n = 2 scored trials. Re-run on all 10 hand-encoded trials before trusting these numbers.
