"""
Build data/brca_linked.jsonl: one line per TCGA-BRCA patient that has BOTH a
TCGA-Reports pathology report and cBioPortal clinical labels.

    python3 -I scripts/build_linked.py

Inputs (data/raw/, downloaded from public sources; see ../README.md):
  TCGA_Reports.csv               patient_filename, text   (Kefeli et al. 2024, MIT)
  brca_tcga_clinical_patient.json cBioPortal brca_tcga patient clinical data

Output record: {"id", "report_text", "labels": {raw TCGA fields}, "gold": {normalized facts}}
"gold" uses the same fact names as criteria_search/card.py where possible.
"""
import collections
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(HERE, "..", "data", "brca_linked.jsonl")

KEEP = ["ER_STATUS_BY_IHC", "PR_STATUS_BY_IHC", "IHC_HER2", "HER2_FISH_STATUS",
        "AJCC_TUMOR_PATHOLOGIC_PT", "AJCC_NODES_PATHOLOGIC_PN", "AJCC_PATHOLOGIC_TUMOR_STAGE",
        "LYMPH_NODES_EXAMINED_HE_COUNT", "LYMPH_NODE_EXAMINED_COUNT", "PATH_MARGIN",
        "HISTOLOGICAL_DIAGNOSIS", "AGE", "SEX"]


def status(v):
    v = (v or "").lower()
    return v if v in ("positive", "negative", "equivocal") else None


def her2_gold(ihc, fish):
    """Clinical HER2 call: IHC 3+ -> positive, IHC 0/1+ -> negative, IHC 2+ (equivocal) -> FISH decides."""
    ihc, fish = status(ihc), status(fish)
    if ihc == "positive" or fish == "positive":
        return "positive"
    if ihc == "negative" or (ihc == "equivocal" and fish == "negative"):
        return "negative"
    return "equivocal" if ihc == "equivocal" else None


def major(code, letter):
    m = re.match(letter + r"(\d)", code or "")
    return int(m.group(1)) if m else None


def gold_facts(L):
    hist = (L.get("HISTOLOGICAL_DIAGNOSIS") or "").lower()
    n_pos = L.get("LYMPH_NODES_EXAMINED_HE_COUNT")
    return {
        "er": status(L.get("ER_STATUS_BY_IHC")),
        "pr": status(L.get("PR_STATUS_BY_IHC")),
        "her2": her2_gold(L.get("IHC_HER2"), L.get("HER2_FISH_STATUS")),
        "t_major": major(L.get("AJCC_TUMOR_PATHOLOGIC_PT"), "T"),
        "n_major": major(L.get("AJCC_NODES_PATHOLOGIC_PN"), "N"),
        "nodes_pos": int(n_pos) if n_pos and n_pos.isdigit() else None,
        "margin": {"negative": "negative", "positive": "positive", "close": "close"}.get(
            (L.get("PATH_MARGIN") or "").lower()),
        "histology": ("ductal" if "ductal" in hist else "lobular" if "lobular" in hist
                      else "mucinous" if "mucinous" in hist else ("other" if hist else None)),
        "age": int(L["AGE"]) if (L.get("AGE") or "").isdigit() else None,
        "sex": {"female": "F", "male": "M"}.get((L.get("SEX") or "").lower()),
    }


def main():
    labels = collections.defaultdict(dict)
    for x in json.load(open(os.path.join(RAW, "brca_tcga_clinical_patient.json"))):
        if x["clinicalAttributeId"] in KEEP:
            labels[x["patientId"]][x["clinicalAttributeId"]] = x["value"]
    csv.field_size_limit(10 ** 8)
    n = 0
    with open(OUT, "w") as out:
        for r in csv.DictReader(open(os.path.join(RAW, "TCGA_Reports.csv"))):
            pid = r["patient_filename"][:12]
            if pid in labels:
                L = labels[pid]
                out.write(json.dumps({"id": pid, "report_text": r["text"],
                                      "labels": L, "gold": gold_facts(L)}) + "\n")
                n += 1
    print(f"wrote {n} linked patients -> {OUT}")


if __name__ == "__main__":
    main()
