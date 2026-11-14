"""
CRITERIA: fact sheet -> per criterion {answer: match|no_match|undetermined, conf, why}

Pipeline:  reader.py  ->  criteria.py  ->  evaluate.py
See concordance_breast_design.md, section 4.

Three-valued logic:
  match        every required fact is known and passes   conf = min(conf of those facts)
  no_match     some known fact fails (one failing fact settles it)   conf = conf of that fact
  undetermined otherwise (a needed fact is unknown)

Each criterion is a list of CONDITIONS, each (fact, test, description), all of which must hold.
The same definitions run on GOLD facts (plain values) to build the answer key, so the
reader and the key can never disagree about what a criterion means.
"""

ANY_HR_POS = "hr"  # pseudo-fact: ER or PR positive (handled below)

CRITERIA = {
    "B1": ("HER2 negative with >=1 positive lymph node (pN>=1)",
           [("her2", lambda v: v == "negative", "HER2 negative"),
            ("n_major", lambda v: v >= 1, "pN >= 1")]),
    "B2": ("ER positive and PR negative",
           [("er", lambda v: v == "positive", "ER positive"),
            ("pr", lambda v: v == "negative", "PR negative")]),
    "B3": ("Triple negative (ER-, PR-, HER2-)",
           [("er", lambda v: v == "negative", "ER negative"),
            ("pr", lambda v: v == "negative", "PR negative"),
            ("her2", lambda v: v == "negative", "HER2 negative")]),
    "B4": ("HR positive (ER+ or PR+) and HER2 negative",
           [(ANY_HR_POS, lambda v: v, "ER or PR positive"),
            ("her2", lambda v: v == "negative", "HER2 negative")]),
    "B5": ("Tumor pT2 or higher",
           [("t_major", lambda v: v >= 2, "pT >= 2")]),
    "B6": ("Node positive (pN>=1)",
           [("n_major", lambda v: v >= 1, "pN >= 1")]),
    "B7": ("Positive surgical margin",
           [("margin", lambda v: v == "positive", "margin positive")]),
    "B8": ("Invasive lobular carcinoma",
           [("histology", lambda v: v == "lobular", "lobular histology")]),
}


def _hr(get):
    """ER-or-PR-positive from two facts: True if either is positive, False if both negative, else unknown."""
    er, pr = get("er"), get("pr")
    vals = [x for x in (er, pr) if x is not None]
    if any(x[0] == "positive" for x in vals):
        x = max((x for x in vals if x[0] == "positive"), key=lambda x: x[1])
        return True, x[1], x[2]
    if er is not None and pr is not None:
        return False, min(er[1], pr[1]), f"{er[2]} | {pr[2]}"
    return None


def evaluate_criterion(cid, get):
    """`get(fact)` -> (value, conf, evidence) or None."""
    _, conds = CRITERIA[cid]
    passed, why = [], []
    for fact, test, desc in conds:
        f = _hr(get) if fact == ANY_HR_POS else get(fact)
        if f is not None and fact == "her2" and f[0] == "equivocal":
            f = None  # IHC 2+ without FISH: final HER2 status not reported -> unknown
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


def answers_from_sheet(sheet):
    """Reader output -> answers for B1-B8."""
    def get(fact):
        f = sheet.get(fact)
        return (f["value"], f["conf"], f["evidence"]) if f else None
    return {cid: evaluate_criterion(cid, get) for cid in CRITERIA}


def answers_from_gold(gold):
    """Gold facts (plain values) -> answer key. 'undetermined' here = gold unknown -> excluded from scoring."""
    def get(fact):
        v = gold.get(fact)
        return (v, 1.0, "gold") if v is not None else None
    return {cid: evaluate_criterion(cid, get)["answer"] for cid in CRITERIA}
