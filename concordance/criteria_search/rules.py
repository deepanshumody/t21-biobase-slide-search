"""
STAGE 3 of 3: RULES  (card -> yes/no for each criterion)

Pipeline:  parse.py  ->  card.py  ->  rules.py

One function per criterion. Each one:
  1. checks the organ first (a breast rule never matches a colon report)
  2. then checks the criterion's conditions on the card

A report is checked against ALL 30 rules ("select all that apply").
None values (report doesn't say) never satisfy a condition.

Lines marked "# ASSUMPTION:" are readings of an unclear criterion; train F1 in
evaluate.py decides whether they are right. See criteria_search_design.md section 5.
"""
import re


def ge(x, n):
    """x >= n, but None never matches."""
    return x is not None and x >= n


def le(x, n):
    return x is not None and x <= n


def node_positive(c):
    # ASSUMPTION: node-positive = pN1 or higher (this includes pN1c tumor
    # deposits), falling back to the positive-node count when no pN is given.
    if c["n_major"] is not None:
        return c["n_major"] >= 1
    return ge(c["nodes_pos"], 1)


# ---------------------------------------------------------------------------
# BREAST
# ---------------------------------------------------------------------------
def c01(c):  # HER2 negative with 1 or more positive lymph nodes
    # ASSUMPTION: "equivocal" HER2 does not count as negative.
    return c["organ"] == "breast" and c["her2"] == "negative" and ge(c["nodes_pos"], 1)

def c02(c):  # ER positive and PR negative
    return c["organ"] == "breast" and c["er"] == "positive" and c["pr"] == "negative"

def c03(c):  # triple negative
    return (c["organ"] == "breast" and c["er"] == "negative"
            and c["pr"] == "negative" and c["her2"] == "negative")

def c04(c):  # LVI present and tumor > 20 mm
    return c["organ"] == "breast" and c["lvi"] is True and (c["size_mm"] or 0) > 20

def c05(c):  # negative margins, invasive carcinoma within 3 mm of closest margin
    # ASSUMPTION: "within 3 mm" means <= 3 mm.
    return c["organ"] == "breast" and c["margin_neg"] is True and le(c["margin_mm"], 3)

def c06(c):  # multifocal, patient under 60
    # Age bands: "under 60" = bands starting below 60 (50-59 and younger).
    return c["organ"] == "breast" and c["multifocal"] is True and c["age_min"] is not None and c["age_min"] < 60

def c07(c):  # Nottingham grade 3, no LVI
    return c["organ"] == "breast" and c["nottingham"] == 3 and c["lvi"] is False


# ---------------------------------------------------------------------------
# COLON
# ---------------------------------------------------------------------------
def c08(c):  # positive lymph nodes (stage III)
    return c["organ"] == "colon" and node_positive(c)

def c09(c):  # mucinous adenocarcinoma
    return c["organ"] == "colon" and c["histology"].startswith("mucinous")

def c10(c):  # tumor deposits present
    return c["organ"] == "colon" and c["deposits"] is True

def c11(c):  # no positive nodes and LVI present
    # ASSUMPTION: "no positive lymph nodes" = 0 positive nodes in the count.
    return c["organ"] == "colon" and c["nodes_pos"] == 0 and c["lvi"] is True

def c12(c):  # pT4
    return c["organ"] == "colon" and c["t_major"] == 4

def c13(c):  # >= 5 cm and no PNI
    return c["organ"] == "colon" and ge(c["size_mm"], 50) and c["pni"] is False


# ---------------------------------------------------------------------------
# LUNG
# ---------------------------------------------------------------------------
def c14(c):  # visceral pleural invasion
    return c["organ"] == "lung" and c["vpi"] is True

def c15(c):  # squamous cell carcinoma with involved bronchial margin
    return (c["organ"] == "lung" and "squamous" in c["histology"]
            and "bronchial margin involved" in c["margins"])

def c16(c):  # adenocarcinoma with >= 1 positive node
    return c["organ"] == "lung" and "adenocarcinoma" in c["histology"] and ge(c["nodes_pos"], 1)


# ---------------------------------------------------------------------------
# PROSTATE
# ---------------------------------------------------------------------------
def c17(c):  # Grade Group 4 or 5
    return c["organ"] == "prostate" and ge(c["grade_group"], 4)

def c18(c):  # seminal vesicle invasion
    return c["organ"] == "prostate" and c["svi"] is True

def c19(c):  # positive margin and no EPE
    return c["organ"] == "prostate" and c["margins"].startswith("positive") and c["epe"] is False

def c20(c):  # PNI present and LVI not identified
    return c["organ"] == "prostate" and c["pni"] is True and c["lvi"] is False


# ---------------------------------------------------------------------------
# STOMACH
# ---------------------------------------------------------------------------
def c21(c):  # HER2 positive
    return c["organ"] == "stomach" and c["her2"] == "positive"

def c22(c):  # poorly cohesive (diffuse, not mixed) with >= 1 positive node
    # "Mixed adenocarcinoma (glandular and poorly cohesive ...)" starts with "mixed", so it's excluded.
    return c["organ"] == "stomach" and c["histology"].startswith("poorly cohesive") and ge(c["nodes_pos"], 1)

def c23(c):  # pT4
    return c["organ"] == "stomach" and c["t_major"] == 4


# ---------------------------------------------------------------------------
# KIDNEY
# ---------------------------------------------------------------------------
def c24(c):  # clear cell RCC, ISUP 3 or 4
    return c["organ"] == "kidney" and "clear cell" in c["histology"] and ge(c["isup"], 3)

def c25(c):  # sarcomatoid or rhabdoid features
    return c["organ"] == "kidney" and c["sarcomatoid"] is True

def c26(c):  # extends into renal vein or IVC
    # ASSUMPTION: "segmental branches of the renal vein" counts.
    return c["organ"] == "kidney" and ("renal vein" in c["extent"] or "vena cava" in c["extent"])


# ---------------------------------------------------------------------------
# SKIN
# ---------------------------------------------------------------------------
def c27(c):  # BCC with involved deep margin
    # Read the Margins field ONLY ("Depth" text can also mention the deep margin).
    # Wordings seen in train: "carcinoma extends to the deep margin",
    # "extends to the peripheral and deep margin", "deep margin involved by carcinoma",
    # "peripheral and deep margins involved by carcinoma".
    deep_involved = re.search(r"extends to the (?:peripheral and )?deep margin|deep margins? involved",
                              c["margins"]) is not None
    return c["organ"] == "skin" and c["histology"].startswith("basal cell carcinoma") and deep_involved

def c28(c):  # invasive SCC, grade 2 or 3
    return (c["organ"] == "skin" and c["histology"].startswith("invasive squamous cell carcinoma")
            and c["scc_grade"] in (2, 3))


# ---------------------------------------------------------------------------
# CROSS-FIELD (demographics)
# ---------------------------------------------------------------------------
def c29(c):  # age >= 70 with node-positive colon cancer
    return c08(c) and ge(c["age_min"], 70)

def c30(c):  # female lung cancer, reported 2023 or 2024
    return c["organ"] == "lung" and c["sex"] == "F" and c["year"] in (2023, 2024)


# Registry: criterion id -> rule. evaluate.py and run.py iterate this.
RULES = {name: fn for name, fn in sorted(globals().items())
         if len(name) == 3 and name[0] == "c" and name[1:].isdigit()}
