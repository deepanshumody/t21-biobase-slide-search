"""
EXPERIMENT: build the SAME card as card.py, but from the LLM-written prose only
(GROSS + MICROSCOPIC). The FINAL DIAGNOSIS block is never read.

Purpose: measure how much of the 1.0 train score comes from reading the
code-written template, and how much survives on free text. rules.py runs
unchanged on these cards.

    parse.py  -> card.py       -> rules.py    (template reader, main system)
    prose     -> prose_card.py -> rules.py    (this experiment)

Two variants (set by `use_header`):
  A  use_header=True : the code-written header (Patient line + SPECIMEN line) is kept
  B  use_header=False: prose only; organ guessed from prose; no age / sex / year

Techniques (all hand-written, no learned weights):
  - polarity(): finds a concept, reads forward to the first present/absent cue,
    and also looks back for "no / neither / nor / without".
  - number patterns for node counts, sizes and grades
  - a few AJCC-style derivations (e.g. colon pN1c = tumor deposits with 0 nodes)
"""
import re

from parse import _PATIENT, _SPECIMEN, organ_from_specimen

NEG_CUE = r"not identified|not seen|not present|not involved|absent|negative|\bis not\b|\bare not\b"
POS_CUE = r"\bpresent\b|\bidentified\b|\bis seen\b|\bconfirmed\b|\binvolv"
_CUE = re.compile(f"(?P<neg>{NEG_CUE})|(?P<pos>{POS_CUE})", re.I)
_NEG_BEFORE = re.compile(r"\b(no|neither|nor|without)\b[^.,;]{0,25}$", re.I)


def prose_of(text):
    i = text.find("GROSS DESCRIPTION")
    return text[i:] if i >= 0 else ""


def microscopic_of(text):
    i = text.find("MICROSCOPIC DESCRIPTION:")
    return text[i + len("MICROSCOPIC DESCRIPTION:"):] if i >= 0 else ""


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=\.)\s+|\n+", text) if s.strip()]


# ---------------------------------------------------------------------------
# Polarity: is concept X said to be present, absent, or not mentioned?
# ---------------------------------------------------------------------------
def polarity(text, concept):
    """True if any mention is positive, False if all mentions are negative, None if never mentioned."""
    verdicts = []
    for m in re.finditer(concept, text, re.I):
        before = text[max(0, m.start() - 40):m.start()]
        if _NEG_BEFORE.search(before):
            verdicts.append(False)
            continue
        stop = re.search(r"[.;]", text[m.end():])
        after = text[m.end(): m.end() + stop.start()] if stop else text[m.end():]
        cue = _CUE.search(after)
        if cue:
            verdicts.append(cue.group("pos") is not None)
        elif re.search(r"\b(focal|established|extensive)\s+$", before, re.I):
            verdicts.append(True)   # "Focal extraprostatic extension at ..." (no cue word)
    if not verdicts:
        return None
    return any(verdicts)


def grab(pattern, text, cast=int, flags=re.I):
    m = re.search(pattern, text, flags)
    return cast(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Organ from prose (variant B): count distinctive words; highest score wins.
# ---------------------------------------------------------------------------
ORGAN_WORDS = {
    "prostate": r"prostat|gleason|seminal vesicle",
    "kidney": r"nephrectomy|renal cell|isup|perinephric",
    "lung": r"lobectomy|pneumonectomy|pleura|bronch|lung",
    "stomach": r"gastrectomy|gastric|lauren|stomach|perigastric",
    "colon": r"colectomy|colon|mesenteric|pericolorectal|cecum|sigmoid",
    "breast": r"mastectomy|lumpectomy|breast|nottingham|ductal carcinoma",
    "skin": r"shave|punch|epiderm|dermis|keratin|melanocyt|nevus",
}


def organ_from_prose(prose):
    scores = {o: len(re.findall(p, prose, re.I)) for o, p in ORGAN_WORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else None


# ---------------------------------------------------------------------------
# Field readers
# ---------------------------------------------------------------------------
_LEAD = re.compile(r"^(?:the\s+)?(?:sections?\s+(?:show|shows|demonstrate|demonstrates|reveal|reveals)\s+|"
                   r"the tumor is classified as\s+)(?:an?\s+|the\s+)?", re.I)


# Named tumor types, most specific first. Output is the canonical name rules.py expects.
HISTOLOGY_NAMES = [
    (r"(?<!non-)mucinous adenocarcinoma", "mucinous adenocarcinoma"),
    (r"mixed adenocarcinoma", "mixed adenocarcinoma"),
    (r"poorly cohesive carcinoma", "poorly cohesive carcinoma"),
    (r"clear cell renal cell carcinoma", "clear cell renal cell carcinoma"),
    (r"basal cell carcinoma", "basal cell carcinoma"),
    (r"squamous cell carcinoma in situ", "squamous cell carcinoma in situ"),
    (r"invasive squamous cell carcinoma", "invasive squamous cell carcinoma"),
    (r"squamous cell carcinoma", "squamous cell carcinoma"),
    (r"adenocarcinoma", "adenocarcinoma"),
]

# Pathologist-knowledge inference when the prose describes cells but never names the tumor.
# Switched by `infer_morphology` so its effect is reported separately.
MORPHOLOGY = [
    ("skin", r"basaloid.*?(palisad|retraction cleft)", "basal cell carcinoma"),
    ("kidney", r"clear cytoplasm", "clear cell renal cell carcinoma"),
]


def histology_of(micro, organ=None, infer_morphology=False):
    """Earliest-named known tumor type in the microscopic text, else (optionally) morphology inference,
    else the first sentence without its 'Sections show a ...' lead-in."""
    hits = [(m.start(), name) for pat, name in HISTOLOGY_NAMES if (m := re.search(pat, micro, re.I))]
    if hits:
        # earliest position wins; on ties the more specific pattern (listed first) wins
        return min(hits, key=lambda h: h[0])[1]
    if infer_morphology:
        for org, pat, name in MORPHOLOGY:
            if organ == org and re.search(pat, micro, re.I | re.S):
                return name
    first = sentences(micro)[0] if sentences(micro) else ""
    return _LEAD.sub("", first).lower()


def nodes_of(prose):
    """First 'X of Y' inside a sentence that talks about nodes."""
    for s in sentences(prose):
        if re.search(r"node", s, re.I):
            m = re.search(r"(\d+)\s+of\s+(\d+)", s)
            if m:
                return int(m.group(1))
    return None


def size_of(prose, micro):
    """Microscopic 'tumor measures / tumor size X' first, then gross 'X in greatest dimension'."""
    for pat, txt in ((r"tumou?r\s+(?:size\s+(?:is\s+)?|measures\s+|measuring\s+)(\d+(?:\.\d+)?)\s*(cm|mm)", micro),
                     (r"(\d+(?:\.\d+)?)\s*(cm|mm)\s+(?:in\s+)?greatest dimension", prose)):
        m = re.search(pat, txt, re.I)
        if m:
            n = float(m.group(1))
            return n * 10 if m.group(2).lower() == "cm" else n
    return None


def scc_grade_of(micro):
    g = grab(r"\(G(\d)\)", micro)
    if g:
        return g
    for word, n in (("well", 1), ("moderately", 2), ("poorly", 3)):
        if re.search(word + r"\s+differentiated", micro, re.I):
            return n
    return None


RECEPTOR_NAMES = {"ER": r"\bER\b|estrogen receptor", "PR": r"\bPR\b|progesterone receptor", "HER2": r"\bHER2\b"}


def receptor_of(prose, name):
    """'ER positive' / 'estrogen receptor positivity' / 'progesterone receptor is negative' -> status.
    Reads only up to the next comma-clause that names another receptor."""
    m = re.search(r"(?:" + RECEPTOR_NAMES[name] + r")([^.]*)", prose, re.I)
    if not m:
        return None
    tail = re.split(r"\b(?:ER|PR|HER2)\b|estrogen|progesterone", m.group(1), flags=re.I)[0]
    s = re.search(r"(positiv|negativ|equivocal)", tail, re.I)
    return {"positiv": "positive", "negativ": "negative", "equivocal": "equivocal"}[s.group(1).lower()] if s else None


def t4_from_depth(micro):
    """Colon / stomach pT4: penetrates the visceral peritoneum or serosa, or directly invades adjacent structures."""
    if re.search(r"without\s+penetrat", micro, re.I):
        return False
    return bool(re.search(r"penetrat\w*\s+(?:through\s+)?(?:the\s+)?(?:visceral peritoneum|serosa)|directly invades",
                          micro, re.I))


# ---------------------------------------------------------------------------
# Build the card (same keys as card.py; keys no rule needs are left out)
# ---------------------------------------------------------------------------
def build_prose_card(text, use_header=True, infer_morphology=False):
    prose, micro = prose_of(text), microscopic_of(text)

    sex = age_band = year = None
    organ = None
    if use_header:
        m = _PATIENT.search(text)
        if m:
            sex, age_band, year = m.group(1), m.group(2), int(m.group(3))
        m = _SPECIMEN.search(text)
        organ = organ_from_specimen(m.group(1)) if m else None
    else:
        organ = organ_from_prose(prose)

    nodes_pos = nodes_of(prose)
    deposits = polarity(prose, r"tumou?r deposits")

    # Derived pN (AJCC knowledge, not template): nodes >= 1 -> N1+; colon 0 nodes + deposits -> pN1c.
    if nodes_pos is not None and nodes_pos >= 1:
        n_major = 1
    elif organ == "colon" and nodes_pos == 0 and deposits:
        n_major = 1
    elif nodes_pos == 0:
        n_major = 0
    else:
        n_major = None

    # ---- organ-specific margin wording, normalized to what rules.py reads ----
    margins, margin_neg, margin_mm = "", None, None
    if organ == "breast":
        margin_mm = grab(r"invasive carcinoma\s+(?:is\s+|lies\s+|lying\s+|located\s+|is located\s+|is situated\s+)*(\d+(?:\.\d+)?)\s*mm\s+from\s+(?:the\s+)?closest margin",
                         micro, float)
        involved = re.search(r"involves the inked|margin (?:is |are )?(?:involved|positive)", micro, re.I)
        margin_neg = None if (margin_mm is None and not involved) else not involved
        if margin_neg:
            margins = "negative"
    elif organ == "lung":
        if re.search(r"bronchial margin\s+(?:is\s+)?involved", prose, re.I):
            margins = "bronchial margin involved"
    elif organ == "prostate":
        margins = "positive" if re.search(r"surgical margins?\s+(?:is\s+|are\s+)?positive", prose, re.I) else "negative"
    elif organ == "skin":
        if re.search(r"(?:extends to|present at|involves)\s+(?:the\s+)?(?:peripheral and\s+)?deep margin|deep margins?\s+(?:is\s+|are\s+)?involved",
                     micro, re.I):
            margins = "extends to the deep margin"

    # ---- kidney extent -------------------------------------------------------
    extent = ""
    if organ == "kidney":
        if polarity(prose, r"renal vein invasion") or re.search(
                r"extends into\s+(?:the\s+)?(?:main\s+renal vein|segmental branches of the renal vein|renal vein)", prose, re.I):
            extent = "renal vein"
        if re.search(r"extends into\s+(?:the\s+)?inferior vena cava", prose, re.I):
            extent += " vena cava"

    sarc = polarity(prose, r"sarcomatoid")
    rhab = polarity(prose, r"rhabdoid")

    return {
        "organ": organ, "sex": sex, "age_band": age_band,
        "age_min": int(re.match(r"\d+", age_band).group()) if age_band else None,
        "year": year,
        "histology": histology_of(micro, organ, infer_morphology),
        "t_cat": None, "t_major": 4 if t4_from_depth(micro) else None,
        "n_cat": None, "n_major": n_major,
        "nodes_pos": nodes_pos,
        "size_mm": size_of(prose, micro),
        "lvi": polarity(prose, r"lymphovascular invasion"),
        "pni": polarity(prose, r"perineural invasion"),
        "deposits": deposits,
        "vpi": polarity(prose, r"visceral pleural invasion"),
        "svi": polarity(prose, r"seminal vesicle invasion"),
        "sarcomatoid": None if sarc is None and rhab is None else bool(sarc or rhab),
        "epe": polarity(prose, r"extraprostatic extension"),
        "multifocal": True if re.search(r"multifocal", prose, re.I) else (False if re.search(r"unifocal", prose, re.I) else None),
        "nottingham": grab(r"Nottingham (?:histologic )?grade(?:\s+of)?\s*(\d)", micro),
        "grade_group": grab(r"Grade Group\s*(\d)", micro),
        "isup": grab(r"ISUP(?:/WHO)?\s+(?:nucleolar\s+)?grade(?:\s+of)?\s*(\d)", micro),
        "scc_grade": scc_grade_of(micro) if organ == "skin" else None,
        "er": receptor_of(prose, "ER"),
        "pr": receptor_of(prose, "PR"),
        "her2": receptor_of(prose, "HER2"),
        "margins": margins, "margin_neg": margin_neg, "margin_mm": margin_mm,
        "depth": "", "extent": extent,
    }
