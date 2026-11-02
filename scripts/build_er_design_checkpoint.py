"""Build the Canvas handout from the course milestone page.

Run with a Python environment containing reportlab and pypdf.
The QMD page is the source of truth for requirements and rubric text.
"""

from html import escape
from pathlib import Path
import re
import shutil
from urllib.parse import urljoin

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "projects/er-design-checkpoint.qmd"
OUTPUT = ROOT / "output/pdf/er-design-checkpoint.pdf"
SITE_COPY = ROOT / "projects/er-design-checkpoint.pdf"
SITE_BASE = "https://JacobDowns.github.io/CSCI340/projects/"
FONT_DIRS = [
    Path("/usr/share/fonts/truetype/liberation2"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/"
    "native/libreoffice-headless/libreoffice/share/fonts/truetype",
]
FONT_DIR = next(p for p in FONT_DIRS if (p / "LiberationSans-Regular.ttf").is_file())
for name, filename in [
    ("Course", "LiberationSans-Regular.ttf"),
    ("Course-Bold", "LiberationSans-Bold.ttf"),
    ("Course-Italic", "LiberationSans-Italic.ttf"),
    ("Course-BoldItalic", "LiberationSans-BoldItalic.ttf"),
]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
pdfmetrics.registerFontFamily(
    "Course", normal="Course", bold="Course-Bold", italic="Course-Italic",
    boldItalic="Course-BoldItalic",
)

INK = colors.HexColor("#182B3A")
ACCENT = colors.HexColor("#205A70")
PALE = colors.HexColor("#EDF3F6")
RULE = colors.HexColor("#CCD7DD")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    "Text", fontName="Course", fontSize=10.5, leading=13.4,
    textColor=INK, spaceAfter=5,
))
styles.add(ParagraphStyle(
    "MainTitle", parent=styles["Text"], fontName="Course-Bold",
    fontSize=19, leading=22, spaceAfter=6,
))
styles.add(ParagraphStyle(
    "Deck", parent=styles["Text"], fontSize=10.5, leading=13,
    textColor=ACCENT, spaceAfter=8,
))
styles.add(ParagraphStyle(
    "Section", parent=styles["Text"], fontName="Course-Bold",
    fontSize=12.5, leading=15, spaceBefore=7, spaceAfter=5, keepWithNext=True,
))
styles.add(ParagraphStyle(
    "Subsection", parent=styles["Section"], fontSize=11, leading=13.5,
    spaceBefore=6,
))
styles.add(ParagraphStyle(
    "BulletText", parent=styles["Text"], leftIndent=11, firstLineIndent=-9,
    spaceAfter=3,
))
styles.add(ParagraphStyle(
    "Cell", parent=styles["Text"], fontSize=10, leading=12.6, spaceAfter=0,
))
styles.add(ParagraphStyle(
    "CellHead", parent=styles["Cell"], fontName="Course-Bold",
    textColor=colors.white,
))
styles.add(ParagraphStyle("Points", parent=styles["Cell"], alignment=TA_CENTER))


def inline(text):
    text = text.translate(str.maketrans({"–": "-", "—": "-", "‑": "-"}))
    text = escape(text)

    def link(match):
        label, target = match.groups()
        if "://" not in target:
            target = urljoin(SITE_BASE, target).replace(".qmd", ".html")
        return f'<link href="{target}" color="#205A70"><u>{label}</u></link>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`([^`]+)`", r"<font name='Course'>\1</font>", text)


def draw_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Course-Bold", 8)
    canvas.setFillColor(ACCENT)
    canvas.drawString(46, 769, "CSCI 340  /  GROUP PROJECT MILESTONE 1")
    canvas.setStrokeColor(RULE)
    canvas.line(46, 760, 566, 760)
    canvas.line(46, 36, 566, 36)
    canvas.setFont("Course", 8)
    canvas.setFillColor(INK)
    canvas.drawString(46, 23, "Database purpose and ER design  |  50 points")
    canvas.drawRightString(566, 23, f"Page {doc.page}")
    canvas.restoreState()


def make_table(raw_rows):
    columns = len(raw_rows[0])
    if columns == 3:
        widths = [121, 50, 337]
    elif raw_rows[0][0] == "Feature":
        widths = [128, 380]
    else:
        widths = [145, 363]
    rows = []
    for row_index, cells in enumerate(raw_rows):
        row = []
        for col_index, value in enumerate(cells):
            style = "CellHead" if row_index == 0 else "Cell"
            if columns == 3 and row_index and col_index == 1:
                style = "Points"
            row.append(Paragraph(inline(value), styles[style]))
        rows.append(row)
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
    ]
    if columns == 3:
        commands.append(("BACKGROUND", (0, -1), (-1, -1), PALE))
    table.setStyle(TableStyle(commands))
    return table


def build():
    source = SOURCE.read_text()
    # Fail before export if rubric points and the declared total diverge.
    rubric = source.split("## Rubric", 1)[1]
    criterion_points = [int(p) for p in re.findall(r"\| \*\*(\d+)\*\* \|", rubric)]
    assert criterion_points == [10, 10, 14, 10, 6, 50]
    assert sum(criterion_points[:-1]) == criterion_points[-1] == 50
    assert "100-point" not in source and "100 points" not in source
    body = source.split("---", 2)[2]
    lines = body.strip().splitlines()
    story = [
        Paragraph("Database purpose<br/>and ER design", styles["MainTitle"]),
        Paragraph("Finish your ER diagram and describe the database", styles["Deck"]),
    ]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith(":::") or "{download=" in line:
            i += 1
            continue
        if line.startswith("## Rubric"):
            story.append(PageBreak())
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            story.extend([make_table(rows), Spacer(1, 7)])
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            story.append(Paragraph(inline(line.lstrip("# ")), styles["Section" if level <= 2 else "Subsection"]))
            i += 1
            continue
        bullet = re.match(r"^(- |\d+\. )(.*)", line)
        if bullet:
            prefix = "- " if bullet.group(1) == "- " else bullet.group(1)
            story.append(Paragraph(inline(prefix + bullet.group(2)), styles["BulletText"]))
            i += 1
            continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", ":::", "- ")):
            paragraph.append(lines[i].strip())
            i += 1
        story.append(Paragraph(inline(" ".join(paragraph)), styles["Text"]))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=letter, leftMargin=46, rightMargin=46,
        topMargin=43, bottomMargin=45,
        title="Project milestone 1 - Database purpose and ER design",
        author="CSCI 340", subject="Assignment instructions and 50-point rubric",
    )
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    reader = PdfReader(OUTPUT)
    extracted = " ".join(" ".join(p.extract_text() for p in reader.pages).split())
    assert "50 points" in extracted and "Clarity and completeness" in extracted
    assert "100 points" not in extracted
    shutil.copyfile(OUTPUT, SITE_COPY)
    print(f"Built {SITE_COPY} ({len(reader.pages)} pages)")
    for number, page in enumerate(reader.pages, 1):
        content = page.extract_text()
        print(f"Page {number}: {len(content.split())} words")


if __name__ == "__main__":
    build()
