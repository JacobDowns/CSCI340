# Instructor decisions before publication

## Required administrative details

- Enter the finalized course logistics in `_variables.yml`; it is the shared source for the website syllabus and Word-syllabus builder.
- Department or college naming beyond the University of Montana identity supplied by the template
- Department-approved course-level outcomes, if they differ from the measurable draft outcomes
- Regular meeting days/time, room, and delivery format
- Instructor name, contact expectations, and student hours
- Learning-management system and discussion channel
- Grading scale and rounding policy
- Exact late-work, extension, revision, and attendance procedures
- Final-exam time after applying the registrar's meeting-time matrix
- Required institution policy language and links

## Resolved from the UM catalog and template

- Official title: Database Design
- Course number: CSCI 340
- Credits: 3
- Offering: fall
- Prerequisite: CSCI 232
- Official catalog description and the UM syllabus structure, logo, institutional statements, support resources, and footer identifier
- Autumn 2026 calendar: classes August 24-December 4; final examinations December 7-11
- Provisional midterm date: Friday, October 23, during class
- Provisional final date: Wednesday, December 9; exact time still depends on the regular meeting time
- Grade categories: participation 10%, assignments 50%, examinations 40% (20% midterm and 20% final)

## Instructional choices

- Individual or team capstone, and maximum team size
- Common course dataset versus student-selected datasets
- Hosted PostgreSQL/PostGIS versus local containers/installations
- Expected Python background and how much class time to allocate to Polars
- Whether every project must contain a spatial phase
- Required versus recommended textbook access
- Number and cadence of problem sets and labs
- Scope of broader database architectures within the abbreviated final integration unit
- AI-assistance boundaries for each assignment family

## Website publication details

- GitHub Pages is configured for `https://JacobDowns.github.io/CSCI340/` through `.github/workflows/publish.yml`.
- In the GitHub repository, set **Settings → Pages → Source** to **GitHub Actions** before the first deployment.
- Decide whether planning notes remain in the public repository.
- Install Quarto and render the full site.
- Execute notebooks in the intended student environment and commit frozen results if desired.
