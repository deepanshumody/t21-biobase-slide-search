"""
CRITERIA (colon): C1-C8, three-valued, same logic as ../concordance_breast/criteria.py.
See concordance_colon_design.md, section 3.

Age is supplied separately from report text, with its source recorded in "why".
The evaluator uses TCGA clinical labels; cohort search uses explicit clinical.age metadata.
"""
CRITERIA = {
    "C1": ("Node positive (pN>=1)  [c08]",
           [("n_major", lambda v: v >= 1, "pN >= 1")]),
    "C2": ("Mucinous adenocarcinoma  [c09]",
           [("mucinous", lambda v: v is True, "mucinous")]),
    "C3": ("No positive nodes and LVI present  [c11]",
           [("n_major", lambda v: v == 0, "pN0"),
            ("lvi", lambda v: v is True, "LVI present")]),
    "C4": ("pT4  [c12]",
           [("t_major", lambda v: v == 4, "pT4")]),
    "C5": ("Perineural invasion present  [~c13]",
           [("pni", lambda v: v is True, "PNI present")]),
    "C6": ("Lymphovascular invasion present",
           [("lvi", lambda v: v is True, "LVI present")]),
    "C7": ("Age >= 70 and node positive  [c29]",
           [("age", lambda v: v >= 70, "age >= 70"),
            ("n_major", lambda v: v >= 1, "pN >= 1")]),
    "C8": ("Tumor left at resection (R1/R2)  [weak gold]",
           [("residual", lambda v: v is True, "R1/R2")]),
}


def evaluate_criterion(cid, get):
    _, conds = CRITERIA[cid]
    passed, why = [], []
    for fact, test, desc in conds:
        f = get(fact)
        if f is None:
            why.append(f"{desc}: unknown")
            continue
        value, conf, ev = f
        if not test(value):
            return {"answer": "no_match", "conf": conf, "why": [f"NOT {desc} ({value}) <- {ev}"]}
        passed.append(conf)
        why.append(f"{desc} ({value}) <- {ev}")
    if len(passed) == len(conds):
        return {"answer": "match", "conf": min(passed), "why": why}
    return {"answer": "undetermined", "conf": None, "why": why}


def answers_from_sheet(sheet, age=None, age_source="clinical metadata"):
    def get(fact):
        if fact == "age":
            return (age, 1.0, age_source) if age is not None else None
        f = sheet.get(fact)
        return (f["value"], f["conf"], f["evidence"]) if f else None
    return {cid: evaluate_criterion(cid, get) for cid in CRITERIA}


def answers_from_gold(gold):
    def get(fact):
        v = gold.get(fact)
        return (v, 1.0, "gold") if v is not None else None
    return {cid: evaluate_criterion(cid, get)["answer"] for cid in CRITERIA}
