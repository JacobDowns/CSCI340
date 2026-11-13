"""Build Activity 7 from the retained Activity 4 Word layout.

Run with Python containing lxml. The source DOCX is never modified; all package
parts outside the worksheet body, activity headers, and metadata are preserved.
Instructor pacing target: A 8 min, B 12 min, C 18 min, D 4 min (42 total).
"""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
from shutil import copyfile
from zipfile import ZipFile

from lxml import etree as ET


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "activities/week-07-er-modeling-activity.docx"
OUTPUT = ROOT / "activities/week-12-normalization-activity.docx"
REFERENCE_SHA256 = "7296bf42f95e1e5ec23d5a782493da2a8a11a0f65b820da6b26e27ece8957683"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def element(tag, **attrs):
    result = ET.Element(f"{{{W}}}{tag}")
    for key, value in attrs.items():
        result.set(f"{{{W}}}{key}", str(value))
    return result


def xml_bytes(tree):
    return ET.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)


def main():
    if sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Reference worksheet changed; review its layout before rebuilding.")

    with ZipFile(REFERENCE) as archive:
        original = {info.filename: (info, archive.read(info.filename)) for info in archive.infolist()}
    tree = ET.fromstring(original["word/document.xml"][1])
    body = tree.find("w:body", NS)
    paragraphs = body.findall("w:p", NS)
    patterns = {
        "title": deepcopy(paragraphs[0]),
        "course": deepcopy(paragraphs[1]),
        "subtitle": deepcopy(paragraphs[2]),
        "normal": deepcopy(paragraphs[3]),
        "heading": deepcopy(paragraphs[7]),
        "question": deepcopy(paragraphs[9]),
        "blank": deepcopy(paragraphs[11]),
    }
    section = deepcopy(body.find("w:sectPr", NS))
    for child in list(body):
        body.remove(child)

    def add_text(parent, text, properties=None):
        run = element("r")
        if properties is not None:
            run.append(deepcopy(properties))
        node = element("t")
        node.set(XML_SPACE, "preserve")
        node.text = text
        run.append(node)
        parent.append(run)

    def paragraph(text, role="normal", new_page=False, keep=False):
        p = deepcopy(patterns[role])
        for child in list(p):
            if child.tag != f"{{{W}}}pPr":
                p.remove(child)
        if new_page or keep:
            props = p.find("w:pPr", NS)
            if props is None:
                props = element("pPr")
                p.insert(0, props)
            props.append(element("pageBreakBefore") if new_page else element("keepNext"))
        # Bold inline **text** using the source's body type, without inventing a style.
        for i, part in enumerate(re.split(r"\*\*(.*?)\*\*", text)):
            if not part:
                continue
            props = None
            if i % 2:
                props = element("rPr")
                props.append(element("b"))
            add_text(p, part, props)
        body.append(p)
        return p

    def question(number, title):
        p = deepcopy(patterns["question"])
        runs = p.findall("w:r", NS)
        props = [deepcopy(run.find("w:rPr", NS)) for run in runs]
        for run in runs:
            p.remove(run)
        add_text(p, f"{number}. ", props[0])
        add_text(p, title, props[1])
        body.append(p)

    def space(inches):
        p = deepcopy(patterns["blank"])
        spacing = p.find("w:pPr/w:spacing", NS)
        spacing.set(f"{{{W}}}line", str(round(inches * 1440)))
        body.append(p)

    def bullet(text):
        p = paragraph(text)
        props = p.find("w:pPr", NS)
        if props is None:
            props = element("pPr")
            p.insert(0, props)
        props.append(element("ind", left=200, hanging=200))
        add_text(p, "")
        run = element("r")
        t = element("t")
        t.set(XML_SPACE, "preserve")
        t.text = "•  "
        run.append(t)
        p.insert(1, run)

    def sample_table():
        table = element("tbl")
        props = element("tblPr")
        props.append(element("tblW", w=5904, type="dxa"))
        props.append(element("tblLayout", type="fixed"))
        borders = element("tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            borders.append(element(edge, val="single", sz=6, color="D9D9D9"))
        props.append(borders)
        margins = element("tblCellMar")
        for edge in ("top", "bottom"):
            margins.append(element(edge, w=65, type="dxa"))
        for edge in ("left", "right"):
            margins.append(element(edge, w=110, type="dxa"))
        props.append(margins)
        table.append(props)
        widths = [720, 1728, 1728, 1728]
        grid = element("tblGrid")
        for width in widths:
            grid.append(element("gridCol", w=width))
        table.append(grid)
        records = [
            ["Row", "X", "Y", "Z"],
            ["1", "1", "a", "red"],
            ["2", "1", "b", "blue"],
            ["3", "2", "a", "green"],
            ["4", "2", "b", "red"],
            ["5", "3", "a", "blue"],
            ["6", "3", "b", "green"],
        ]
        for row_index, values in enumerate(records):
            row = element("tr")
            row_props = element("trPr")
            row_props.append(element("cantSplit"))
            if row_index == 0:
                row_props.append(element("tblHeader"))
            row.append(row_props)
            for width, value in zip(widths, values):
                cell = element("tc")
                cell_props = element("tcPr")
                cell_props.append(element("tcW", w=width, type="dxa"))
                cell_props.append(element("vAlign", val="center"))
                if row_index == 0:
                    cell_props.append(element("shd", fill="EAF0F6", val="clear"))
                cell.append(cell_props)
                p = element("p")
                p_props = element("pPr")
                p_props.append(element("jc", val="center"))
                p_props.append(element("spacing", before=0, after=0))
                p.append(p_props)
                run_props = element("rPr") if row_index == 0 else None
                if run_props is not None:
                    run_props.append(element("b"))
                add_text(p, value, run_props)
                cell.append(p)
                row.append(cell)
            table.append(row)
        body.append(table)

    # Page 1: definitions in use, with sample checks rather than domain inference.
    paragraph("Activity 7 Normalization", "title")
    body.append(deepcopy(patterns["course"]))
    paragraph("Read dependencies and test the normal forms", "subtitle")
    paragraph("Name and collaborators")
    space(0.18)
    paragraph(
        "Work individually or in a group. Use the lecture definitions as a reference. "
        "Support your conclusions with dependencies, counterexamples, or scenario rules. "
        "Write relation schemas rather than SQL."
    )
    paragraph("Part A Read a dependency", "heading")
    question("A1", "Test the rows")
    paragraph(
        "For each dependency below, decide whether it holds in this instance. "
        "If it fails, give two row numbers that demonstrate the failure. "
        "The Row column is only a label, not an attribute."
    )
    sample_table()
    paragraph("X → Z       (X, Y) → Z       Z → Y       Y → X")
    space(0.76)
    question("A2", "Distinguish an instance from a rule")
    paragraph(
        "Does a dependency that holds here have to hold in all valid future data? "
        "Explain what additional information would justify using it to normalize a schema."
    )
    space(0.56)

    # Page 2: the full definition, including its prime-attribute condition.
    paragraph("Part B Apply the definitions", "heading", new_page=True)
    paragraph(
        "All three schemas are in 1NF. The listed keys are the only candidate keys. "
        "Each key determines every attribute; use the listed dependencies and their implications."
    )
    paragraph("For **B1–B3**, record the following:")
    bullet("The prime attributes and the non-prime attributes.")
    bullet("Whether the schema is in 2NF. If not, identify a partial dependency.")
    bullet(
        "Whether it is in 3NF. For each listed non-trivial dependency, say whether "
        "the left side is a superkey, the right side is prime, or neither condition holds."
    )
    question("B1", "R with attributes X Y Z")
    paragraph("Candidate key: **(X, Y)**. Dependency: **X → Z**.")
    space(1.05)
    question("B2", "S with attributes X Y Z")
    paragraph("Candidate key: **X**. Dependencies: **X → Y** and **Y → Z**.")
    space(1.05)
    question("B3", "T with attributes X Y Z")
    paragraph(
        "Candidate keys: **(X, Y)** and **(X, Z)**. "
        "Dependencies: **(X, Y) → Z** and **Z → Y**."
    )
    space(1.25)

    # Page 3: derive the dependencies and remove partial dependencies.
    paragraph("Part C Revise a workshop database", "heading", new_page=True)
    paragraph(
        "A community center stores registrations for scheduled workshops in "
        "**Enrollment** with these attributes:"
    )
    paragraph(
        "student_id, workshop_id, student_name, workshop_title, "
        "room_id, room_name, enrolled_on"
    )
    bullet(
        "A student can enroll in several workshops; a workshop can have several students. "
        "There is one row per student–workshop pair."
    )
    bullet("Each student ID identifies one student name.")
    bullet(
        "Each workshop ID identifies one scheduled workshop and determines its "
        "title, assigned room ID, and room name."
    )
    bullet("Each room ID identifies one room name. Several workshops can use the same room.")
    bullet(
        "enrolled_on records when that student enrolled in that workshop. "
        "All values are atomic; names, titles, and dates are not unique. "
        "There are no additional uniqueness rules."
    )
    question("C1", "Translate the rules")
    paragraph(
        "Write the functional dependencies specified by the scenario. "
        "Identify a candidate key and the prime and non-prime attributes."
    )
    space(0.95)
    question("C2", "Identify the anomalies")
    paragraph(
        "Describe one update, one insertion, and one deletion anomaly in Enrollment. "
        "Identify the specific fact that could be inconsistent, unrecordable, or lost."
    )
    space(0.78)
    question("C3", "Make a first split")
    paragraph(
        "Split the original table into three tables: **Student**, **Workshop**, "
        "and **Enrollment**. Determine where each original attribute belongs "
        "and identify a primary key for each table. Then explain why each table "
        "is in **2NF**, using the dependencies from C1."
    )
    space(1.0)

    # Page 4: make the 3NF check explicit, then check atomic values.
    paragraph("Part C Finish the workshop design", "heading", new_page=True)
    question("C4", "Check a table that meets 2NF")
    paragraph("Consider this proposed table, with **workshop_id as its only candidate key**:")
    paragraph("Workshop(workshop_id, workshop_title, room_id, room_name)")
    paragraph(
        "Using the Part C rules, show the transitive dependency that causes trouble. "
        "For the offending dependency, apply both conditions in the 3NF definition. "
        "Explain why meeting 2NF did not prevent this problem."
    )
    space(0.78)
    question("C5", "Finish the split")
    paragraph(
        "Write a complete 3NF design for all the original Enrollment attributes. "
        "Mark primary keys and foreign keys. Identify the columns you would match "
        "to reconstruct an enrollment record with its student, workshop, and room descriptions."
    )
    space(1.02)
    paragraph("Part D Check atomic values", "heading")
    question("D1", "Repair a list of IDs")
    paragraph(
        "A separate design stores Workshop(workshop_id, workshop_title, topic_ids). "
        "Each topic_ids cell stores a comma-separated list of topic IDs. "
        "For example, the text '4,9' represents a workshop associated with topics 4 and 9. "
        "Each topic ID refers to Topic(topic_id, topic_name). "
        "Does this meet 1NF for the intended topic_id values? Propose schemas and keys "
        "that allow multiple topics and workshops with no topics, without parsing a list."
    )
    space(0.7)
    body.append(section)

    edits = {"word/document.xml": xml_bytes(tree)}
    for name, (_, contents) in original.items():
        if name.startswith("word/header") and name.endswith(".xml"):
            updated = contents.replace(b"Week 7 ER activity", b"Week 12 normalization activity")
            if updated != contents:
                edits[name] = updated

    core = ET.fromstring(original["docProps/core.xml"][1])
    core_ns = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    }
    for tag, value in (
        ("dc:title", "Activity 7 Normalization"),
        ("dc:subject", "Database Design normalization activity"),
        ("dc:description", "Practice functional dependencies, keys, 1NF, 2NF, and 3NF."),
    ):
        node = core.find(tag, core_ns)
        if node is not None:
            node.text = value
    edits["docProps/core.xml"] = xml_bytes(core)

    # Update the retained app page-count cache without rewriting other properties.
    app = ET.fromstring(original["docProps/app.xml"][1])
    pages = app.find("{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Pages")
    if pages is not None:
        pages.text = "4"
    edits["docProps/app.xml"] = xml_bytes(app)

    # Start from a copy, and replace only the declared editable parts.
    copyfile(REFERENCE, OUTPUT)
    with ZipFile(OUTPUT, "w") as archive:
        for name, (info, contents) in original.items():
            archive.writestr(info, edits.get(name, contents))

    with ZipFile(OUTPUT) as archive:
        for name, (_, contents) in original.items():
            if name not in edits:
                assert archive.read(name) == contents, f"Unexpected package change: {name}"
    assert sha256(REFERENCE.read_bytes()).hexdigest() == REFERENCE_SHA256
    print(OUTPUT)


if __name__ == "__main__":
    main()
