# CSCI 340 course materials

This repository is the source for a Quarto course website and a reproducible Word syllabus for **Database Systems and Data Management**.

## Project layout

- `_quarto.yml` - course website configuration
- `syllabus.qmd` and `schedule.qmd` - student-facing course documents
- `lectures/` - narrative lecture notes, diagrams, and in-class activities
- `notebooks/` - executable labs and computational investigations
- `projects/` - semester capstone materials
- `planning/` - instructor-facing design rationale and decisions
- `syllabus/` - generated Word syllabus and its reproducible template-based build script

## Preview the website

Install [Quarto](https://quarto.org/docs/get-started/) and run:

```powershell
quarto preview
```

The computational notebooks display without execution by default. To run one, change its front-matter setting from `enabled: false` to `enabled: true` and install the packages listed in `requirements.txt`.

Static checks that do not require Quarto or third-party notebook packages are available with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate_site.ps1
python scripts/validate_notebooks.py
```

## Rebuild the Word syllabus

Use the Python environment containing `python-docx`:

```powershell
python syllabus/build_syllabus.py
```

Administrative placeholders are intentional. See `planning/instructor-decisions.md` before publication.
