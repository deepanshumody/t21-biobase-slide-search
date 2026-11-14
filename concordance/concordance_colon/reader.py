"""
READER (rule-based, colon): real colorectal pathology report -> fact sheet with evidence.

Reuses the shared machinery from ../concordance_breast/reader.py (OCR normalization,
boilerplate filter, conflict resolution, pT/pN finders, calibration). Adds colon facts:
lvi, pni, mucinous, residual, and a node finder that SUMS counts across specimens.
See concordance_colon_design.md, section 4.
"""
import importlib.util
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "breast_reader", os.path.join(_HERE, "..", "concordance_breast", "reader.py"))
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)          # shared: normalize, is_boilerplate, snippet, resolve, find_t, find_n, KIND_CONF

KIND_CONF = br.KIND_CONF
WORDNUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                         "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
NUM = r"(\d+|" + "|".join(WORDNUM) + r")"


def _n(s):
    s = s.lower()
    return int(s) if s.isdigit() else WORDNUM[s]


# ---------------------------------------------------------------------------
# Present / absent findings (LVI, PNI): "X: Not identified", "X is present", "no X"
# ---------------------------------------------------------------------------
POS = r"present|identified|positive|yes\b|seen"
NEG = r"not identified|not seen|not present|absent|negative|\bno\b|none"


def find_present(t, concept, positive_only=False):
    for m in re.finditer(concept, t, re.I):
        before = t[max(0, m.start() - 30):m.start()]
        if re.search(r"\b(no|without|negative for|free of)\s+(?:\w+\s+){0,2}$", before, re.I):
            if not positive_only:
                yield False, "narrative", m.start(), m.end()
            continue
        after = t[m.end():m.end() + 45]
        # Negative phrases are tried FIRST and without a filler word, so "Not identified" can't be
        # read as filler "Not" + positive "identified".
        cue = re.match(r"[\s:,.(-]*(?:is\s+|are\s+|was\s+)?(?:(" + NEG + r")|(?:\w+\s+)?(" + POS + r"|suspected|indeterminate))",
                       after, re.I)
        if not cue:
            continue
        w = (cue.group(1) or cue.group(2)).lower()
        cue_start = cue.start(1) if cue.group(1) else cue.start(2)
        if w in ("suspected", "indeterminate"):
            continue                      # equivocal statement -> no evidence either way
        v = not re.match(NEG, w, re.I)
        if positive_only and not v:
            continue
        kind = "synoptic" if ":" in after[:cue_start] else "narrative"
        yield v, kind, m.start(), m.end() + cue.end()


LVI = r"lympho-?\s?vascular(?:\s+space)?\s+invasion|angiolymphatic\s+invasion|lymphatic\s+(?:vessel\s+)?invasion|small\s+vessel\s+invasion"
VENOUS = r"(?:large\s+|extramural\s+)?venous\s+invasion|vascular\s+invasion|large\s+vessel\s+invasion"


def find_lvi(t):
    yield from find_present(t, LVI)
    yield from find_present(t, VENOUS, positive_only=True)   # venous invasion present also counts as LVI
    for m in re.finditer(r"\bL\s?([01])\s*,?\s*V\s?([012])\b", t):   # UICC codes "L1, V0"
        yield (m.group(1) == "1" or m.group(2) != "0"), "stage_code", m.start(), m.end()


def find_pni(t):
    yield from find_present(t, r"perineural\s+(?:invasion|infiltration|spread)|\bPn\s?1\b")
    for m in re.finditer(r"\bPn\s?([01])\b", t):
        yield m.group(1) == "1", "stage_code", m.start(), m.end()


def find_mucinous(t):
    """Mucinous = >50% mucin (WHO). 'with mucinous features/differentiation' or '<50%' -> not mucinous."""
    for m in re.finditer(r"mucinous\s+(?:\(colloid\)\s+)?adenocarcinoma|adenocarcinoma,?\s+mucinous(?:\s+type)?|"
                         r"colloid\s+carcinoma|carcinoma\s+mucinosum|adenocarcinoma\s+mucinosum", t, re.I):
        ctx = t[max(0, m.start() - 40):m.end() + 40]
        if re.search(r"<\s*50\s*%|less than 50|partim|partially", ctx, re.I):
            yield False, "narrative", m.start(), m.end()
        else:
            yield True, "synoptic" if re.search(r"(?:histologic(?:al)?\s+type|diagnosis)\s*:\s*$", t[max(0, m.start() - 30):m.start()], re.I) else "narrative", m.start(), m.end()
    for m in re.finditer(r"(?:with|showing)\s+(?:focal\s+|extensive\s+)?mucinous\s+(?:features|differentiation|component)", t, re.I):
        ctx = t[m.end():m.end() + 40]
        yield (not re.search(r"<\s*50|less than 50", ctx) and bool(re.search(r">\s*50|more than 50|greater than 50", ctx))), "narrative", m.start(), m.end()
    # Plain adenocarcinoma stated as the histologic type (no mucinous mention) -> not mucinous.
    if not re.search(r"mucin", t, re.I):
        m = re.search(r"(?:histologic(?:al)?\s+type\s*:\s*)?(?:invasive\s+)?adenocarcinoma", t, re.I)
        if m:
            yield False, "derived", m.start(), m.end()


def find_residual(t):
    """Tumor left at resection: margins involved (R1) vs clear (R0)."""
    for m in re.finditer(r"(?:extent of resection\s*:\s*|\b)R([012])(?:\s*:|\s+resection|\b(?=[^.]{0,20}(?:complete|incomplete|margin)))", t, re.I):
        yield m.group(1) != "0", "stage_code", m.start(), m.end()
    for m in re.finditer(r"\bV\s?[012]\s*,?\s*R\s?([012])\b", t):        # "L1, V0, R0"
        yield m.group(1) != "0", "stage_code", m.start(), m.end()
    for m in re.finditer(r"(?:surgical|resection|all)?\s*margins?\s*(?:\([^)]*\))?\s*:?\s*(?:are\s+|is\s+)?"
                         r"(free of|negative|uninvolved|clear|not involved)", t, re.I):
        yield False, ("synoptic" if ":" in m.group(0) else "narrative"), m.start(), m.end()
    for m in re.finditer(r"margins?\s*(?:\([^)]*\))?\s*:?\s*(?:is\s+|are\s+)?(?<!un)(involved|positive)\s+(?:by|for|with)\s+(?:invasive\s+)?(?:adeno)?carcinoma|"
                         r"carcinoma\s+(?:extends\s+to|is\s+present\s+at|involves)\s+(?:the\s+)?(?:\w+\s+){0,2}margin", t, re.I):
        yield True, "narrative", m.start(), m.end()


def find_nodes(t):
    """Yields (positive, examined, kind, start, end). Excludes 'page 1/2'."""
    pats = [(r"lymph nodes?\s*:?\s*(?:positive|negative)?\s*\(?\s*(\d+)\s*/\s*(\d+)", "synoptic"),
            (r"pN\s?[0-2][a-c]?\s*\(\s*(\d+)\s*/\s*(\d+)\s*\)", "stage_code"),
            (r"(?<!page )(?<!page)\b(\d+)\s*/\s*(\d+)\s*\)?\s*(?:\w+\s+){0,2}(?:lymph\s+)?nodes?", "narrative"),
            (r"(?:involv\w*|metasta\w*\s+(?:to|in))\s+" + NUM + r"\s+(?:of|out of)\s+" + NUM + r"\s+(?:\w+\s+){0,2}(?:lymph\s+)?nodes?", "narrative"),
            (NUM + r"\s+(?:of|out of)\s+" + NUM + r"\s+(?:\w+\s+){0,2}(?:lymph\s+)?nodes?\s+(?:are\s+|is\s+)?(?:positive|involved)", "narrative"),
            (r"(?:metasta\w*|carcinoma|tumou?r)[^.]{0,30}?\(\s*(\d+)\s*/\s*(\d+)\s*\)", "narrative")]
    for pat, kind in pats:
        for m in re.finditer(pat, t, re.I):
            a, b = _n(m.group(1)), _n(m.group(2))
            if a <= b <= 150 and not re.search(r"page\s*$", t[max(0, m.start() - 6):m.start()], re.I):
                yield a, b, kind, m.start(), m.end()
    for m in re.finditer(r"(?:all\s+)?" + NUM + r"\s+(?:\w+\s+){0,2}lymph nodes?[^.]{0,20}?(?:negative|benign|free of|no evidence of)", t, re.I):
        yield 0, _n(m.group(1)), "narrative", m.start(), m.end()
    for m in re.finditer(r"(?:no|negative for)\s+(?:metastatic\s+)?(?:carcinoma|tumou?r|malignancy)[^.]{0,30}?\(\s*0\s*/\s*(\d+)\s*\)", t, re.I):
        yield 0, int(m.group(1)), "narrative", m.start(), m.end()


def resolve_nodes(cands, t):
    """Synoptic/stage-code totals win (max); otherwise SUM unique (pos, examined) pairs across specimens."""
    if not cands:
        return None
    strong = [c for c in cands if c[2] in ("synoptic", "stage_code")]
    if strong:
        top = max(strong, key=lambda c: (c[0], c[1]))
        return {"value": top[0], "conf": KIND_CONF[top[2]], "kind": top[2], "evidence": br.snippet(t, top[3], top[4])}
    uniq = {(c[0], c[1]): c for c in cands}
    total = sum(a for a, _ in uniq)
    first = next(iter(uniq.values()))
    kind = "narrative" if len(uniq) == 1 else "derived"
    return {"value": total, "conf": KIND_CONF[kind], "kind": kind,
            "evidence": br.snippet(t, first[3], first[4]) + (f"  [summed {sorted(uniq)}]" if len(uniq) > 1 else "")}


def resolve_any_true(fact, cands, t):
    """LVI / PNI / residual: any credible positive -> True (findings are reported where seen)."""
    if not cands:
        return None
    pos = [c for c in cands if c[0] is True]
    if pos and len(pos) < len(cands):
        neg_strong = [c for c in cands if c[0] is False and c[1] == "synoptic"]
        pos_strong = [c for c in pos if c[1] in ("synoptic", "stage_code")]
        if neg_strong and not pos_strong:      # synoptic "Not identified" beats a stray narrative hit
            pos = []
    pick = pos[0] if pos else max(cands, key=lambda c: KIND_CONF[c[1]])
    conflict = len({c[0] for c in cands}) > 1
    kind = "conflict" if conflict else pick[1]
    conf = KIND_CONF[pick[1]] * (br.CONFLICT_FACTOR * 1.5 if conflict else 1)
    return {"value": bool(pick[0]), "conf": round(conf, 3), "kind": kind, "base_kind": pick[1],
            "evidence": br.snippet(t, pick[2], pick[3])}


FACT_FINDERS = {"lvi": find_lvi, "pni": find_pni, "residual": find_residual, "mucinous": find_mucinous}


def read_report(text, naive=False, calibration=None):
    t = br.normalize(text)
    keep = (lambda c: True) if naive else (lambda c: not br.is_boilerplate(t, c[-2], c[-1]))
    sheet = {}
    for fact, finder in (("t_major", br.find_t), ("n_major", br.find_n)):
        cands = [c for c in finder(t) if keep(c)]
        if naive:
            sheet[fact] = {"value": cands[0][0], "conf": 1.0, "kind": "naive", "evidence": br.snippet(t, cands[0][2], cands[0][3])} if cands else None
        else:
            sheet[fact] = br.resolve(fact, cands, t)
    nodes = [c for c in find_nodes(t) if keep(c)]
    if naive:
        sheet["nodes_pos"] = {"value": nodes[0][0], "conf": 1.0, "kind": "naive", "evidence": ""} if nodes else None
    else:
        sheet["nodes_pos"] = resolve_nodes(nodes, t)
    for fact, finder in FACT_FINDERS.items():
        cands = [c for c in finder(t) if keep(c)]
        if naive:
            sheet[fact] = {"value": cands[0][0], "conf": 1.0, "kind": "naive", "evidence": br.snippet(t, cands[0][2], cands[0][3])} if cands else None
        elif fact == "mucinous":
            sheet[fact] = br.resolve(fact, [(("yes" if c[0] else "no"),) + tuple(c[1:]) for c in cands], t)
            if sheet[fact]:
                sheet[fact]["value"] = sheet[fact]["value"] == "yes"
        else:
            sheet[fact] = resolve_any_true(fact, cands, t)
    if not naive and sheet["n_major"] is None and sheet["nodes_pos"] is not None:
        np_ = sheet["nodes_pos"]
        sheet["n_major"] = {"value": 1 if np_["value"] >= 1 else 0, "conf": KIND_CONF["derived"],
                            "kind": "derived", "evidence": np_["evidence"]}
    if calibration and not naive:
        br.calibrated(sheet, calibration)
    return sheet
