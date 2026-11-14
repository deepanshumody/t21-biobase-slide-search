"""
READER (rule-based): real breast pathology report text -> fact sheet with evidence.

Pipeline:  reader.py  ->  criteria.py  ->  evaluate.py
See concordance_breast_design.md, section 3.

Every fact comes back as
    {"value": ..., "conf": 0-1, "kind": "synoptic|stage_code|narrative|derived|conflict", "evidence": "..."}
or None when the report doesn't state it ("unknown" is a valid answer).

How it works, per fact:
  1. normalize OCR text (whitespace, common OCR confusions)
  2. collect CANDIDATES: every pattern hit -> (value, kind, snippet)
  3. drop candidates sitting in BOILERPLATE (method / definition text that names a
     receptor and a status word without describing this patient)
  4. RESOLVE: one value -> confidence of the strongest evidence kind;
     several different values -> majority, confidence x 0.5 (kind = "conflict")

`naive=True` turns off steps 3-4 (first hit wins, no boilerplate filter): this is the
keyword-style baseline in evaluate.py.
"""
import re
from collections import Counter

# Starting confidence per evidence kind (hand-set; calibrated in evaluate.py).
KIND_CONF = {"synoptic": 0.95, "stage_code": 0.90, "narrative": 0.80, "derived": 0.75}
CONFLICT_FACTOR = 0.5

# ---------------------------------------------------------------------------
# 1. OCR normalization
# ---------------------------------------------------------------------------
OCR_FIXES = [
    (r"carcinuna|carcinorna|carcin0ma", "carcinoma"),
    (r"\bHER\s*-?\s*2\s*/?\s*-?\s*neu\b", "HER2/neu"),
    (r"\bHER\s*-\s*2\b|\bHer-?2\b|\bHER-2\b", "HER2"),
    (r"\boestrogen\b", "estrogen"),
]


def normalize(text):
    t = re.sub(r"\s+", " ", text)
    for pat, rep in OCR_FIXES:
        t = re.sub(pat, rep, t, flags=re.I)
    return t


# ---------------------------------------------------------------------------
# Boilerplate: method / definition text near a hit -> ignore that hit.
# ---------------------------------------------------------------------------
BOILER = re.compile(
    r"defined as|is considered|control (?:tissue|slide)|validated|validation|guideline|ASCO|\bCAP\b|"
    r"\bFDA\b|selection of patients|interpretation|allred score (?:of|is calculated)|less than or equal|"
    r"reference range|\bkit\b|clone|antibod|is calculated|recommend|for whom|scoring system|"
    r"\bif\b|should be|may be|cut-?off|threshold|category for|staining result that|scores of|"
    r"reference range|were evaluated|assessed by|performed (?:on|using|by)|approved", re.I)


def is_boilerplate(t, start, end, before=70, after=40):
    return bool(BOILER.search(t[max(0, start - before):end + after]))


def snippet(t, start, end, pad=40):
    return t[max(0, start - pad):end + pad].strip()


# ---------------------------------------------------------------------------
# 2. Candidate finders, one per fact. Each yields (value, kind, start, end).
# ---------------------------------------------------------------------------
STATUS = r"(positive|negative|pos\b|neg\b|equivocal|borderline|indeterminate)"


def _status_word(w):
    w = w.lower()
    if w.startswith("pos"):
        return "positive"
    if w.startswith("neg"):
        return "negative"
    if w in ("equivocal", "borderline"):
        return "equivocal"
    return None


def _pct_status(pct):
    """IHC percent -> status (>= 1% positive, ASCO/CAP 2010)."""
    return "positive" if pct >= 1 else "negative"


def find_receptor(t, name):
    """ER or PR: 'ER: Positive', 'ESTROGEN RECEPTORS: positive', 'ER positive', 'ER: 95%',
    'Estrogen receptors found in over 10%', 'estrogen and progesterone receptor: <1%'."""
    label = {"ER": r"(?:estrogen receptors?|\bER\b(?!/)|\bER-alpha\b)",
             "PR": r"(?:progesterone receptors?|\bPR\b|\bPgR\b)"}[name]
    # label: STATUS  (synoptic) / label STATUS (narrative)
    for m in re.finditer(label + r"(\s*(?:status)?\s*(?:\(IHC\))?\s*:\s*|\s+(?:is\s+|are\s+)?)" + STATUS, t, re.I):
        v = _status_word(m.group(2))
        if v:
            yield v, ("synoptic" if ":" in m.group(1) else "narrative"), m.start(), m.end()
    # label ... NN%  (percent of nuclei)
    for m in re.finditer(label + r"[^.%]{0,40}?(<|less than|over|>)?\s*(\d{1,3})\s*%", t, re.I):
        lt = (m.group(1) or "").lower() in ("<", "less than")
        pct = float(m.group(2))
        yield ("negative" if lt and pct <= 1 else _pct_status(pct)), "narrative", m.start(), m.end()
    # "estrogen receptors in neoplastic cell nuclei not found" / "... not detected"
    for m in re.finditer(label + r"[^.]{0,50}?\b(not found|not detected|not identified|absent)", t, re.I):
        yield "negative", "narrative", m.start(), m.end()
    # "estrogen receptor activity was judged to be. positive" / "... interpreted as negative"
    for m in re.finditer(label + r"[^%]{0,40}?(?:judged to be|interpreted as|reported as)\.?\s+" + STATUS, t, re.I):
        v = _status_word(m.group(1))
        if v:
            yield v, "narrative", m.start(), m.end()
    # combined "ER/PR: positive", "ER and PR negative"
    for m in re.finditer(r"\bER\s*(?:/|and)\s*PR\b(\s*:\s*|\s+(?:are\s+|both\s+)?)" + STATUS, t, re.I):
        v = _status_word(m.group(2))
        if v:
            yield v, "narrative", m.start(), m.end()


def find_her2(t):
    lab = r"HER2(?:/neu)?(?:\s*\((?:herceptest|IHC|FISH|CISH)\))?(?:\s+(?:IHC|by IHC|protein|test|immunohistochemistry|FISH|gene))?"
    for m in re.finditer(lab + r"(\s*(?:status|result|score)?\s*:\s*|\s+(?:is\s+|was\s+)?(?:interpreted as\s+)?)" + STATUS, t, re.I):
        v = _status_word(m.group(2))
        if v:
            yield v, ("synoptic" if ":" in m.group(1) else "narrative"), m.start(), m.end()
    # IHC score: 0 / 1+ / zero -> negative, 2+ -> equivocal, 3+ -> positive
    for m in re.finditer(lab + r"[^.]{0,25}?(?:score\s*(?:of\s*)?)?:?\s*\b(zero|0|1\+|2\+|3\+)", t, re.I):
        s = m.group(1).lower()
        v = {"zero": "negative", "0": "negative", "1+": "negative", "2+": "equivocal", "3+": "positive"}[s]
        yield v, "synoptic", m.start(), m.end()
    # FISH: amplified / not amplified
    for m in re.finditer(r"HER2(?:/neu)?[^.]{0,40}?\b(not amplified|non-?amplified|no amplification|amplified|amplification)", t, re.I):
        v = "negative" if re.match(r"not|non|no ", m.group(1), re.I) else "positive"
        yield v, "narrative", m.start(), m.end()


def find_t(t):
    for m in re.finditer(r"\b(?:y?p)T\s?(is|[0-4])(?![0-9])", t):   # pT2, pT 2c, pT2N1a
        yield (0 if m.group(1) == "is" else int(m.group(1))), "stage_code", m.start(), m.end()
    for m in re.finditer(r"\bT([0-4])[a-d]?[ ,]{0,3}N\s?[0-3XO]", t):  # "T2 N1a" without p
        yield int(m.group(1)), "stage_code", m.start(), m.end()
    for m in re.finditer(r"tumou?r extent\s*:\s*T([0-4])", t, re.I):
        yield int(m.group(1)), "synoptic", m.start(), m.end()


def find_n(t):
    for m in re.finditer(r"(?:\b|(?<=[0-9a-d]))(?:y?p)N\s?([0-3]|X|O(?![a-z]))", t):
        if m.group(1) != "X":
            yield (0 if m.group(1) == "O" else int(m.group(1))), "stage_code", m.start(), m.end()
    for m in re.finditer(r"\bp?T\s?[0-4][a-d]?[ ,]{0,3}N\s?([0-3]|O(?![a-z]))", t):
        yield (0 if m.group(1) == "O" else int(m.group(1))), "stage_code", m.start(), m.end()


def find_nodes_pos(t):
    """Positive lymph node count."""
    syn = [r"(?:lymph nodes|number of (?:lymph )?nodes) (?:positive|with (?:macro)?metastas[ie]s)\s*:\s*(\d+)",
           r"(?:total\s+)?number of (?:lymph\s+)?nodes containing metasta\w*[^:]{0,60}:\s*(\d+)",
           r"(?:total )?number of positive (?:lymph )?nodes\s*:?\s*(\d+)"]
    for pat in syn:
        for m in re.finditer(pat, t, re.I):
            yield int(m.group(1)), "synoptic", m.start(), m.end()
    narr = [r"(\d+)\s*/\s*(\d+)\s*(?:\)?\s*(?:lymph\s+)?(?:nodes?|positive|involved|with metasta))",
            r"(?:node status|lymph nodes?)\s*:?\s*(?:negative|positive)?\s*\(?(\d+)\s*/\s*(\d+)",
            r"(?:metasta\w*|carcinoma)[^.]{0,30}?\b(?:in\s+)?(\d+)\s+(?:of|out of)\s+(\d+)\s+(?:\w+\s+){0,2}(?:lymph\s+)?nodes?",
            r"(\d+)\s+(?:of|out of)\s+(\d+)\s+(?:\w+\s+){0,2}(?:lymph\s+)?nodes?\s+(?:are\s+|is\s+)?(?:positive|involved)"]
    for pat in narr:
        for m in re.finditer(pat, t, re.I):
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b <= 80:
                yield a, "narrative", m.start(), m.end()
    for m in re.finditer(r"(?:lymph\s+)?nodes?\s+(?:is|are)\.?\s+negative for (?:metastatic\s+)?(?:carcinoma|tumou?r|malignancy)|"
                         r"lymph nodes?[^.]{0,30}?(?:with\s+)?no evidence of metasta", t, re.I):
        yield 0, "narrative", m.start(), m.end()
    for m in re.finditer(r"(?:no|negative for)\s+(?:metastatic\s+)?(?:carcinoma|tumou?r|malignancy|metastas[ie]s)[^.]{0,40}?\(\s*0\s*/\s*(\d+)\s*\)", t, re.I):
        yield 0, "narrative", m.start(), m.end()


def find_margin(t):
    pos = [r"margins?\s*(?:status)?\s*:\s*(?:positive|involved)",
           r"margins?\s+(?:is\s+|are\s+)?(?:positive|involved)\s+(?:for|by|with)\s+(?:invasive|infiltrating|carcinoma|tumou?r)(?![^.:]{0,20}:)",
           r"(?:invasive|infiltrating)\s+(?:\w+\s+){0,2}carcinoma\s+(?:extends\s+to|is\s+present\s+at|involves|is\s+at)\s+(?:the\s+)?(?:\w+\s+){0,2}(?:inked\s+)?(?:surgical\s+)?margin",
           r"tumou?r\s+(?:extends\s+to|involves|is\s+present\s+at)\s+(?:the\s+)?(?:\w+\s+){0,2}(?:inked\s+)?margin"]
    neg = [r"margins?\s*(?:status)?\s*:\s*(?:negative|uninvolved|free|clear|not involved)",
           r"no involvement of the (?:surgical\s+)?margins?",
           r"margins?\s+(?:are\s+|is\s+)?(?:negative|free|uninvolved|clear|not involved)(?!\s+(?:by|of|for)\s+(?:dcis|ductal carcinoma in situ))",
           r"(?:all\s+)?(?:surgical\s+)?margins?\s+(?:are\s+|is\s+)?(?:free of|negative for)\s+(?:invasive\s+)?(?:carcinoma|tumou?r|neoplasm|malignancy)",
           r"margins?\s+(?:of\s+excision\s+)?(?:are\s+|is\s+)?(?:widely\s+)?(?:free|clear)"]
    for pats, v in ((pos, "positive"), (neg, "negative")):
        for pat in pats:
            for m in re.finditer(pat, t, re.I):
                yield v, ("synoptic" if ":" in m.group(0) else "narrative"), m.start(), m.end()


def find_histology(t):
    pats = [(r"(?:invasive|infiltrating)\s+(?:\w+\s+)?lobular\s+carcinoma|lobular\s+carcinoma,?\s+(?:invasive|infiltrating)", "lobular"),
            (r"(?:invasive|infiltrating)\s+(?:\w+\s+)?ductal\s+(?:adeno)?carcinoma|ductal\s+carcinoma,?\s+(?:invasive|infiltrating)|"
             r"invasive\s+carcinoma\s+(?:of\s+)?no\s+special\s+type|carcinoma\s+NST\b", "ductal"),
            (r"mucinous\s+(?:\(colloid\)\s+)?carcinoma|colloid\s+carcinoma", "mucinous")]
    for pat, v in pats:
        for m in re.finditer(pat, t, re.I):
            kind = "synoptic" if re.search(r"(?:histologic(?:al)?\s+type|diagnosis)\s*:\s*$", t[max(0, m.start() - 30):m.start()], re.I) else "narrative"
            yield v, kind, m.start(), m.end()


def find_listed(t, name):
    """'Tumor is negative for ER, PR and HER2' -> status for every receptor in the list."""
    names = {"ER": r"\bER\b|estrogen", "PR": r"\bPR\b|progesterone", "HER2": r"\bHER2\b|HER2/neu"}[name]
    for m in re.finditer(r"\b(positive|negative)\s+for\s+((?:ER|PR|HER2(?:/neu)?|estrogen|progesterone|receptors?|and|,|\s)+)", t, re.I):
        if re.search(names, m.group(2), re.I):
            yield m.group(1).lower(), "narrative", m.start(), m.end()


FINDERS = {"er": lambda t: [*find_receptor(t, "ER"), *find_listed(t, "ER")],
           "pr": lambda t: [*find_receptor(t, "PR"), *find_listed(t, "PR")],
           "her2": lambda t: [*find_her2(t), *find_listed(t, "HER2")], "t_major": find_t, "n_major": find_n,
           "nodes_pos": find_nodes_pos, "margin": find_margin, "histology": find_histology}


# ---------------------------------------------------------------------------
# 3-4. Filter + resolve
# ---------------------------------------------------------------------------
def resolve(fact, cands, t):
    if not cands:
        return None
    # Facts with a natural "most severe wins" rule: nodes / stage take the max
    # (a later specimen adds nodes; a summary line repeats the max), histology
    # reports "mixed" as other.
    values = [c[0] for c in cands]
    best_kind = max((c[1] for c in cands), key=lambda k: KIND_CONF[k])
    ev = snippet(t, cands[0][2], cands[0][3])
    if fact in ("nodes_pos", "t_major", "n_major"):
        v = max(values)
        top = next(c for c in cands if c[0] == v)
        return {"value": v, "conf": KIND_CONF[top[1]], "kind": top[1], "evidence": snippet(t, top[2], top[3])}
    if fact == "her2" and "equivocal" in values and set(values) - {"equivocal"}:
        # IHC 2+ is provisional; a definite result (usually FISH) is the final call.
        cands = [c for c in cands if c[0] != "equivocal"]
        values = [c[0] for c in cands]
        best_kind = max((c[1] for c in cands), key=lambda k: KIND_CONF[k])
        ev = snippet(t, cands[0][2], cands[0][3])
    if fact == "histology" and {"ductal", "lobular"} <= set(values):
        return {"value": "other", "conf": KIND_CONF["narrative"] * CONFLICT_FACTOR, "kind": "conflict",
                "evidence": "both ductal and lobular mentioned (mixed?)"}
    counts = Counter(values)
    if len(counts) == 1:
        return {"value": values[0], "conf": KIND_CONF[best_kind], "kind": best_kind, "evidence": ev}
    # Conflict: weight by evidence strength; majority wins at reduced confidence.
    score = Counter()
    for v, k, *_ in cands:
        score[v] += KIND_CONF[k]
    v, s = score.most_common(1)[0]
    top = next(c for c in cands if c[0] == v)
    share = s / sum(score.values())
    return {"value": v, "conf": round(KIND_CONF[top[1]] * share * (2 * CONFLICT_FACTOR), 3), "kind": "conflict",
            "evidence": snippet(t, top[2], top[3]) + f"  [conflict: {dict(counts)}]"}


def calibrated(sheet, cal):
    """Swap hand-set confidences for DEV-measured accuracy per (fact, kind); conflicts keep their penalty."""
    for fact, f in sheet.items():
        if f is None:
            continue
        base_kind = f.get("base_kind", f["kind"])
        c = cal["pair"].get(f"{fact}|{f['kind']}", cal["kind"].get(f["kind"]))
        if c is None and f["kind"] == "conflict":
            c = cal["kind"].get(base_kind, f["conf"])
        if c is not None:
            f["conf_raw"], f["conf"] = f["conf"], c
    return sheet


def read_report(text, naive=False, calibration=None):
    """report text -> {fact: {value, conf, kind, evidence} | None}
    calibration: table from calibrate.py (calibration.json); None = hand-set confidences."""
    t = normalize(text)
    sheet = {}
    for fact, finder in FINDERS.items():
        cands = list(finder(t))
        if naive:
            sheet[fact] = ({"value": cands[0][0], "conf": 1.0, "kind": "naive", "evidence": snippet(t, cands[0][2], cands[0][3])}
                           if cands else None)
            continue
        cands = [c for c in cands if not is_boilerplate(t, c[2], c[3])]
        sheet[fact] = resolve(fact, cands, t)
    # Derived: node count implies node status when no pN code is given.
    if not naive and sheet["n_major"] is None and sheet["nodes_pos"] is not None:
        np_ = sheet["nodes_pos"]
        sheet["n_major"] = {"value": 1 if np_["value"] >= 1 else 0, "conf": KIND_CONF["derived"],
                            "kind": "derived", "evidence": np_["evidence"]}
    if calibration and not naive:
        calibrated(sheet, calibration)
    return sheet
