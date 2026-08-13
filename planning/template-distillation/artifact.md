# UM syllabus template execution contract

## Reference

- Retained reference: `C:\Users\iostr\Documents\ChatGPT\CSCI340\resources\UM Syllabus Template.docx`
- SHA-256: `0F644C7DD84FC04C464ADFE4D7031E68A20B4FCCA9B0BF1A53ED6373205A5A64`
- Size: 120,856 bytes
- Section count: 1
- Page count: unresolved. The package has no cached page count and LibreOffice is unavailable in this environment.
- Structural evidence: `planning/template-distillation/template-style-evidence.json` and the packaged document audit scripts.
- Reference render: attempted at `planning/template-distillation/reference-render`; no pages were produced because `soffice` is unavailable.
- Visual asset inspected independently: `word/media/image1.png`, the full-width University of Montana maroon logo with white background.

## Page system

- One section, `NEW_PAGE`, portrait US Letter (8.5 x 11 inches).
- Margins: 1 inch on all sides; content width 6.5 inches.
- Header/footer distance: inherited from the retained section; no first-page or odd/even variants.
- Header: one empty paragraph; preserve.
- Footer: right-aligned template identifier `Doc ID: LEAD 08.15.2025 (v1)` with surrounding empty template paragraphs; preserve.
- No fields, content controls, footnote references, endnote references, or source tables.

## Typography and color

- Document defaults: Calibri 11 pt via the minor theme font; 8 pt after; auto line value 259 (approximately 1.08 lines).
- Theme fonts: Calibri Light major Latin and Calibri minor Latin.
- Heading 1: Arial Narrow 20 pt, italic, 12 pt before, 6 pt after, keep with next. Used only for the syllabus title.
- Heading 2: Calibri 16 pt, bold, UM maroon `#70002E`. Used for major syllabus sections.
- Heading 3: source-derived 14 pt hierarchy based on Heading 4; used for course-policy and week-level subsections.
- Heading 4: Calibri 12 pt, bold, UM maroon `#70002E`, 2 pt before, 0 pt after, keep with next.
- Subtitle: Calibri 11 pt, gray `#5A5A5A`.
- List Paragraph: Calibri 11 pt by default with a 0.5-inch left indent. Course-detail and instructor-detail source patterns carry direct 12 pt text.
- Instructor-note source pattern: direct 10 pt Calibri. All instructor notes are editable guidance and must be removed from the student-facing output.
- Body hyperlinks and institutional resource wording are preserve-only unless a course-specific edit is required.

## Lists and tables

- The source uses real Word numbering with several distinct definitions. Preserve and clone the nearest semantic source list paragraph rather than creating fake bullets.
- Course detail rows use source paragraph index 7 as their formatting pattern (`numId=3`, level 0).
- Instructor detail rows use source paragraph index 15 (`numId=2`, level 0).
- Course outcomes and unit objectives use source paragraph indices 24 and 28 (`numId=27`, level 1).
- Institutional inclusion principles and mental-health resources use their own retained numbering definitions and must remain unchanged.
- The source contains no tables. Course calendar and grading content should therefore use cloned heading, paragraph, and list patterns rather than introducing a competing table system.

## Components

- Opening logo: `word/media/image1.png`, displayed inline at approximately 6.32 x 1.58 inches. Preserve image, relationship, placement, and alt text.
- Opening title stack: logo, Heading 1 course title, Subtitle term/status.
- Course and instructor metadata: labeled List Paragraph patterns, not a table.
- Major sections: Heading 2.
- Policy and support subsections: Heading 3 and Heading 4.
- Footer identifier: preserve exactly.
- No running header, page-number field, decorative cover, callout, or source table pattern exists; do not add one.

## Content flow

1. UM logo and title stack.
2. Course Information: course details followed by instructor information.
3. Course Description, Outcomes, and Objectives.
4. Course Calendar.
5. Grading Information.
6. Course Expectations & Policies.
7. Information for Students: retained institutional language and resources.

## Slot map

Stable locators refer to `word/document.xml`, body paragraph order in the retained reference, source style, and unique source text.

- Paragraph 0 / Heading 2 / drawing relationship: preserve UM logo and alt text.
- Paragraph 1 / Normal / begins `[Instructor Note: If you wish`: remove note only.
- Paragraph 2 / Heading 1 / `[Course Name] Syllabus`: replace with official course-title syllabus label.
- Paragraph 3 / Subtitle / `[Term Offered]`: replace with supplied term or an explicit development-draft status.
- Paragraph 5 / Normal / catalog instructor note: remove.
- Paragraphs 7-13 / List Paragraph / Course Details labels: replace with labeled course values; preserve source list paragraph properties.
- Paragraph 14 / Normal / begins `Instructor Information`: retain label, remove embedded note, and use it as the instructor-metadata lead.
- Paragraphs 15-19 / List Paragraph: replace with instructor values; preserve list properties.
- Paragraphs 22-32: replace catalog guidance and placeholder outcomes/objectives with the official catalog description, course emphasis, measurable outcomes, and unit objectives. Clone source list patterns when additional outcomes are required.
- Paragraphs 33-35: retain Course Calendar Heading 2; replace note/blank content with 14 cloned week blocks using Heading 3 and Normal/List Paragraph source patterns.
- Paragraphs 36-40: retain Grading Information and default UM grading scale; replace guidance with weighted assignment categories, evaluation principles, and capstone milestones.
- Paragraphs 41-56: retain Course Expectations & Policies hierarchy. Replace instructor-note slots for attendance, GenAI, workload, communication, and health/safety. Course-specific collaboration, late-work, data ethics, and help subsections may be inserted using cloned Heading 3 and Normal patterns before the preserve-only Academic Misconduct section.
- Paragraphs 50-55 and 57-97, except paragraph 61: preserve institutional headings, wording, hyperlinks, numbering, and resource text. Remove the inclusion instructor note at paragraph 61 while retaining the provided inclusion statement.
- Footer part `word/footer1.xml`: preserve template identifier and formatting.

## Package preservation

Preserve-only parts and relationships:

- `_rels/.rels`
- `word/header1.xml`, `word/footer1.xml`
- `word/media/image1.png`
- `word/theme/theme1.xml`
- `word/styles.xml`
- `word/numbering.xml`
- `word/settings.xml`
- `word/fontTable.xml`, `word/webSettings.xml`
- `word/footnotes.xml`, `word/endnotes.xml`
- all `customXml/*` parts and their relationships
- source image, header, footer, hyperlink, theme, and numbering relationships in `word/_rels/document.xml.rels`, except additions strictly required by new content
- `[trash]/*` opaque parts when the writer preserves them; if the document library drops only these unreferenced recovery artifacts, record the deviation rather than treating them as functional content.

Expected editable parts: `word/document.xml`, document relationships only if content requires them, and document metadata identifying the generated syllabus.

## Fidelity gates

- Recompute the retained-reference SHA-256 immediately before authoring; abort on mismatch.
- Build from a working copy of the reference, never from a blank document.
- Preserve the UM logo, maroon hierarchy, title stack, metadata-list pattern, official policy/support hierarchy, hyperlinks, and footer identifier.
- Remove all text matching `[Instructor Note:` and all unresolved source placeholders.
- Use the official catalog title, credits, prerequisite, offering, and catalog description for CSCI 340.
- Preserve real numbering for all cloned lists.
- Run section, style, heading, image, field, content-control, table-geometry, and accessibility audits on the final document.
- Compare package inventories and hashes for preserve-only parts.
- Attempt final render; if `soffice` remains unavailable, disclose the lack of page-image inspection and do not claim visual QA.
