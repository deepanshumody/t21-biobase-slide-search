"""
STAGE 2 of 3: CARD  (labeled raw fields -> typed facts)

Pipeline:  parse.py  ->  card.py  ->  rules.py

Turns wording into values a rule can test:
    "not identified"        -> False
    "3 of 14 positive"      -> 3
    "4.3 cm"                -> 43.0 (mm)
    "ER positive, 95% ..."  -> er = "positive"
    "pT4a pN1b"             -> t_major = 4, n_major = 1

Convention: None means "the report doesn't say", which differs from False ("the
report says no"). Rules treat None as "does not match".

See criteria_search_design.md section 4.
"""
import re


# ---------------------------------------------------------------------------
# Small readers: each turns one kind of wording into one value.
# ---------------------------------------------------------------------------

def present(value):
    """'present ...' -> True, 'not identified' / 'absent' -> False, else None."""
    if value is None:
        return None
    v = value.lower().strip()
    if v.startswith(("not identified", "absent", "none", "no ")):
        return False
    if v.startswith(("present", "identified")):
        return True
    return None


def first_int(value):
    m = re.search(r"\d+", value or "")
    return int(m.group()) if m else None


def size_mm(value):
    """'4.3 cm' -> 43.0, '3 mm' -> 3.0. Uses the first number+unit pair."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(cm|mm)", value or "")
    if not m:
        return None
    n = float(m.group(1))
    return n * 10 if m.group(2) == "cm" else n


def receptor(text, name):
    """Status of ER / PR / HER2 inside a Biomarkers string."""
    m = re.search(name + r"\s+(positive|negative|equivocal|low)", text or "", re.I)
    return m.group(1).lower() if m else None


def nodes_positive(value):
    """'3 of 14 positive' -> 3. None when the field is missing."""
    m = re.search(r"(\d+)\s+of\s+(\d+)\s+positive", value or "")
    return int(m.group(1)) if m else None


def stage(value):
    """'pT4a pN1b' -> ('4a', '1b'). Also handles ypT / pTis / (m) / (sn) suffixes."""
    t = re.search(r"\by?pT(is|X|\d[a-d]?)", value or "")
    n = re.search(r"\by?pN(X|\d[a-c]?(?:mi)?)", value or "")
    return (t.group(1) if t else None), (n.group(1) if n else None)


def major(cat):
    """'4a' -> 4, 'is' / 'X' / None -> None."""
    return int(cat[0]) if cat and cat[0].isdigit() else None


def grab_int(pattern, value):
    """First captured integer of `pattern` in `value`, or None."""
    m = re.search(pattern, value or "")
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Build the card. One flat dict per report; rules read only from this.
# ---------------------------------------------------------------------------

def build_card(parsed):
    f = parsed["fields"]
    get = lambda k: f.get(k)
    low = lambda k: (f.get(k) or "").lower()

    t_cat, n_cat = stage(get("Pathologic stage (AJCC 8th ed.)") or get("Pathologic stage"))
    margins = low("Margins")
    biomarkers = get("Biomarkers") or ""
    m_mm = re.search(r"(\d+(?:\.\d+)?)\s*mm from the closest margin", margins)

    return {
        # --- STEP 1: which tissue (every rule checks this first) -------------
        "organ": parsed["organ"],

        # --- who ------------------------------------------------------------
        "sex": parsed["sex"],
        "age_band": parsed["age_band"],
        "age_min": first_int(parsed["age_band"]),   # '70-79' -> 70, '90+' -> 90
        "year": parsed["year"],

        # --- what (lowercased; skin uses its unlabeled Diagnosis line) ------
        "histology": low("Histologic type") or low("Diagnosis"),

        # --- stage / nodes --------------------------------------------------
        "t_cat": t_cat, "t_major": major(t_cat),
        "n_cat": n_cat, "n_major": major(n_cat),
        "nodes_pos": nodes_positive(get("Lymph nodes")),

        # --- size -----------------------------------------------------------
        "size_mm": size_mm(get("Tumor size")),

        # --- yes/no findings ------------------------------------------------
        "lvi": present(get("Lymphovascular invasion")),
        "pni": present(get("Perineural invasion")),
        "deposits": present(get("Tumor deposits")),
        "vpi": present(get("Visceral pleural invasion")),
        "svi": present(get("Seminal vesicle invasion")),
        "sarcomatoid": present(get("Sarcomatoid or rhabdoid features")),
        # EPE: "not identified (organ-confined)" vs "established extraprostatic extension ..."
        "epe": None if get("Extraprostatic extension") is None
               else not low("Extraprostatic extension").startswith("not identified"),
        "multifocal": low("Tumor focality").startswith("multifocal") if get("Tumor focality") else None,

        # --- grades ---------------------------------------------------------
        "nottingham": first_int(get("Nottingham grade")),
        "grade_group": grab_int(r"Grade Group\s*(\d)", get("Gleason score")),
        "isup": first_int(get("ISUP grade")),
        "scc_grade": grab_int(r"\(G(\d)\)", get("Diagnosis")),

        # --- receptors ------------------------------------------------------
        "er": receptor(biomarkers, "ER"),
        "pr": receptor(biomarkers, "PR"),
        # breast: inside Biomarkers; stomach: its own HER2 field
        "her2": receptor(biomarkers, "HER2") or receptor("HER2 " + (get("HER2") or ""), "HER2"),

        # --- margins (raw text kept for organ-specific rules) ---------------
        "margins": margins,
        "margin_neg": margins.startswith("negative") if margins else None,
        "margin_mm": float(m_mm.group(1)) if m_mm else None,

        # --- free-text extent fields ----------------------------------------
        "depth": low("Depth of invasion"),
        "extent": low("Extent of invasion"),
    }
