"""
Build data/coadread_linked.jsonl: TCGA colorectal patients with a TCGA-Reports report
and cBioPortal `coadread_tcga` labels.   python3 build_linked.py
See concordance_colon_design.md, section 2.
"""
import collections
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
OUT = os.path.join(HERE, "data", "coadread_linked.jsonl")


def gold_facts(L):
    def major(code, letter):
        m = re.match(letter + r"(\d)", code or "")
        return int(m.group(1)) if m else None
    yn = lambda v: {"YES": True, "NO": False}.get((v or "").upper())
    hist = L.get("HISTOLOGICAL_DIAGNOSIS")
    rt = (L.get("RESIDUAL_TUMOR") or "").upper()
    npos = L.get("LYMPH_NODES_EXAMINED_HE_COUNT")
    return {
        "t_major": major(L.get("AJCC_TUMOR_PATHOLOGIC_PT"), "T"),
        "n_major": major(L.get("AJCC_NODES_PATHOLOGIC_PN"), "N"),
        "nodes_pos": int(npos) if npos and npos.isdigit() else None,
        "mucinous": ("mucinous" in hist.lower()) if hist else None,
        "lvi": yn(L.get("LYMPHOVASCULAR_INVASION_INDICATOR")),
        "pni": yn(L.get("PERINEURAL_INVASION")),
        "residual": {"R0": False, "R1": True, "R2": True}.get(rt),   # RX / missing -> unknown
        "age": int(L["AGE"]) if (L.get("AGE") or "").isdigit() else None,
        "site": (L.get("SITE_OF_TUMOR_TISSUE") or "").lower() or None,
    }


def main():
    labels = collections.defaultdict(dict)
    for x in json.load(open(os.path.join(RAW, "coadread_tcga_clinical_patient.json"))):
        labels[x["patientId"]][x["clinicalAttributeId"]] = x["value"]
    csv.field_size_limit(10 ** 8)
    n = 0
    with open(OUT, "w") as out:
        for r in csv.DictReader(open(os.path.join(RAW, "TCGA_Reports.csv"))):
            pid = r["patient_filename"][:12]
            if pid in labels:
                out.write(json.dumps({"id": pid, "report_text": r["text"], "gold": gold_facts(labels[pid])}) + "\n")
                n += 1
    print(f"wrote {n} -> {OUT}")


if __name__ == "__main__":
    main()
