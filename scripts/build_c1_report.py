#!/usr/bin/env python3
"""Build the C1 methods report from the recorded experiment artifacts."""
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/c1_methodology_report.pdf"
DATA = json.loads((ROOT / "output/c1_improved/validation_summary.json").read_text())
ORIGINAL = json.loads((ROOT / "output/c1/validation_summary.json").read_text())
FONT_ROOT = Path("/System/Library/Fonts/Supplemental")
for name, filename in [("Arial", "Arial.ttf"), ("Arial-Bold", "Arial Bold.ttf"),
                       ("Arial-Italic", "Arial Italic.ttf"), ("Code", "Courier New.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_ROOT / filename)))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-Bold")
INK = colors.HexColor("#172B3A")
TEAL = colors.HexColor("#087C83")
GREY = colors.HexColor("#556673")
LIGHT = colors.HexColor("#EEF5F5")
RULE = colors.HexColor("#DAE3E8")
WIDTH = 516
STYLES = {
    "body": ParagraphStyle("body", fontName="Arial", fontSize=10, leading=14.3, textColor=INK, spaceAfter=8),
    "small": ParagraphStyle("small", fontName="Arial", fontSize=8.6, leading=11.6, textColor=GREY, spaceAfter=6),
    "table": ParagraphStyle("table", fontName="Arial", fontSize=9, leading=12, textColor=INK),
    "table_small": ParagraphStyle("table_small", fontName="Arial", fontSize=8.1, leading=10.7, textColor=INK),
    "table_head": ParagraphStyle("table_head", fontName="Arial-Bold", fontSize=8.6, leading=11.3, textColor=colors.white),
    "h1": ParagraphStyle("h1", fontName="Arial-Bold", fontSize=23, leading=28, textColor=INK, spaceAfter=14),
    "h2": ParagraphStyle("h2", fontName="Arial-Bold", fontSize=12, leading=16, textColor=TEAL, spaceBefore=9, spaceAfter=7),
    "eyebrow": ParagraphStyle("eyebrow", fontName="Arial-Bold", fontSize=8.8, leading=12, textColor=TEAL, spaceAfter=8),
    "code": ParagraphStyle("code", fontName="Code", fontSize=8.5, leading=12.5, textColor=INK, spaceAfter=2),
    "callout": ParagraphStyle("callout", fontName="Arial-Bold", fontSize=10.5, leading=15, textColor=TEAL),
}


def p(text, style="body"):
    return Paragraph(text, STYLES[style])


def table(headers, rows, widths, small=False):
    style = "table_small" if small else "table"
    cells = [[p(escape(str(value)), "table_head") for value in headers]]
    cells += [[p(escape(str(value)), style) for value in row] for row in rows]
    result = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FA")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE),
    ]))
    return result


def callout(text):
    t = Table([[p(text, "callout")]], colWidths=[WIDTH])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 11), ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))
    return t


def page_title(number, title, subtitle=None):
    elements = [p(f"METHODS REPORT / {number:02d}", "eyebrow"), p(title, "h1")]
    if subtitle:
        elements.append(p(subtitle, "small"))
    return elements


class ComparisonPlot(Flowable):
    """Vector plot of the paired validation repeats with an explicit axis."""
    def __init__(self, rows):
        super().__init__()
        self.rows = rows
        self.width = WIDTH
        self.height = 148

    def draw(self):
        c = self.canv
        x0, x1, y0, y1 = 36, 502, 26, 115
        for value in [82, 84, 86, 88]:
            y = y0 + (value - 81) / 8 * (y1 - y0)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.4)
            c.line(x0, y, x1, y)
            c.setFont("Arial", 8)
            c.setFillColor(GREY)
            c.drawRightString(x0 - 7, y - 2.5, f"{value}%")
        for key, color, offset in [("old_accuracy", colors.HexColor("#8998A5"), -2), ("new_accuracy", TEAL, 2)]:
            points = []
            for index, row in enumerate(self.rows):
                x = x0 + index * (x1 - x0) / (len(self.rows) - 1) + offset
                y = y0 + (row[key] * 100 - 81) / 8 * (y1 - y0)
                points.append((x, y))
            c.setStrokeColor(color)
            c.setLineWidth(1.2)
            for left, right in zip(points, points[1:]):
                c.line(*left, *right)
            c.setFillColor(color)
            for x, y in points:
                c.circle(x, y, 2.6, fill=1, stroke=0)
        c.setFillColor(GREY)
        c.setFont("Arial", 8)
        for index, row in enumerate(self.rows):
            x = x0 + index * (x1 - x0) / (len(self.rows) - 1)
            c.drawCentredString(x, 12, str(row["seed"]))
        c.setFont("Arial-Bold", 8.3)
        c.setFillColor(TEAL)
        c.drawString(36, 134, "New ensemble")
        c.setFillColor(colors.HexColor("#8998A5"))
        c.drawString(123, 134, "Original selection procedure")
        c.setFont("Arial", 7.5)
        c.setFillColor(GREY)
        c.drawRightString(502, 134, "x-axis: split seed; y-axis: accuracy")


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.6)
    canvas.line(48, 748, 564, 748)
    canvas.line(48, 40, 564, 40)
    canvas.setFont("Arial-Bold", 8)
    canvas.setFillColor(TEAL)
    canvas.drawString(48, 761, "BIOBASE / TASK C1")
    canvas.setFont("Arial", 8)
    canvas.setFillColor(GREY)
    canvas.drawRightString(564, 761, "14 NOVEMBER 2026")
    canvas.drawString(48, 25, "Organ classification | Internal validation; official held-out score unknown")
    canvas.drawRightString(564, 25, str(document.page))
    canvas.restoreState()


def build():
    story = []
    story += page_title(1, "Classifying the organs<br/>in 67 held-out slides", "Biobase challenge | Method, experiments, results and reproducibility")
    story.append(p("The final submission uses an equal-weight ensemble of three ridge classifiers built on pretrained image embeddings. Two classifiers add tile-distribution summaries to GigaPath and BiomedCLIP; the third puts more weight on GigaPath. All 190 slides with organ labels are used for the final fit."))
    story.append(callout("Internal validation: 85.64% for the new ensemble, 85.00% for the original selection procedure and 85.27% for the original fixed classifier. The gain is small and uncertain. [4]"))
    story.append(Spacer(1, 12))
    story.append(p("Task and data", "h2"))
    story.append(p("Task C1 requires one organ or organ-group label per held-out slide, submitted as a CSV with columns <b>slide_id,organ</b>. Accuracy is the scoring metric. The data contain 15 organ groups from four suppliers. The synthetic report dataset is separate and was not used. [1]"))
    story.append(table(["Data partition", "Slides", "How it was used"], [
        ["All supplied slides", "263", "Manifest and image-feature inventory"],
        ["Non-held-out slides", "196", "Six have no organ label"],
        ["Usable organ-labelled slides", "190", "Final model fitting"],
        ["Common comparison cohort", "188", "Paired original/new validation"],
        ["Held-out slides", "67", "Prediction only; answer key not used"],
    ], [175, 50, 291]))
    story.append(Spacer(1, 10))
    story.append(p("Why 188 for comparison but 190 for the final fit?", "h2"))
    story.append(p("Two labelled slides lack GigaPath vectors: SUPP-03-bb_03_wsi_0004 and SUPP-03-bb_03_wsi_0005. The original comparison excluded them. The final implementation represents a missing feature block with zeros, allowing their other image features and organ labels to contribute. Paired comparisons retain the original 188-slide cohort. [2, 4]"))
    story.append(p("Workflow", "h2"))
    story.append(p("Inspect data and run baseline &gt; build normalized image features &gt; select regularization inside validation folds &gt; average three classifiers &gt; fit on all labelled slides &gt; validate the 67-row submission."))
    story.append(PageBreak())

    story += page_title(2, "How the final model works")
    story.append(p("1. Normalize the pretrained image representations", "h2"))
    story.append(p("The supplied slide vectors are mean-pooled tile representations, not newly computed GigaPath slide-transformer outputs. Each slide vector is L2-normalized. The final model uses the supplied 1,536-dimensional GigaPath and 512-dimensional BiomedCLIP slide vectors. Pretrained encoders remain frozen. [2]"))
    story.append(p("2. Preserve variation between tiles", "h2"))
    story.append(p("For DINOv2 and H-optimus, the stored int8 tile vectors are divided by their scale factor, 127, and each tile vector is L2-normalized. For every feature coordinate, the 10th, 50th and 90th percentiles across a slide's tiles are calculated, concatenated, then L2-normalized. This gives 1,152 DINOv2 features and 4,608 H-optimus features per slide. These summaries retain distributional information that a mean alone discards. [2]"))
    story.append(p("3. Fit three complementary ridge classifiers", "h2"))
    story.append(p("Let G and B be cosine-similarity matrices for GigaPath and BiomedCLIP. Let D and H be the corresponding dot-product matrices for normalized DINOv2 and H-optimus quantile features. The weighted kernels below are equivalent to linear models on appropriately weighted, concatenated feature blocks."))
    story.append(table(["Classifier", "Kernel", "Final alpha"], [
        ["DINOv2 distribution", "0.375 G + 0.375 B + 0.25 D", "0.01"],
        ["H-optimus distribution", "0.375 G + 0.375 B + 0.25 H", "0.10"],
        ["GigaPath-weighted", "0.75 G + 0.25 B", "0.30"],
    ], [155, 291, 70]))
    story.append(Spacer(1, 9))
    story.append(p("For each classifier, Y contains one-hot organ labels. Ridge coefficients A solve:", "body"))
    story.append(p("(K_train + alpha * I) A = Y", "code"))
    story.append(p("query_scores = K_query,train A", "code"))
    story.append(Spacer(1, 5))
    story.append(p("Regularization limits coefficient magnitude, which helps when the number of image features exceeds the number of labelled slides. The implementation solves this system numerically; no neural-network fine-tuning is needed. [2, 4]"))
    story.append(p("4. Average the scores and choose one organ", "h2"))
    story.append(p("The three class-score vectors are averaged equally, and the class with the largest average score is selected. The final feature families are fixed; each family's alpha is chosen from 0.003, 0.01, 0.03, 0.1, 0.3 and 1.0 using training-only leave-one-out accuracy. Scores and score margins are not calibrated probabilities."))
    story.append(PageBreak())

    story += page_title(3, "How performance was measured")
    story.append(p("Nested validation on the same slides", "h2"))
    story.append(p("The original and new procedures were evaluated on identical splits of the 188-slide comparison cohort. Ten random seeds each generate three stratified outer folds, keeping rare-class examples apart so every outer training fold retains each organ. Each slide is predicted once per repeat. [4]"))
    story.append(p("Within each outer training set, leave-one-out validation chooses alpha for each of the three feature families. The selected models are then fitted on that outer training set and evaluated on its untouched validation fold. Each slide's tiles stay together. No validation targets enter that fold's classifier fit."))
    story.append(table(["Method", "Mean accuracy", "What is selected"], [
        ["Original selection procedure", "85.00%", "Best of the original 24 candidates within each training fold"],
        ["Original fixed classifier", "85.27%", "50/50 GigaPath/BiomedCLIP ridge, alpha = 0.1"],
        ["Final three-model ensemble", "85.64%", "Alpha per fixed feature family within each training fold"],
    ], [175, 92, 249]))
    story.append(Spacer(1, 9))
    story.append(ComparisonPlot(DATA["comparison"]))
    story.append(p("Figure 1. Accuracy by split seed. The new procedure exceeds the original selection procedure in seven repeats, ties in two and is lower in one. Repeats reuse the same slides; they are not independent test sets.", "small"))
    story.append(p("What the gain means", "h2"))
    story.append(p("The gain over the original selection procedure is <b>0.64 percentage points</b>. A paired slide-level bootstrap gives an approximate 95% interval of <b>-0.27 to +1.60 percentage points</b>. For each slide, correctness differences are averaged across repeats; 10,000 bootstrap samples then resample slides, using seed 822. The interval includes zero and does not account for every source of development bias."))
    story.append(p("A separate validation run on all 190 labelled slides averages 85.11%; it is not the paired 188-slide comparison. The earlier 84.40% estimate for the original procedure used only seeds 17, 29 and 43. The different baseline estimates reflect different splits, not a changed original model. [3, 4]", "small"))
    story.append(PageBreak())

    story += page_title(4, "Experiments and decisions")
    story.append(p("Development started with the supplied cosine nearest-neighbour baseline and then tested lightweight classifiers on frozen image features. Larger pathology-specific checkpoints could not be downloaded in this execution environment, so new image encoding used a cached DINOv2 ViT-S/14 model on CPU. [3, 5, 6]"))
    story.append(table(["Experiment", "Evidence and decision"], [
        ["Initial embedding benchmark", "Compared four supplied models, nearest-neighbour variants and ridge regression. The initial GigaPath/BiomedCLIP ridge model reached 88.30% exploratory leave-one-out accuracy; the initial three-repeat nested estimate was 84.40%."],
        ["Tile distribution summaries", "Tested means, standard deviations and quantiles. DINOv2 quantiles combined with GigaPath/BiomedCLIP reached 170/188 (90.43%) in exploratory leave-one-out screening. DINOv2 and H-optimus quantiles were retained."],
        ["Broad feature and kernel search", "Tested feature weights, additional model combinations and radial-basis kernels. A broad model search was less consistent than the final fixed three-family ensemble, so the final model varies regularization only."],
        ["20x tile embeddings", "Removed all 461 listed blank tiles from 7,354 tiles and encoded the remaining 6,893 with cached DINOv2. No clear validation benefit was found; these features were excluded from the final model."],
        ["Whole-slide thumbnail views", "Encoded one full view and four quadrants for each of 263 slides, giving 1,315 views. The strongest tested combination reached 166/188 (88.30%) exploratory leave-one-out accuracy. Excluded."],
        ["Support-vector classifiers", "Tested six feature kernels with C = 1, 10 and 100. Best exploratory leave-one-out result: 157/188 (83.51%). Excluded."],
        ["Multinomial logistic classifiers", "Tested three feature kernels with C = 10, 100 and 1,000. Best exploratory leave-one-out result: 163/188 (86.70%). Excluded."],
    ], [139, 377], small=True))
    story.append(Spacer(1, 12))
    story.append(callout("The 90.43% exploratory score was used during development. It is not the final validation estimate and is not an official held-out score."))
    story.append(Spacer(1, 10))
    story.append(p("How the extra images were processed", "h2"))
    story.append(p("For the 20x experiment, images were resized to 256 pixels on the short side, center-cropped to 224 and ImageNet-normalized. Both the class-token feature and the mean patch-token feature were saved. One slide, SUPP-04-bb_04_wsi_0009, had no usable 20x tile. Thumbnail experiments cropped outer glass with a fixed RGB mask and square-padded the full view and quadrants. Cached features and checkpoint hashes were retained. [6]", "small"))
    story.append(PageBreak())

    story += page_title(5, "Where the model succeeds and fails")
    story.append(p("Organ-level recall on the paired 188-slide cohort", "h2"))
    story.append(p("Recall is the fraction of slides of a given organ that are correctly classified. Values below average the same slides over ten repeats. Counts are unique slides, not repeated predictions. The comparator is the original selection procedure. [4]", "small"))
    organ_rows = []
    for organ, values in sorted(DATA["per_organ"].items()):
        organ_rows.append([organ, values["slides"], f"{100 * values['old_recall']:.1f}%", f"{100 * values['new_recall']:.1f}%"])
    organ_table = table(["Organ group", "Slides", "Original recall", "New recall"], organ_rows, [216, 60, 120, 120])
    organ_table.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
    story.append(organ_table)
    story.append(Spacer(1, 9))
    story.append(p("The largest persistent weaknesses are Other or mixed and Bladder. Improvements are not uniform: stomach, liver and uterus recall decrease slightly. Perfect results for Bone and Esophagus involve only four and two slides respectively, so they offer limited evidence of generalization."))
    story.append(p("Supplier distribution matters", "h2"))
    rows = [[supplier, values["slides"], f"{100 * values['old_accuracy']:.1f}%", f"{100 * values['new_accuracy']:.1f}%"] for supplier, values in DATA["per_supplier"].items()]
    story.append(table(["Supplier", "Slides", "Original accuracy", "New accuracy"], rows, [156, 60, 150, 150], small=True))
    story.append(Spacer(1, 8))
    story.append(p("SUPP-02 supplies 128/188 comparison slides and 57/67 held-out slides. The validation folds mix suppliers; these results do not establish performance on a previously unseen supplier. The SUPP-03 estimate is particularly uncertain because the paired cohort contains only three labelled slides from that supplier. Supplier identity itself was not used as a feature.", "small"))
    story.append(PageBreak())

    story += page_title(6, "Submission and reproducibility")
    story.append(p("What was delivered", "h2"))
    story.append(p("The new CSV contains exactly 67 unique held-out slide IDs, in template order, with an allowed organ-group value in every row. The original submission is preserved. Only one prediction differs: [8]"))
    story.append(table(["Slide", "Original", "New candidate"], [["SUPP-02-bb_02_wsi_0032", "Uterus", "Colon and rectum"]], [226, 130, 160]))
    story.append(Spacer(1, 7))
    story.append(p("This is a changed prediction, not a verified correction. Its true label was not consulted.", "small"))
    story.append(p("Reproduce the default final workflow", "h2"))
    story.append(p("From the challenge directory, use a Python environment with NumPy. The validated numerical environment used Python 3.12 and NumPy 2.3.5. These commands recompute nested validation and the final submission from the supplied embedding files:", "body"))
    for line in ["python3 -m pip install -r scripts/requirements_c1.txt", "python3 scripts/test_c1.py", "python3 scripts/c1_evaluate_improved.py"]:
        story.append(p(escape(line), "code"))
    story.append(Spacer(1, 9))
    story.append(p("The default run requires the original comparison CSV at output/c1/submission_organ.csv. It is already present. If starting from the supplied packs and these scripts alone, first run python3 scripts/c1_embeddings.py. To write a separate reproduction directory, add --out-dir output/c1_reproduced to the final command.", "small"))
    story.append(p("Files to inspect", "h2"))
    story.append(table(["File or directory", "Purpose"], [
        ["output/c1_improved/submission_organ.csv", "New candidate submission"],
        ["output/c1/submission_organ.csv", "Preserved original submission"],
        ["output/c1_improved/validation_summary.json", "Metrics, selected parameters and limitations"],
        ["output/c1_improved/validation_predictions.csv", "Per-slide predictions for every validation repeat"],
        ["output/c1_improved/review_queue.csv", "Alternatives, margins, model agreement and neighbours"],
        ["output/c1_improved/artifact_hashes.json", "SHA-256 hashes of model code, inputs and outputs"],
        ["scripts/c1_features.py", "Feature normalization, pooling and kernel construction"],
        ["scripts/c1_evaluate_improved.py", "Nested validation, final fitting and CSV generation"],
    ], [280, 236], small=True))
    story.append(Spacer(1, 9))
    story.append(p("The final default does not load the experimental 20x or thumbnail features and needs neither PyTorch nor scikit-learn. Their extraction and screening scripts remain available, and the image-feature caches are retained in output/c1_20x_features and output/c1_overview_features. [5, 6]", "small"))
    story.append(PageBreak())

    story += page_title(7, "Checks, limitations and evidence")
    story.append(p("Verification performed", "h2"))
    story.append(p("Four automated tests passed: exact leave-one-out ridge predictions match explicit refits; changing validation targets cannot change a training-only fit; folds keep slide IDs separate and retain rare classes in training; and zero-valued feature blocks remain numerically valid. Additional checks verified finite cached features, exclusion of listed blank tiles, CSV completeness and unchanged original artifact hashes. [7, 8]"))
    story.append(p("Limits of the evidence", "h2"))
    story.append(p("<b>Internal validation only.</b> Feature families were chosen after exploring these same labelled data. Regularization selection is nested, but the overall development history is not an untouched external test. The paired bootstrap interval includes no gain, and the official 67-slide answer key was never used."))
    story.append(p("<b>Small and uneven sample.</b> There are only two Esophagus slides and four each for Bone and Bone marrow in the paired cohort. Most slides come from one supplier. Repeated splits reduce sensitivity to a single partition but do not create new independent patients."))
    story.append(p("<b>Unknown patient overlap.</b> Patient identifiers were not supplied. No exact duplicate thumbnail hashes or GigaPath vector pairs with cosine above 0.999 were found, but these checks cannot establish patient independence."))
    story.append(p("<b>Scope of inputs and experiments.</b> Filenames, supplier identifiers, age, sex and report text were not predictive features. The 20x experiment used a cached general-purpose DINOv2 model; its negative result does not show that higher-resolution pathology-specific encoders would fail. Larger checkpoints could not be downloaded in this environment."))
    story.append(p("Evidence index", "h2"))
    references = [
        ("[1] Task and cohorts", "pack_slides/README.md; pack_slides/slides_manifest.json; pack_slides/organ_groups.json."),
        ("[2] Features and model", "tilepack/embeddings/README.md; scripts/c1_features.py; scripts/c1_screen.py; scripts/c1_evaluate_improved.py."),
        ("[3] Initial benchmark", "output/c1/validation_summary.json; scripts/c1_embeddings.py."),
        ("[4] Final validation", "output/c1_improved/validation_summary.json; validation_predictions.csv; fold_model_selections.json in the same directory."),
        ("[5] Exploratory screens", "tmp/c1_improved/screen.json; screen_20x.json; screen_overview.json; svm_screen.json; logistic_screen.json. Corresponding scripts: c1_screen.py, c1_screen_svm.py and c1_screen_logistic.py."),
        ("[6] Additional image features", "tiles20x/README.md; output/c1_20x_features/summary.json and provenance.json; output/c1_overview_features/provenance.json; scripts/c1_extract_20x.py; scripts/c1_extract_overview.py."),
        ("[7] Numerical checks", "scripts/test_c1.py; four tests passed in the recorded execution."),
        ("[8] Submission audit", "output/c1_improved/submission_organ.csv; submission_changes.csv; artifact_hashes.json; experiment_report.json in the same directory."),
    ]
    for label, text in references:
        story.append(p(f"<b>{escape(label)}.</b> {escape(text)}", "small"))
    story.append(p("All evidence paths are relative to the challenge directory. Metrics were read from the saved artifacts; this report did not retrain the classifier or change predictions.", "small"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    document = BaseDocTemplate(str(OUT), pagesize=(612, 792), leftMargin=48, rightMargin=48,
                               topMargin=62, bottomMargin=54, title="Biobase Task C1: Organ Classification Methods Report",
                               author="", subject="Methods, validation, experiments and reproducibility for task C1")
    document.addPageTemplates(PageTemplate(id="report", frames=[Frame(48, 54, WIDTH, 676, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=footer))
    document.build(story)
    print(OUT)
    print("SHA256", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    build()
