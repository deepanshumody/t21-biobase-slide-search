#!/usr/bin/env python3
"""Build a one-page C2 explanation from the recorded validation results."""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "output/c2/validation_summary.json").read_text())
OUT = ROOT / "output/pdf/c2_summary.pdf"
FONT_DIR = Path("/System/Library/Fonts/Supplemental")
for name, file in [("Arial", "Arial.ttf"), ("Arial-Bold", "Arial Bold.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold")
INK = colors.HexColor("#172B3A")
TEAL = colors.HexColor("#087C83")
MUTED = colors.HexColor("#536674")
LIGHT = colors.HexColor("#EDF5F5")
RULE = colors.HexColor("#D9E5E9")
WIDTH = 504
STYLES = {
    "eyebrow": ParagraphStyle("eyebrow", fontName="Arial-Bold", fontSize=8.5, leading=11, textColor=TEAL, spaceAfter=8),
    "title": ParagraphStyle("title", fontName="Arial-Bold", fontSize=25, leading=30, textColor=INK, spaceAfter=8),
    "body": ParagraphStyle("body", fontName="Arial", fontSize=10.2, leading=14.1, textColor=INK, spaceAfter=6),
    "heading": ParagraphStyle("heading", fontName="Arial-Bold", fontSize=11.3, leading=15, textColor=TEAL, spaceBefore=10, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Arial", fontSize=8.5, leading=11.5, textColor=MUTED, spaceAfter=5),
    "formula": ParagraphStyle("formula", fontName="Arial-Bold", fontSize=10.5, leading=14, textColor=TEAL),
    "head": ParagraphStyle("head", fontName="Arial-Bold", fontSize=9.1, leading=12, textColor=colors.white),
    "cell": ParagraphStyle("cell", fontName="Arial", fontSize=10.1, leading=13, textColor=INK),
}


def p(text, kind="body"):
    return Paragraph(text, STYLES[kind])


def footer(canvas, doc):
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(54, 38, 558, 38)
    canvas.setFont("Arial", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(54, 24, "TEAM T21  |  Biobase challenge  |  November 14, 2026")
    canvas.drawRightString(558, 24, "C2 SUMMARY  /  1")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    story = [
        p("BIOBASE / C2 COMPLETION NOTE", "eyebrow"),
        p("Finding similar pathology slides", "title"),
        p("We combined C1 organ predictions with visual similarity to return ten ranked matches for each of the 67 query slides."),
        p("263 slides searched  &nbsp; | &nbsp;  190 organ labels for training  &nbsp; | &nbsp;  670 ranked results", "small"),
        p("What we changed", "heading"),
        p("<b>1. Matched the scoring rule.</b> C2 measures how often the top 1, 5, and 10 results share the query's organ group. We therefore added organ evidence to the supplied GigaPath visual-similarity baseline."),
        p("<b>2. Reused C1.</b> The existing three-classifier ensemble uses supplied GigaPath and BiomedCLIP features plus DINOv2 and H-optimus tile statistics. Known gallery labels are used directly; unlabelled slides receive model-derived organ scores that retain uncertainty."),
        p("<b>3. Combined the evidence.</b> Candidates are ranked by organ agreement and rescaled GigaPath cosine similarity. Repeated validation selected the blend below. Each query is excluded from its own results, with no duplicate matches."),
    ]
    weight = DATA["final_weight"]
    formula = Table([[p(f"Final score = {weight:.0%} organ agreement + {1 - weight:.0%} visual similarity", "formula")]], colWidths=[WIDTH])
    formula.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.extend([
        Spacer(1, 3), formula,
        p("How we checked it", "heading"),
        p("Both methods were compared on the same 188 labelled slides with GigaPath vectors, using five repeated four-fold runs. Query-fold labels were hidden from training and ranking. Three repeated inner four-fold runs selected the blend using training data only."),
    ])
    headers = ["Internal validation", "Top 1", "Top 5", "Top 10"]
    rows = [[p(x, "head") for x in headers]]
    for label, key in [("GigaPath baseline", "baseline"), ("Organ-aware retrieval", "organ_aware")]:
        rows.append([p(label, "cell")] + [p(f"{DATA[key][f'p_at_{k}']:.1%}", "cell") for k in [1, 5, 10]])
    rows.append([p("Gain (percentage points)", "cell")] + [p(f"+{100 * DATA['paired_gain'][f'p_at_{k}']:.1f}", "cell") for k in [1, 5, 10]])
    table = Table(rows, colWidths=[234, 90, 90, 90], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("BACKGROUND", (0, 2), (-1, 2), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE),
    ]))
    story.extend([
        table,
        p("What the results mean", "heading"),
        p("<b>These are internal estimates, not official challenge scores.</b> No official held-out labels were used. C1 feature choices were previously explored on these data, and the final gallery is larger. Rare organs have few matches; patient overlap cannot be ruled out. Matching organs does not establish matching diagnoses."),
        p("Delivered and verified", "heading"),
        p("The completed submission is <b>output/c2/submission_similar.csv</b>, with per-match evidence, an uncertainty review queue, validation records, and reproduction code. All 11 C1/C2 tests, new-code lint, and artifact audits passed. The regenerated baseline exactly matches the archived baseline."),
        Spacer(1, 3),
        p("Sources: pack_slides/README.md; output/c2/validation_summary.json; scripts/c2_retrieval.py. Official scoring remains to be completed.", "small"),
    ])
    doc = SimpleDocTemplate(str(OUT), pagesize=(612, 792), leftMargin=48, rightMargin=48,
                            topMargin=37, bottomMargin=48, title="C2: Finding similar pathology slides",
                            author="Team T21", subject="Short explanation of the C2 method, validation, and deliverables")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    main()
