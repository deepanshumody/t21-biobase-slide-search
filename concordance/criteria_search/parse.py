"""
STAGE 1 of 3: PARSE  (report_text -> labeled raw fields)

Pipeline:  parse.py  ->  card.py  ->  rules.py
                         (typed facts)  (30 yes/no checks)

Only the code-written parts of a report are read here:
  - the "Patient:" line   -> sex, age band, year
  - the "SPECIMEN:" line  -> organ
  - the FINAL DIAGNOSIS block -> {field name: raw value text}
The GROSS / MICROSCOPIC prose (written by an LLM) is ignored.

See criteria_search_design.md section 3.
"""
import json
import re

# ---------------------------------------------------------------------------
# Every field name that can appear in a FINAL DIAGNOSIS block (from the README,
# all organs combined). Sorted longest-first so the regex prefers
# "Pathologic stage (AJCC 8th ed.)" over "Pathologic stage", and
# "Depth of invasion" over "Depth".
# ---------------------------------------------------------------------------
FIELD_NAMES = sorted({
    # skin
    "Specimen", "Diagnosis", "Margins", "Tumor size", "Aggressive growth pattern",
    "Ulceration", "Perineural invasion", "Depth", "Pathologic stage",
    "Depth of invasion", "Lymphovascular invasion", "High-risk features",
    "Pathologic stage (AJCC 8th ed.)", "Invasive carcinoma", "Breslow thickness",
    "Mitotic rate", "Regression", "Tumor-infiltrating lymphocytes",
    "Microscopic satellites", "Neurotropism", "Extension along follicular epithelium",
    "Dermal invasion", "Residual melanoma in this excision", "Biopsy correlation",
    "Part B, sentinel lymph nodes (left inguinal)",
    "Part B, sentinel lymph nodes (left axillary)", "Clark level",
    "Part B, sentinel lymph nodes (right inguinal)",
    "Part B, sentinel lymph nodes (left cervical)",
    "Part B, sentinel lymph nodes (right axillary)",
    "Part B, sentinel lymph nodes (right cervical)",
    # breast
    "Tumor site", "Histologic type", "Nottingham grade", "Tumor focality",
    "Ductal carcinoma in situ", "Lymph nodes", "Biomarkers", "Neoadjuvant therapy",
    # lung
    "Visceral pleural invasion",
    # prostate
    "Gleason score", "Tumor extent", "Cribriform glands", "Intraductal carcinoma",
    "Extraprostatic extension", "Seminal vesicle invasion",
    # stomach / colon
    "Histologic grade", "HER2", "Macroscopic tumor perforation", "Tumor deposits",
    # kidney
    "ISUP grade", "Sarcomatoid or rhabdoid features", "Extent of invasion",
}, key=len, reverse=True)

# A field starts at the start of the block, after a newline, or after "; "
# (the one-line layout), followed by "<Name>:".
_FIELD_START = re.compile(
    r"(?:^|\n|;\s)\s*(" + "|".join(re.escape(n) for n in FIELD_NAMES) + r"):\s*"
)

_PATIENT = re.compile(r"Patient:\s*([MF]),\s*age band\s*([0-9+\-]+)\s*\|\s*Report year:\s*(\d{4})")
_SPECIMEN = re.compile(r"^SPECIMEN:\s*(.+)$", re.M)
_BLOCK = re.compile(r"FINAL DIAGNOSIS:(.*?)(?:\n\s*GROSS DESCRIPTION:|\Z)", re.S)

# Organ keywords looked up in the SPECIMEN line (first hit wins).
ORGAN_KEYWORDS = [
    ("skin", "skin"), ("breast", "breast"), ("lung", "lung"), ("prostate", "prostate"),
    ("stomach", "stomach"), ("gastr", "stomach"), ("kidney", "kidney"), ("renal", "kidney"),
    ("colon", "colon"), ("rect", "colon"), ("cecum", "colon"), ("sigmoid", "colon"),
]


def _clean(value):
    """Trim whitespace and the trailing ';' / '.' left by the one-line layout."""
    value = value.strip()
    value = re.sub(r"[;\s]+$", "", value)
    if value.endswith(".") and not value.endswith("ed.)"):
        value = value[:-1]
    return value.strip()


def parse_block(block):
    """FINAL DIAGNOSIS text -> {field: value}. Unlabeled leading text = 'Diagnosis'."""
    fields = {}
    starts = list(_FIELD_START.finditer(block))
    lead = block[: starts[0].start()] if starts else block
    if _clean(lead):
        fields["Diagnosis"] = _clean(lead)
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(block)
        fields[m.group(1)] = _clean(block[m.end():end])
    return fields


def organ_from_specimen(specimen):
    """The keyword appearing EARLIEST in the line wins, so
    'Colon (...), colectomy with en bloc resection of stomach' -> colon."""
    s = specimen.lower()
    hits = [(s.find(kw), organ) for kw, organ in ORGAN_KEYWORDS if kw in s]
    return min(hits)[1] if hits else None


def parse_report(text):
    """report_text -> {'organ','sex','age_band','year','specimen','fields'}."""
    out = {"organ": None, "sex": None, "age_band": None, "year": None,
           "specimen": None, "fields": {}}
    m = _PATIENT.search(text)
    if m:
        out["sex"], out["age_band"], out["year"] = m.group(1), m.group(2), int(m.group(3))
    m = _SPECIMEN.search(text)
    if m:
        out["specimen"] = m.group(1).strip()
        out["organ"] = organ_from_specimen(out["specimen"])
    m = _BLOCK.search(text)
    if m:
        out["fields"] = parse_block(m.group(1))
    if out["specimen"]:
        out["fields"]["Specimen"] = out["specimen"]  # labels store Specimen too
    return out


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]
