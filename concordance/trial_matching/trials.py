"""
TRIAL RULES: 10 real recruiting trials, hand-encoded from their eligibility text.

Source text: trials/selected/<NCT>.json (ClinicalTrials.gov API v2, fetched 2026-11-14;
found via Paperclip search + the ctgov SQL tables). See trial_matching_design.md, section 4.

Each trial has:
  include : [(quote, rule)]   rule(profile) -> True (passes) / False (fails) / None (profile can't tell)
  exclude : [(quote, rule)]   rule(profile) -> True (patient is excluded) / False / None
  needs   : [quote]           criteria a pathology report can never settle (ECOG, labs, consent...)
Quotes are the trial's own words (trimmed), so every rule can be checked against its source.
Rules use only the profile; any interpretation choice is marked ASSUMPTION.
"""


# ---------------------------------------------------------------------------
# Helpers (three-valued: True / False / None)
# ---------------------------------------------------------------------------
def age_between(lo=None, hi=None):
    """Age bands: pass if the whole band is inside, fail if wholly outside, else None."""
    def rule(t):
        a, b = t["age_lo"], t["age_hi"]
        if a is None:
            return None
        inside = (lo is None or a >= lo) and (hi is None or b <= hi)
        outside = (lo is not None and b < lo) or (hi is not None and a > hi)
        return True if inside else False if outside else None
    return rule


def eq(key, *vals):
    return lambda t: None if t[key] is None else t[key] in vals


def is_true(key):
    return lambda t: None if t[key] is None else bool(t[key])


def is_false(key):
    return lambda t: None if t[key] is None else not t[key]


def all_of(*rules):
    def rule(t):
        out = [r(t) for r in rules]
        return False if False in out else (None if None in out else True)
    return rule


def any_of(*rules):
    def rule(t):
        out = [r(t) for r in rules]
        return True if True in out else (None if None in out else False)
    return rule


def tn(t_ok, n_ok):
    """Combine T and N tests; N unknown (pNX / not examined) -> None."""
    def rule(t):
        if t["t_cat"] is None or t["n_cat"] is None:
            return None if (t["t_cat"] is None or t_ok(t["t_cat"])) else False
        return t_ok(t["t_cat"]) and n_ok(t["n_cat"])
    return rule


def histology_has(pattern, known_other=r"sarcoma|lymphoma|melanoma|neuroendocrine|small cell"):
    """True if the named type is present, False only if a DIFFERENT tumour type is named, else None.
    (Absence of a name is not evidence: prose may describe cells without naming the tumour.)"""
    def rule(t):
        h = t["histology"] or ""
        if re.search(pattern, h, re.I):
            return True
        return False if re.search(known_other, h, re.I) else None
    return rule


T = lambda c: int(c[0]) if c and c[0].isdigit() else (0 if c == "is" else -1)   # '4a' -> 4
N = lambda c: int(c[0]) if c and c[0].isdigit() else -1
M0 = "no distant metastasis (M0): imaging, not pathology"


# ---------------------------------------------------------------------------
# Stage tables (AJCC 8th, anatomic, from pT/pN only; M assumed 0 and listed as a need)
# ---------------------------------------------------------------------------
def lung_stage(t):
    tc, nc = t["t_cat"], t["n_cat"]
    if tc is None or nc is None:
        return None
    n = N(nc)
    tk = "1" if tc.startswith("1") else ("2a" if tc == "2a" or tc == "2" else "2b" if tc == "2b" else tc[0])
    table = {("1", 0): "IA", ("2a", 0): "IB", ("2b", 0): "IIA", ("1", 1): "IIB", ("2a", 1): "IIB", ("2b", 1): "IIB",
             ("3", 0): "IIB", ("1", 2): "IIIA", ("2a", 2): "IIIA", ("2b", 2): "IIIA", ("3", 1): "IIIA",
             ("4", 0): "IIIA", ("4", 1): "IIIA", ("1", 3): "IIIB", ("2a", 3): "IIIB", ("2b", 3): "IIIB",
             ("3", 2): "IIIB", ("4", 2): "IIIB", ("3", 3): "IIIC", ("4", 3): "IIIC"}
    return table.get((tk, n))


GASTRIC_III = {"2-3a", "3-2", "4a-1", "4a-2", "4b-0", "1-3b", "2-3b", "3-3a", "4a-3a", "4b-1", "4b-2",
               "3-3b", "4a-3b", "4b-3a", "4b-3b"}


def gastric_stage_iii(t):
    """Exact T/N combinations listed in NCT07366528's inclusion criterion 4."""
    tc, nc = t["t_cat"], t["n_cat"]
    if tc is None or nc is None:
        return None
    # A category without its sub-letter (e.g. prose says "pT4", not "pT4a") -> try every sub-letter;
    # decide only if they all agree.
    t_opts = ["4a", "4b"] if tc == "4" else [tc if tc in ("4a", "4b") else tc[0]]
    n_opts = ["3a", "3b"] if nc == "3" else [nc if nc in ("3a", "3b") else nc[0]]
    hits = {f"{a}-{b}" in GASTRIC_III for a in t_opts for b in n_opts}
    return hits.pop() if len(hits) == 1 else None


def breast_anatomic_stage(t):
    tc, nc = t["t_cat"], t["n_cat"]
    if tc is None or nc is None:
        return None
    tt, n = T(tc), N(nc)
    if n == 1 and nc != "1mi":
        return {0: "IIA", 1: "IIA", 2: "IIB", 3: "IIIA"}.get(tt)
    return None


def nodal_rni_risk_score(t):
    """NCT06757621 risk score: inner quadrant (1), 2-3 positive nodes (1), tumour thrombus (1),
    stage IB-IIA (1) / IIB-IIIA (2). Age <=40 can't score here (trial requires >= 45)."""
    stage = breast_anatomic_stage(t)
    if stage is None or t["nodes_pos"] is None or t["lvi"] is None or t["tumor_site"] is None:
        return None
    return (("inner" in t["tumor_site"]) + (2 <= t["nodes_pos"] <= 3) + bool(t["lvi"])
            + (1 if stage in ("IB", "IIA") else 2))


def melanoma_stage(t):
    """AJCC 8th: IIB = T3b/T4a N0, IIC = T4b N0, III = N+. N unknown (pNX) -> None unless N+."""
    tc, nc = t["t_cat"], t["n_cat"]
    if nc is not None and N(nc) >= 1:
        return "III"
    if tc is None or nc is None:
        return None
    return {"3b": "IIB", "4a": "IIB", "4b": "IIC"}.get(tc, "other")


def colon_high_risk_ii_or_iii(t):
    """ASSUMPTION: high-risk stage II = pT3-4 N0 with any of pT4, LVI, PNI, perforation, G3, <12 nodes."""
    if t["n_cat"] is None or t["t_cat"] is None:
        return None
    if N(t["n_cat"]) >= 1:
        return True
    if T(t["t_cat"]) < 3:
        return False
    flags = [T(t["t_cat"]) == 4, t["lvi"], t["pni"], t["perforation"], (t["grade"] or 0) >= 3,
             (t["nodes_exam"] is not None and t["nodes_exam"] < 12)]
    if any(f is True for f in flags):
        return True
    return None if any(f is None for f in flags) else False


# ---------------------------------------------------------------------------
# The trials
# ---------------------------------------------------------------------------
TRIALS = {
    "NCT06757621": {
        "organ": "breast", "title": "Hypofractionated postoperative regional nodal irradiation, pT1-2N1 breast cancer",
        "include": [
            ("≥45 years old", age_between(45, None)),
            ("Receiving breast-conserving surgery or total mastectomy and axillary lymph node dissection or sentinel lymph node biopsy",
             lambda t: None if t["nodes_exam"] is None else t["nodes_exam"] > 0),
            ("Negative surgical margins", eq("margin", "negative")),
            ("patients without neoadjuvant chemotherapy", is_false("neoadjuvant")),
            ("pT1-2N1M0 … 1-3 [ALND] / 1-2 [SLNB] metastatic lymph nodes, at least 1 lymph node with macroscopic metastasis",
             lambda t: None if t["t_cat"] is None or t["n_cat"] is None or t["nodes_pos"] is None else
             (1 <= T(t["t_cat"]) <= 2 and t["n_cat"] in ("1", "1a") and
              1 <= t["nodes_pos"] <= (2 if t["sentinel"] else 3))),
            ("a score of 0-2 according to the following risk factors … (inner quadrant, 2-3 nodes, tumour thrombus, stage)",
             lambda t: None if nodal_rni_risk_score(t) is None else nodal_rni_risk_score(t) <= 2),
        ],
        "exclude": [],
        "needs": [M0, "ASSUMPTION: 'choroidal tumour thrombus' read as lymphovascular invasion; stage = AJCC anatomic",
                  "prior malignancy history", "consent"],
    },
    "NCT07237256": {
        "organ": "breast", "title": "Chemotherapy de-escalation in HR+/HER2- intermediate-risk early breast cancer",
        "include": [
            ("Patient is ≥ 18 years old", age_between(18, None)),
            ("Patient is female", eq("sex", "F")),
            ("pT2 pN0 Grade 3 or pT2 pN0 Grade 2 with Ki67≥20% or pT0-2 pN1 or pT3-4 pN0",
             lambda t: None if t["t_cat"] is None or t["n_cat"] is None else
             (True if (T(t["t_cat"]) == 2 and N(t["n_cat"]) == 0 and t["grade"] == 3)
              or (T(t["t_cat"]) <= 2 and N(t["n_cat"]) == 1) or (T(t["t_cat"]) >= 3 and N(t["n_cat"]) == 0)
              else None if (T(t["t_cat"]) == 2 and N(t["n_cat"]) == 0 and t["grade"] == 2)   # Ki-67 not reported
              else False)),
            ("ER-positive (with tumor cells showing ≥10% ER staining)",
             lambda t: None if t["er"] is None else False if t["er"] != "positive" else
             (None if t["er_pct"] is None else t["er_pct"] >= 10)),
            ("HER2-negative according to the most recent ASCO/CAP guidelines", eq("her2", "negative")),
            ("Curative surgery … with negative surgical margins (or revision surgery planned)",
             lambda t: None if t["margin"] is None else (True if t["margin"] == "negative" else None)),
        ],
        "exclude": [],
        "needs": ["known menopausal status", "Ki-67 for pT2 pN0 grade 2 (not in reports)", "ECOG 0-1",
                  "blood counts, renal and hepatic function", "QTcF < 450 ms", "chemotherapy eligible per investigator"],
    },
    "NCT05797467": {
        "organ": "colon", "title": "Adjuvant chemotherapy ± targeted therapy, pT3-4N2 colorectal cancer",
        "include": [
            ("aged 18-75 years", age_between(18, 75)),
            ("Pathologically confirmed pT3-4N2 stage colorectal adenocarcinoma after surgery",
             all_of(histology_has(r"adenocarcinoma"),
                    tn(lambda c: T(c) in (3, 4), lambda c: N(c) == 2))),
        ],
        "exclude": [("Patients with emergent surgery due to intestinal obstruction, int[estinal perforation]…",
                     is_true("perforation"))],
        "needs": ["ASA < IV and/or ECOG ≤ 2", "no other malignancy", "organ function", "consent"],
    },
    "NCT05086614": {
        "organ": "colon", "title": "Thymosin-alpha 1 after radical resection of high-risk stage II / stage III colorectal cancer",
        "include": [
            ("Colorectal cancer receiving radical resection", lambda t: None if t["margin"] is None else t["margin"] == "negative"),
            ("Pathologically diagnosed with high-risk stage II or stage III", colon_high_risk_ii_or_iii),
            ("[age] 18 to 75 Years", age_between(18, 75)),
        ],
        "exclude": [],
        "needs": [M0, "ECOG 0-2", "hepatic, renal and hematologic function", "no prior immune-promoting drugs"],
    },
    "NCT05487391": {
        "organ": "lung", "title": "QL1706 + platinum chemotherapy as adjuvant therapy, resected stage II-IIIB NSCLC",
        "include": [
            ("Histopathologically confirmed squamous or non-squamous non-small cell lung cancer",
             histology_has(r"carcinoma", r"small cell|sarcoma|lymphoma|carcinoid")),
            ("Stage II-IIIB according to the 8th edition of the AJCC", lambda t: None if lung_stage(t) is None else
             lung_stage(t) in ("IIA", "IIB", "IIIA", "IIIB")),
            ("had received radical surgical resection (R0)", lambda t: None if t["margin"] is None else t["margin"] == "negative"),
            ("[age] 18 Years and older", age_between(18, None)),
        ],
        "exclude": [],
        "needs": [M0, "non-squamous: no EGFR-sensitizing mutation or ALK fusion (not in reports)",
                  "enrolled ≤ 70 days after surgery", "ECOG 0-1", "contraception", "consent"],
    },
    "NCT07477626": {
        "organ": "prostate", "title": "Radiotherapy after prostatectomy for node-positive prostate cancer",
        "include": [
            ("Age ≥ 18 years", age_between(18, None)),
            ("Histologically confirmed adenocarcinoma of the prostate", histology_has(r"adenocarcinoma")),
            ("Radical prostatectomy with pelvic lymph node dissection and pathologically confirmed positive pelvic lymph nodes",
             lambda t: None if t["n_cat"] is None else False if N(t["n_cat"]) == 0 else
             (None if not t["specimen"] else "prostatectomy" in t["specimen"])),
        ],
        "exclude": [],
        "needs": ["ECOG 0-2", "postoperative ADT < 1 year if given", "organ function", "no measurable pelvic recurrence on MRI",
                  "contraception", "consent"],
    },
    "NCT07366528": {
        "organ": "stomach", "title": "Adjuvant SOX vs DS, stage III gastric cancer after D2 gastrectomy",
        "include": [
            ("age 18 to 80 years old", age_between(18, 80)),
            ("histologically confirmed adenocarcinoma of the stomach or gastroesophageal junction",
             histology_has(r"adenocarcinoma|poorly cohesive carcinoma")),
            ("achieved R0 resection", lambda t: None if t["margin"] is None else t["margin"] == "negative"),
            ("had no systemic therapy like neoadjuvant therapy", is_false("neoadjuvant")),
            ("AJCC stage IIIA (T2N3a, T3N2, …) … IIIC (… T4bN3b)", gastric_stage_iii),
            ("and has Lauren classification", is_true("lauren")),
        ],
        "exclude": [],
        "needs": ["D2 lymphadenectomy (extent of dissection not in reports)", M0, "ECOG 0-1", "organ function",
                  "contraception", "consent", "no other primary malignancy"],
    },
    "NCT04997837": {
        "organ": "stomach", "title": "Adjuvant chemotherapy ± PD-1 inhibitor ± chemoradiotherapy, resected pN3 gastric/GEJ",
        "include": [
            ("Patients after standard D2/R0 resection", lambda t: None if t["margin"] is None else t["margin"] == "negative"),
            ("Postoperative histologically confirmed adenocarcinoma of the stomach or GEJ",
             histology_has(r"adenocarcinoma|poorly cohesive carcinoma")),
            ("Positive lymph nodes more than 7, stage pN3",
             lambda t: None if t["n_cat"] is None or t["nodes_pos"] is None else (N(t["n_cat"]) == 3 and t["nodes_pos"] > 7)),
            ("[age] 18 Years and older", age_between(18, None)),
        ],
        "exclude": [],
        "needs": ["D2 lymphadenectomy", "M0 or M1 with CY1P0 only", "ECOG 0-1", "expected survival > 6 months",
                  "blood and biochemistry thresholds", "consent"],
    },
    "NCT06661720": {
        "organ": "kidney", "title": "Pembrolizumab ± tivozanib, adjuvant after nephrectomy for intermediate-high / high-risk RCC",
        "include": [
            ("RCC with clear cell component with or without sarcomatoid features following complete resection",
             histology_has(r"clear cell", r"papillary|chromophobe|collecting duct|sarcoma")),
            ("Intermediate-high risk: pT2 grade 4 or sarcomatoid, N0M0; pT3 any grade N0 — High risk: pT4 N0; any pT N+",
             lambda t: (True if t["n_cat"] is not None and N(t["n_cat"]) >= 1 else
                        None if t["t_cat"] is None else
                        False if T(t["t_cat"]) <= 1 or (T(t["t_cat"]) == 2 and t["grade"] != 4 and not t["sarcomatoid"]) else
                        None if t["n_cat"] is None else    # pNX: risk group needs N0 confirmed
                        True)),
            ("Age >= 18 years", age_between(18, None)),
            ("Note: microscopically positive soft tissue or vascular margins without gross residual disease are permitted",
             lambda t: True),
        ],
        "exclude": [],
        "needs": [M0 + " (or resected cM1 NED)", "surgery 4-16 weeks before registration", "no prior systemic therapy",
                  "ECOG ≤ 2", "blood counts, renal, hepatic function, urine protein", "HIV/HBV/HCV status",
                  "cardiac history, pneumonitis, blood pressure"],
    },
    "NCT07581509": {
        "organ": "skin", "title": "Adjuvant pembrolizumab biosimilar (Bmab1800) vs Keytruda, resected stage IIB-III melanoma (Phase 1)",
        "include": [
            ("Male or female patients aged ≥18 years", age_between(18, None)),
            ("Histologically confirmed melanoma that is completely surgically resected with negative margins",
             all_of(eq("group", "melanoma"), lambda t: None if t["margin"] is None else t["margin"] == "negative")),
            ("Stage IIB, IIC, or Stage III melanoma per AJCC 8th edition",
             lambda t: None if melanoma_stage(t) is None else melanoma_stage(t) in ("IIB", "IIC", "III")),
        ],
        "exclude": [("History of ocular/uveal and mucosal melanoma", lambda t: False)],  # Biobase skin = cutaneous
        "needs": ["ECOG 0-1", "resection ≥ 28 days before consent; randomization ≤ 12 weeks after surgery",
                  "disease-free on imaging; no brain metastases", "autoimmune disease, steroids, prior checkpoint therapy"],
    },
}

import re  # noqa: E402  (used inside the lambdas above)
