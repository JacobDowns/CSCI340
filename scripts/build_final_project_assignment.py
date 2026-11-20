"""Build the concise final project assignment and rubric as a Word document."""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "projects/final-project-assignment.docx"
RUBRIC = [
    (
        "Revised ER diagram",
        10,
        "Clear, complete model using correct course notation, keys, cardinalities, "
        "and participation. Addresses milestone feedback and agrees with the implemented database.",
    ),
    (
        "SQL table definitions",
        30,
        "DDL executes successfully and implements the revised design with suitable "
        "types, primary and foreign keys, relationship tables, and other appropriate constraints.",
    ),
    (
        "Populated database",
        20,
        "All tables are created and populated in the live group project schema. Sample "
        "data is meaningful, satisfies constraints, meets the row requirement, "
        "and supports the queries.",
    ),
    (
        "Queries and expected results",
        30,
        "At least four distinct, realistic questions are answered correctly. Queries "
        "run on the live group data and use appropriate SQL. Reported results are "
        "complete and match the actual output.",
    ),
    (
        "Clarity and verification",
        10,
        "Files and report are organized and readable. Group and database/schema "
        "are identified; query labels, parameters, and execution instructions make "
        "the work straightforward to verify.",
    ),
]
assert sum(row[1] for row in RUBRIC) == 100

doc = Document()
section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
section.top_margin = section.bottom_margin = Inches(0.65)
section.left_margin = section.right_margin = Inches(0.7)
section.footer_distance = Inches(0.28)

for name in ("Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "List Bullet"):
    style = doc.styles[name]
    style.font.name = "Arial"
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_after = Pt(5)

normal = doc.styles["Normal"]
normal.font.size = Pt(11)
normal.paragraph_format.line_spacing = 1.04
normal.paragraph_format.widow_control = True
doc.styles["Title"].font.size = Pt(23)
doc.styles["Title"].paragraph_format.space_after = Pt(5)
doc.styles["Subtitle"].font.size = Pt(11)
doc.styles["Subtitle"].paragraph_format.space_after = Pt(9)
for name in ("Heading 1", "Heading 2"):
    style = doc.styles[name]
    style.font.size = Pt(13)
    style.font.bold = True
    style.paragraph_format.space_before = Pt(9)
    style.paragraph_format.space_after = Pt(5)
    style.paragraph_format.keep_with_next = True
for style in doc.styles:
    for border in list(style.element.iter(qn("w:pBdr"))):
        border.getparent().remove(border)

doc.core_properties.title = "Final database project"
doc.core_properties.subject = "CSCI 340 final project requirements and 100 point rubric"
doc.core_properties.author = "CSCI 340"


def para(text, style=None):
    return doc.add_paragraph(text, style)


def heading(text):
    return para(text, "Heading 1")


def bullet(text):
    return para(text, "List Bullet")


para("Final database project", "Title")
para("CSCI 340  |  100 points  |  One submission per group", "Subtitle")
para(
    "Revise your ER design, implement and populate your PostgreSQL database, and "
    "demonstrate how it answers useful questions. Build on your existing project "
    "and milestone feedback; keep the scope manageable. Submit by the deadline posted in Canvas."
)

heading("Revised ER diagram")
para(
    "Submit a readable diagram reflecting your final design and relevant milestone 1 "
    "feedback. Use course notation, including underlined keys, relationship diamonds, "
    "arrows, and participation lines. The diagram and implemented tables should "
    "represent the same entities, relationships, and rules."
)

heading("Table definitions and sample data")
para(
    "Create all project tables in your assigned group project schema. Submit a "
    "schema.sql file containing the PostgreSQL table creation commands, with suitable "
    "types, primary keys, foreign keys, and other appropriate constraints. Order the "
    "commands so the script runs successfully in an empty workspace."
)
para(
    "Populate every table with at least three meaningful rows. For a fixed lookup "
    "table with fewer than three valid values, include all valid values. Include "
    "enough related records in the live schema to demonstrate your relationships and queries."
)

heading("Four realistic queries")
para(
    "Write at least four SELECT queries that support distinct, common uses of your "
    "database, such as finding available resources, listing a customer's bookings, "
    "or summarizing activity. Use joins, filtering, aggregation, or other techniques "
    "where they help answer the question. Simple table listings alone are not sufficient."
)
para("Label your queries Q1, Q2, and so on, and include the following for each in your report:")
bullet("The question or use case, with any specific parameter values or dates.")
bullet("The SQL query as selectable text, also saved in queries.sql with the same label.")
bullet("The complete expected result, including column headings and returned values.")
para(
    "Run each query against your live group project schema and verify the reported result. "
    "Choose examples that produce meaningful output small enough to include in full. "
    "Use fixed dates or parameter values for reproducibility, and ORDER BY when row order matters."
)

doc.add_page_break()
heading("What to submit")
para("Submit these three files together in Canvas, either individually or in one ZIP:")
bullet(
    "project.pdf: project title, group number and members, a brief purpose statement, "
    "the revised ER diagram, and the questions, queries, and expected results."
)
bullet("schema.sql: commands to create all tables and their constraints.")
bullet("queries.sql: your labeled queries, ready to execute.")
para(
    "Identify your database and group schema in the report. Use schema-qualified table "
    "names or SET search_path in queries.sql to select the correct schema. The instructor "
    "will run your queries directly against the live group schema and compare the output "
    "with your expected results. Keep its tables and data unchanged after submission "
    "until grading is complete."
)
para(
    "Include your group number and names at the top of each SQL file; brief comments "
    "are sufficient. Acknowledge sources and material assistance under course policies."
)

heading("Grading rubric")
table = doc.add_table(rows=1, cols=3)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
table.autofit = False
widths = [Inches(1.65), Inches(0.6), Inches(4.85)]
for col, width in zip(table.columns, widths):
    col.width = width
for cell, label in zip(table.rows[0].cells, ("Criterion", "Points", "Full credit")):
    cell.text = label
for criterion, score, description in RUBRIC:
    cells = table.add_row().cells
    cells[0].text = criterion
    cells[1].text = str(score)
    cells[2].text = description
cells = table.add_row().cells
cells[0].text = "Total"
cells[1].text = "100"
cells[2].text = ""

borders = OxmlElement("w:tblBorders")
for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
    border = OxmlElement(f"w:{edge}")
    for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
        border.set(qn(f"w:{key}"), value)
    borders.append(border)
table._tbl.tblPr.append(borders)
repeat = OxmlElement("w:tblHeader")
table.rows[0]._tr.get_or_add_trPr().append(repeat)

for row_index, row in enumerate(table.rows):
    prevent_split = OxmlElement("w:cantSplit")
    row._tr.get_or_add_trPr().append(prevent_split)
    for col_index, cell in enumerate(row.cells):
        cell.width = widths[col_index]
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        tcpr = cell._tc.get_or_add_tcPr()
        margins = OxmlElement("w:tcMar")
        for side in ("top", "left", "bottom", "right"):
            margin = OxmlElement(f"w:{side}")
            margin.set(qn("w:w"), "95")
            margin.set(qn("w:type"), "dxa")
            margins.append(margin)
        tcpr.append(margins)
        if row_index == 0:
            shade = OxmlElement("w:shd")
            shade.set(qn("w:fill"), "E7EDF3")
            tcpr.append(shade)
        for p in cell.paragraphs:
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.02
            if col_index == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.name = "Arial"
                run.font.size = Pt(10.5)
                run.font.color.rgb = RGBColor(0, 0, 0)
                run.bold = row_index in (0, len(table.rows) - 1)

p = para("Partial credit reflects the quality and completeness of the work in each category.")
p.paragraph_format.space_before = Pt(7)

footer = section.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
run = footer.add_run("CSCI 340  |  Final project  |  ")
run.font.name = "Arial"
run.font.size = Pt(9)
field = OxmlElement("w:fldSimple")
field.set(qn("w:instr"), "PAGE")
footer._p.append(field)

doc.save(OUTPUT)
print(OUTPUT)
