"""
MATCH: profile x trial -> verdict, completeness, why. Plus validation and ranked lists.

    python3 match.py                # Biobase train (9,010 labelled reports) -> results/
    python3 match.py --test         # Biobase test (979 reports; report profile only, no truth)

Verdicts (trial_matching_design.md, section 2):
  excluded       an inclusion rule fails, or an exclusion rule is met (names the line)
  eligible       every inclusion rule passes, no exclusion met -> "eligible on available data";
                 the trial's `needs` list is what the clinician still has to verify
  undetermined   some rule can't be decided from the profile
completeness = rules the profile could decide / (all rules + needs)
"""
import collections
import json
import os
import sys

from trials import TRIALS
from patient_profile import prose_profile, report_profile, truth_profile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "criteria_search", "pack_reports")
OUT = os.path.join(HERE, "results")


def judge(profile, trial):
    passed, failed, unknown = [], [], []
    for quote, rule in trial["include"]:
        v = rule(profile)
        (passed if v is True else failed if v is False else unknown).append(quote)
    for quote, rule in trial["exclude"]:
        v = rule(profile)
        (failed if v is True else passed if v is False else unknown).append(("EXCLUSION: " + quote))
    n_rules = len(trial["include"]) + len(trial["exclude"])
    verdict = "excluded" if failed else ("undetermined" if unknown else "eligible")
    completeness = (len(passed) + len(failed)) / (n_rules + len(trial["needs"]))
    return {"verdict": verdict, "completeness": round(completeness, 3),
            "passed": passed, "failed": failed, "unknown": unknown, "to_verify": trial["needs"]}


def run(records, builders):
    """records -> {builder: {(patient_id, nct): judgement}} for trials matching the patient's organ."""
    out = {b: {} for b in builders}
    for r in records:
        for b, build in builders.items():
            tw = build(r)
            for nct, trial in TRIALS.items():
                if tw["organ"] == trial["organ"]:
                    out[b][(r["id"], nct)] = judge(tw, trial)
    return out


def summarize(res, records):
    by_trial = collections.defaultdict(collections.Counter)
    fail_reasons = collections.defaultdict(collections.Counter)
    comp = collections.defaultdict(list)
    for (pid, nct), j in res.items():
        by_trial[nct][j["verdict"]] += 1
        comp[nct].append(j["completeness"])
        for q in j["failed"]:
            fail_reasons[nct][q[:70]] += 1
    return by_trial, fail_reasons, comp


def ranked(res, nct, k=10):
    rows = [(pid, j) for (pid, t), j in res.items() if t == nct and j["verdict"] != "excluded"]
    order = {"eligible": 0, "undetermined": 1}
    rows.sort(key=lambda x: (order[x[1]["verdict"]], -x[1]["completeness"], len(x[1]["unknown"]), x[0]))
    return rows[:k]


def main(args):
    test = "--test" in args
    recs = [json.loads(l) for l in open(os.path.join(DATA, "test.jsonl" if test else "train.jsonl"))]
    builders = {"report": lambda r: report_profile(r["report_text"])}
    if not test:
        builders["truth"] = truth_profile
        builders["prose"] = lambda r: prose_profile(r["report_text"])
    res = run(recs, builders)
    os.makedirs(OUT, exist_ok=True)
    tag = "test" if test else "train"

    by_trial, fails, comp = summarize(res["report"], recs)
    lines = [f"# Trial matching: Biobase {tag} ({len(recs)} reports) x {len(TRIALS)} recruiting trials\n",
             "| Trial | Organ | Patients of that organ | Eligible on available data | Undetermined | Excluded | Mean completeness |",
             "|---|---|---|---|---|---|---|"]
    for nct, tr in TRIALS.items():
        c = by_trial[nct]
        n = sum(c.values())
        lines.append(f"| [{nct}](https://clinicaltrials.gov/study/{nct}) {tr['title'][:60]} | {tr['organ']} | {n} | "
                     f"{c['eligible']} | {c['undetermined']} | {c['excluded']} | {sum(comp[nct]) / max(1, n):.2f} |")
    lines.append("\n## Most common reasons for exclusion\n")
    for nct in TRIALS:
        top = "; ".join(f"{q} ({n})" for q, n in fails[nct].most_common(2))
        lines.append(f"- **{nct}**: {top}")

    if not test:
        lines.append("\n## Validation: do the decisions change with how the profile was built?\n")
        lines.append("| Profile source vs truth (labels) | Same verdict | Truth eligible → this profile eligible | Truth eligible → undetermined | Wrongly excluded |")
        lines.append("|---|---|---|---|---|")
        for b in ("report", "prose"):
            same = elig_kept = elig_und = wrong_ex = n_el = 0
            for key, jt in res["truth"].items():
                jb = res[b].get(key)
                if jb is None:
                    continue
                same += jb["verdict"] == jt["verdict"]
                if jt["verdict"] == "eligible":
                    n_el += 1
                    elig_kept += jb["verdict"] == "eligible"
                    elig_und += jb["verdict"] == "undetermined"
                    wrong_ex += jb["verdict"] == "excluded"
            n = len(res["truth"])
            lines.append(f"| {b} | {same / n:.1%} of {n} pairs | {elig_kept}/{n_el} | {elig_und}/{n_el} | {wrong_ex}/{n_el} |")

    lines.append("\n## Top candidates per trial (eligible first, then by completeness)\n")
    rank_dump = {}
    for nct, tr in TRIALS.items():
        rows = ranked(res["report"], nct)
        rank_dump[nct] = [{"patient": pid, **j} for pid, j in rows]
        lines.append(f"### {nct}: {tr['title']}")
        for pid, j in rows[:5]:
            unk = ("; unknown: " + "; ".join(u[:50] for u in j["unknown"])) if j["unknown"] else ""
            lines.append(f"- `{pid}` **{j['verdict']}** (completeness {j['completeness']:.2f}){unk}")
        lines.append(f"  - still to verify for every candidate: {'; '.join(tr['needs'][:4])}{' …' if len(tr['needs']) > 4 else ''}")
    open(os.path.join(OUT, f"summary_{tag}.md"), "w").write("\n".join(lines) + "\n")
    json.dump(rank_dump, open(os.path.join(OUT, f"ranked_{tag}.json"), "w"), indent=1)
    print("\n".join(lines[:30]))
    print(f"... full report: results/summary_{tag}.md")


if __name__ == "__main__":
    main(sys.argv[1:])
