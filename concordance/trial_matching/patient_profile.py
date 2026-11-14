"""
PATIENT PROFILE: one structured profile per patient, the facts a trial can check.

Three builders, same keys (see trial_matching_design.md, section 1 and 3):
  report_profile(text)        from the report via criteria_search/parse.py (template block)  <- what we match with
  truth_profile(record)       from the Biobase labels                                         <- validation truth
  prose_profile(text)         from GROSS/MICROSCOPIC prose only (criteria_search/prose_card)  <- "no template" stress test

A value of None means "the source doesn't say"; rules then return undetermined, never a guess.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "criteria_search"))
from parse import parse_report          # noqa: E402
from prose_card import build_prose_card  # noqa: E402

SKIN_GROUPS = [  # Diagnosis text -> Biobase skin group (only those trials care about)
    (r"melanoma in situ|lentigo maligna(?! melanoma)", "melanoma_in_situ"),
    (r"melanoma", "melanoma"),
    (r"squamous cell carcinoma in situ", "scc_in_situ"),
    (r"invasive squamous cell carcinoma", "scc"),
    (r"basal cell carcinoma", "bcc"),
]


def _num(pat, s, cast=float):
    m = re.search(pat, s or "", re.I)
    return cast(m.group(1)) if m else None


def age_range(band):
    """'60-69' -> (60, 69); '90+' -> (90, 120)."""
    if not band:
        return None, None
    if band.endswith("+"):
        return int(band[:-1]), 120
    lo, hi = band.split("-")
    return int(lo), int(hi)


def stage_parts(stage_text):
    """'pT2b pN1a(sn)' -> ('2b', '1a', True). NX -> None."""
    t = re.search(r"pT(is|X|\d[a-d]?)", stage_text or "")
    n = re.search(r"pN(X|\d(?:mi|[a-c])?)(\(sn\))?", stage_text or "")
    t_cat = t.group(1) if t and t.group(1) not in ("X",) else None
    n_cat = n.group(1) if n and n.group(1) != "X" else None
    sn = bool(n and n.group(2))
    return t_cat, n_cat, sn


def major(cat):
    return int(cat[0]) if cat and cat[0].isdigit() else (0 if cat == "is" else None)


def _her2(organ, f):
    """Breast: 'HER2 negative (score 1+)' inside Biomarkers. Stomach: its own HER2 field, status first."""
    if organ == "breast":
        m = re.search(r"HER2 (positive|negative|equivocal|low)", f.get("Biomarkers") or "")
    elif organ == "stomach":
        m = re.match(r"\s*(positive|negative|equivocal|low)", f.get("HER2") or "")
    else:
        return None
    return m.group(1) if m else None


COARSE = {"melanoma", "melanoma_in_situ", "scc", "scc_in_situ", "bcc"}


def profile_from_fields(f, organ, sex, age_band, group=None, pT=None, pN=None):
    """Shared builder: diagnosis fields (as in the report's final-diagnosis block) -> profile."""
    low = lambda k: (f.get(k) or "").lower()
    stage_txt = f.get("Pathologic stage (AJCC 8th ed.)") or f.get("Pathologic stage") or ""
    if pT or pN:  # labels carry the stage separately
        stage_txt = f"{pT or ''} {pN or ''}"
    t_cat, n_cat, sn = stage_parts(stage_txt)
    nodes = re.search(r"(\d+)\s+of\s+(\d+)\s+(?:sentinel\s+)?(?:lymph\s+nodes\s+)?positive",
                      " ".join(v for k, v in f.items() if k == "Lymph nodes" or k.startswith("Part B")))
    bio = f.get("Biomarkers") or ""
    margins = low("Margins")
    diag = (f.get("Diagnosis") or f.get("Histologic type") or "")
    if organ == "skin" and group is None:
        group = next((g for pat, g in SKIN_GROUPS if re.search(pat, diag, re.I)), "other")
    lo, hi = age_range(age_band)
    return {
        "organ": organ, "sex": sex, "age_lo": lo, "age_hi": hi, "group": group,
        "specimen": (f.get("Specimen") or "").lower(),
        "histology": diag.lower(),
        "t_cat": t_cat, "t_major": major(t_cat), "n_cat": n_cat, "n_major": major(n_cat), "sentinel": sn,
        "nodes_pos": int(nodes.group(1)) if nodes else None,
        "nodes_exam": int(nodes.group(2)) if nodes else None,
        "grade": (_num(r"^(\d)", f.get("Nottingham grade"), int) or _num(r"G(\d)", f.get("Histologic grade"), int)
                  or _num(r"^(\d)", f.get("ISUP grade"), int)),
        "er": (re.search(r"ER (positive|negative|low)", bio).group(1) if re.search(r"ER (positive|negative|low)", bio) else None),
        "er_pct": _num(r"ER \w+,\s*(?:less than\s*)?(\d+)%", bio),
        "pr": (re.search(r"PR (positive|negative|low)", bio).group(1) if re.search(r"PR (positive|negative|low)", bio) else None),
        "her2": _her2(organ, f),
        "margin": (None if not margins else
                   "positive" if re.search(r"involv|extends to|positive at|^positive", margins) and "uninvolved" not in margins
                   else "negative"),
        "tumor_site": low("Tumor site") or None,
        "lvi": (None if f.get("Lymphovascular invasion") is None else low("Lymphovascular invasion").startswith("present")),
        "pni": (None if f.get("Perineural invasion") is None else low("Perineural invasion").startswith("present")),
        "perforation": (None if f.get("Macroscopic tumor perforation") is None
                        else low("Macroscopic tumor perforation").startswith("present")),
        "sarcomatoid": (None if f.get("Sarcomatoid or rhabdoid features") is None
                        else low("Sarcomatoid or rhabdoid features").startswith("present")),
        "neoadjuvant": (None if f.get("Neoadjuvant therapy") is None else not low("Neoadjuvant therapy").startswith("none")),
        "lauren": bool(re.search(r"lauren", diag, re.I)) if organ == "stomach" else None,
        "breslow_mm": _num(r"(\d+(?:\.\d+)?)\s*mm", f.get("Breslow thickness")),
        "ulceration": (None if f.get("Ulceration") is None else low("Ulceration").startswith("present")),
    }


def report_profile(text):
    p = parse_report(text)
    return profile_from_fields(p["fields"], p["organ"], p["sex"], p["age_band"])


def truth_profile(rec):
    L = rec["labels"]
    group = (L["group"] if L["group"] in COARSE else "other") if L["organ"] == "skin" else None
    return profile_from_fields(L["diagnosis"], L["organ"], L["sex"], L["age_band"], group=group,
                            pT=L["pT"], pN=L["pN"])


# AJCC 8th regional-node categories by number of positive nodes (organ-specific). Lung nodes are
# staged by station, not count, so lung stays unknown.
N_BY_COUNT = {
    "colon":    [(0, "0"), (1, "1"), (4, "2a"), (7, "2b")],
    "stomach":  [(0, "0"), (1, "1"), (3, "2"), (7, "3a"), (16, "3b")],
    "breast":   [(0, "0"), (1, "1"), (4, "2"), (10, "3")],
    "prostate": [(0, "0"), (1, "1")],
    "kidney":   [(0, "0"), (1, "1")],
}


def n_cat_from_count(organ, nodes_pos, n_major):
    """Prose profile: derive N category from the positive-node count; never round N2/N3 down to N1."""
    if nodes_pos is None:
        return "0" if n_major == 0 else None
    cat = None
    for lo, c in N_BY_COUNT.get(organ, []):
        if nodes_pos >= lo:
            cat = c
    return cat


def prose_profile(text):
    """Header + GROSS/MICROSCOPIC prose only. Fields the prose reader doesn't produce stay None."""
    c = build_prose_card(text, use_header=True, infer_morphology=True)
    lo, hi = age_range(c["age_band"])
    t_major = c["t_major"]
    return {
        "organ": c["organ"], "sex": c["sex"], "age_lo": lo, "age_hi": hi, "group": None, "specimen": "",
        "histology": c["histology"], "t_cat": str(t_major) if t_major else None, "t_major": t_major,
        "n_cat": n_cat_from_count(c["organ"], c["nodes_pos"], c["n_major"]), "n_major": c["n_major"], "sentinel": False,
        "nodes_pos": c["nodes_pos"], "nodes_exam": None,
        "grade": c["nottingham"] or c["isup"], "er": c["er"], "er_pct": None, "pr": c["pr"], "her2": c["her2"],
        "margin": ("negative" if c["margin_neg"] else "positive" if c["margin_neg"] is False else None),
        "tumor_site": None, "lvi": c["lvi"], "pni": c["pni"], "perforation": None, "sarcomatoid": c["sarcomatoid"],
        "neoadjuvant": None, "lauren": None, "breslow_mm": None, "ulceration": None,
    }
