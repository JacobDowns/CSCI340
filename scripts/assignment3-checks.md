# Assignment 3 instructor checks

`check_assignment3.py` runs across a roster of PostgreSQL schemas and produces a searchable HTML report, a CSV with one row per check, and detailed JSON. It follows the Assignment 3 handout and Activity 3 requirements. It does **not** assign grades or send student feedback.

The report groups evidence under the handout's four instructor-check categories (2/2/4/2 points). The number of passing checks is **not a score**: some checks overlap, some depend on a valid fixture, and some require instructor interpretation.

## Setup and connection

Use `uv` with Python 3.11 or newer and psycopg 3 (already listed in this repository's `requirements.txt`). From the repository root, create the environment if `.venv` does not already exist:

```bash
uv venv --python python3 .venv
```

If `.venv` already exists, reuse it and skip the creation command. Install the dependency into that environment:

```bash
uv pip install --python .venv/bin/python 'psycopg[binary]>=3.1,<4'
```

The commands below run `.venv/bin/python` directly, so activating the environment is unnecessary.

Connect with an instructor account that can inspect all student tables. Use libpq's `.pgpass`/`PGPASSFILE` or a configured service for authentication; the script does not read student passwords or put passwords into command arguments. In particular, the provisioning manifest selects schemas; it is **not** used to log in as students.

For this course, the existing private connection config and provisioning manifest can be used directly:

```bash
export PGUSER=YOUR_INSTRUCTOR_ROLE

# Read-only inspection of every provisioned student's schema.
.venv/bin/python scripts/check_assignment3.py \
  --config instructor-solutions/student-account-provisioning.toml \
  --schema-file instructor-solutions/student-accounts-2026-09-11/credential-manifest.csv
```

`--config` reads only `[database] host`, `port`, `name`, and `sslmode`. `PGUSER` supplies the instructor role. If authentication fails, check the password file, connection details, and instructor privileges. No interactive password prompt is implemented.

Alternatively, use `--service YOUR_LIBPQ_SERVICE` or omit both options and set `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGSSLMODE` as needed.

## Select schemas

Choose exactly one selection method:

- `--schema-file FILE.csv`: recommended for the whole class; finds missing schemas as well as existing ones. Accepts the existing provisioning manifest, or a CSV with `schema,student` columns (`student` is optional). Only these identity fields are retained; passwords and other roster fields are discarded.
- `--schema EXACT_NAME`: repeat this option to check several exact schemas. Quoted/mixed-case identifiers are supported.
- `--schema-prefix csci340_`: discovers existing schemas whose names start with this literal prefix. This cannot identify a student whose schema is entirely missing. The underscore is literal, not a SQL wildcard.

A roster CSV can be as simple as:

```csv
schema,student
csci340_example1,Example Student One
csci340_example2,Example Student Two
```

For a targeted recheck where `escape_team.contact_email` was instead named `email`, use an explicit override:

```bash
PGUSER=course_admin .venv/bin/python scripts/check_assignment3.py \
  --config instructor-solutions/student-account-provisioning.toml \
  --schema csci340_790775522 \
  --team-email-column email \
  --probe-writes
```

Run this in the system shell, not at the `psql` prompt (`\q` exits psql). The override requires exactly one explicit `--schema`, so it cannot accidentally affect a whole-roster run. It maps the email field for final-data matching and every email-related probe, including required values, blank text and duplicate teams. It does not rename the student's column. The original column-name mismatch remains a `FAIL` and the explicit mapping is recorded as `REVIEW`; these findings do not block the adapted probes. Raw snapshots/catalog definitions retain the actual column names. If both names exist, or the alternate is absent, the mapping is rejected and behavioral probes are skipped. Omit `--probe-writes` for a read-only mapped inspection.

## Table and column naming differences across the roster

Use an explicit per-schema TOML map with `--name-map`. The private file
`instructor-solutions/assignment3-name-map.toml` contains the three confirmed field-name
differences from the saved catalog: Erin's `email`, Koen's `special_request`, and
Samuel's `conatct_email`. It can be used with the full roster:

```bash
PGUSER=course_admin .venv/bin/python scripts/check_assignment3.py \
  --config instructor-solutions/student-account-provisioning.toml \
  --schema-file instructor-solutions/student-accounts-2026-09-11/credential-manifest.csv \
  --name-map instructor-solutions/assignment3-name-map.toml \
  --probe-writes
```

Authentication uses the same password environment/file setup as earlier runs. Omit
`--probe-writes` to inspect first. Every report now includes a catalog-only list of
the actual tables, views and columns in each selected schema, including schemas
where the standard tables are missing. Use that inventory and the student's work
to identify equivalents before adding a mapping. Similar spelling alone is not
sufficient evidence. The checker does not automatically choose fuzzy matches.

Example syntax (illustrative names, not a claim about an actual student):

```toml
[schemas.csci340_example.tables]
escape_room = "rooms"
escape_booking = "escape_bookings"

[schemas.csci340_example.columns.escape_room]
room_id = "id"
room_name = "name"

[schemas.csci340_example.columns.escape_booking]
booking_id = "id"
room_id = "room"
special_requests = "special_request"
```

Keys always use the expected table/field names; values are actual identifiers.
Mappings apply only inside the exact named schema, including mixed-case/quoted
identifiers. They cover record matching, primary/foreign-key inspection and all
behavioral SQL. Primary keys and foreign keys are still inspected for real
constraints; a rename cannot manufacture a missing key or missing rule. Required
fields must map one-to-one, so `room_id` cannot reuse the required `room_code` field.

The report displays applied mappings prominently, retains original names in raw
snapshots/catalogs/SQL traces, and keeps naming mismatches separate from behavior
results. Internal returned probe values and matching candidates use expected field
names. Unknown mapping keys, duplicate targets, missing targets and coexistence of
expected and alternate names are rejected; ambiguous mappings block behavioral
probes for that schema. Fix or remove stale mappings if a student repairs a name.
Mappings for unselected schemas are ignored with a console notice.

For grading, evaluate the naming requirement once rather than treating dependent
skips as separate failed rules. Award behavior credit from the adapted tests that
actually ran. Name mapping does not normalize data values, timestamp types, text
activity states or different key designs. A separate reviewed activity-value
override, described below, can adapt the boolean fixtures to equivalent text
states. These options do not change proposed grades or earlier reports.

### Reviewed text activity states

If a student's `is_active` uses meaningful text states instead of booleans, use
`--room-active-value active --room-inactive-value retired --room-inactive-value unavailable`
with **one explicit `--schema`**. Choose the actual values after reviewing that
student's definition; the script never guesses them or applies them to a roster.
Both an active value and at least one distinct inactive value are required.
Repeat the inactive option to test multiple permitted closed/retired states.

This changes the temporary room fixtures, the expected omitted-column default,
and accepted inactive-value probes. It does not change student tables or stored
assignment rows. The default probe still omits `is_active` and checks that the
database returns the specified active value; a missing or wrong default still
fails. NULL rejection and all other tests remain in place, including missing
references and reserved/cancelled booking-history protection. Keep `--name-map`
when column aliases also need mapping.

For example, after authenticating, run:

```bash
.venv/bin/python scripts/check_assignment3.py \
  --config instructor-solutions/student-account-provisioning.toml \
  --schema student_schema \
  --name-map instructor-solutions/assignment3-name-map.toml \
  --room-active-value active \
  --room-inactive-value retired \
  --room-inactive-value unavailable \
  --probe-writes
```

Reports record the chosen states in `activity_value_mapping`, alongside raw
column types and data. The text-type REVIEW and exact-name findings remain
visible as evidence; interpret accepted equivalents separately from actual rule
failures. A successful run does not establish that an ambiguous label such as
`occupied` means inactive/closed. Semantic review remains necessary. Behavioral
rollback and sequence-advance caveats are unchanged.

The default output is a new dated directory under `instructor-solutions/`, which is excluded from Git and the course website. `--output PATH` selects a different **new** directory. Reports contain student records: keep them private. The directory is created with mode 700 and files with mode 600. Existing output directories are never overwritten.

## Run behavioral checks

First inspect the read-only report or try one schema. To run the full suite across the roster:

```bash
.venv/bin/python scripts/check_assignment3.py \
  --config instructor-solutions/student-account-provisioning.toml \
  --schema-file instructor-solutions/student-accounts-2026-09-11/credential-manifest.csv \
  --probe-writes
```

This mode needs `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on the three tables and access to their generated-ID sequences. Schemas owned by the instructor can still contain tables owned by students; schema ownership alone does not grant table access. Use the instructor/admin connection you ordinarily use for checking those tables. The script does not change grants, table definitions, or constraints.

Each schema runs in a transaction that is **always rolled back**, even on success. Probes create their own rooms, teams, and booking; they do not update or delete the assignment rows. Each attempted mutation has its own savepoint, so an expected SQL error does not abort the remaining checks. Deferred constraints are forced before judging success. Defaults are tested by omitting columns, and all later fixture operations use the IDs actually returned by PostgreSQL.

**Generated-ID sequences may advance, even when the transaction rolls back.** Do not reset them afterward; gaps are normal. PostgreSQL documents this behavior in [Sequence Manipulation Functions](https://www.postgresql.org/docs/current/functions-sequence.html). The implementation uses psycopg's [transaction and savepoint support](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

Behavioral mode skips tables with row-level security, enabled user triggers, rules, or inheritance/partitioning, since those need individual review. Custom default/check functions can also have effects outside ordinary table transactions; use a disposable database copy for such designs. The assignment's ordinary types/defaults/constraints are the supported scope.

## What the report checks

Read-only mode captures the three permanent tables, column definitions, keys, defaults, foreign keys, and stored rows ordered by their IDs. It looks for:

- LIB-01 and LIB-02, both named The Library After Midnight;
- two Vipers teams with the required email, and The Clue Crew;
- one Vipers team with a completed $79.50 LIB-01 booking and a reserved $0.00 LIB-01 booking on a different date;
- a reserved Clue Crew booking in LIB-02, and an unbooked second Vipers team.

It permits unrelated practice rows and never assumes IDs start at 1 or are consecutive. It identifies matching candidate sets rather than guessing which booking was originally $89.50. Missing or ambiguous matches are `REVIEW`, since Question 10 or a documented reset can explain changes. Compare these results with the student's submitted generated IDs. Historical defaults and the original $89.50 value cannot be proven from final stored rows alone.

Behavioral mode additionally tests:

- database-generated IDs; active/reserved/NULL defaults; duplicate experience names; duplicate team names and emails; repeat bookings;
- explicit NULLs in every required column, optional requests, empty/space-only required text, duplicate room codes;
- accepted lower/upper bounds and rejected out-of-range capacity, party size, and prices; preservation of cents at $79.50 and support for $9999.99;
- whole-number storage, allowed difficulty/status values, invalid difficulty/status values, end times equal to or earlier than start times, and required/ordered times for cancelled bookings;
- absent room and team references, using a generated and then deleted fixture ID verified absent;
- blocked room and team deletion with reserved bookings and again with cancelled bookings.

Most invalid-value checks use updates of a previously accepted fixture to isolate one field. The same PostgreSQL column constraints apply to inserts. The suite also uses inserts for defaults, duplicates, generated IDs, and repeat visits. It does not require the optional capacity-vs-party, active-room, or overlap extensions.

The report includes SQLSTATE, constraint/column names when provided by PostgreSQL, and SQL plus bound parameters for individual probes. Rejection by an unrelated error (e.g., permission denial or missing columns) does not count as passing the intended rule. Some type/domain implementations and custom constraints require manual interpretation. Missing `NOT NULL` metadata is marked `REVIEW` because a domain or equivalent check may enforce it.

`PASS` means that particular check succeeded; `FAIL` means an observed mismatch; `REVIEW` means ambiguous evidence; `ERROR` indicates an execution/access problem; `SKIP` means not tested. Inspect all five statuses: a green result on one example does not prove every possible input is validly constrained.

The default snapshot limit is 1,000 rows per table. If exceeded, final-data matching is skipped with a review notice; increase `--row-limit` if appropriate. Statement timeout defaults to 5 seconds (`--timeout-ms`); lock timeout is 2 seconds. Each schema has a consistent snapshot. The script proceeds after individual schema errors. Exit code 2 indicates execution/configuration errors, while ordinary student findings return 0; inspect the report for FAIL/REVIEW/SKIP.

## Broader catalog audit for possible evaluation mismatches

`inspect_assignment3_schemas.py` complements the checker by inventorying **every**
ordinary/partitioned/foreign table, view and materialized view in each selected
schema, including unexpectedly named relations. It also finds relations owned by
the student's same-named database role in other non-system schemas. Ownership is
only a location clue: it does not establish which assignment a table belongs to,
and tables owned by other roles outside the assigned schema are not discovered.

It uses a read-only transaction per student and queries PostgreSQL catalogs only.
It does not read student rows, run views, evaluate defaults, call student functions,
advance sequences, or change anything in the database. It captures:

- Actual names, types (including domain constraints and enum values), nullability,
  identities, generated columns and defaults.
- Primary/foreign keys, unique/check constraints, referenced tables and columns,
  indexes, sequence configuration/ownership/permissions, table privileges and schema USAGE.
- Views, triggers, rules, row security policies and inheritance metadata that may
  require individual review before behavioral tests.
- Review notes for similar names, existing confirmed mappings, alternate locations,
  different key designs and representations such as text activity states.

Candidate names are suggestions, never automatically applied. The audit will not
suggest reusing a distinct required column (for example, `room_code` for `room_id`).
Similarity is heuristic and may miss synonyms or suggest unrelated tables; full
definitions are retained for inspection. Existing `--name-map` entries are shown
as instructor-confirmed choices, with stale/ambiguous mappings flagged. Cross-schema
locations cannot be handled by the checker's within-schema mappings. Representation
notes are not deductions: compare meaning, constraints, written work and behavioral
evidence before deciding whether an implementation satisfies the requirement.

Run using the existing uv-created `.venv`; there are no new dependencies. This
subshell prompts privately and discards its password variable when it exits:

```bash
(
  cd /home/bizon/classes/CSCI340 || exit
  read -rsp 'course_admin password: ' PGPASSWORD || exit
  printf '\n'
  export PGPASSWORD
  PGUSER=course_admin .venv/bin/python scripts/inspect_assignment3_schemas.py \
    --config instructor-solutions/student-account-provisioning.toml \
    --schema-file instructor-solutions/student-accounts-2026-09-11/credential-manifest.csv \
    --name-map instructor-solutions/assignment3-name-map.toml
)
```

Use `--schema csci340_790775522` instead of `--schema-file ...` for one student;
repeat `--schema` for several. The report is saved in a **new** private directory
`instructor-solutions/assignment3-schema-audit-YYYYMMDD-HHMMSS/`, containing
`schema-audit.json` (complete evidence for review), `report.html` (searchable viewer)
and `summary.txt` (review notes). Optional `--output PATH` must be a new directory.
Directory/file permissions are 700/600, and manifest passwords are not exported.

Default per-statement timeout is 10 seconds (`--timeout-ms`), with a two-second
lock timeout. An execution error marks that student's audit incomplete; other
students continue. Exit code 2 means an execution/configuration error. Missing
schemas and review notes return 0 and must be reviewed in the report. The audit
does not update grades, feedback, previous reports or the name-map file.

## Local integration tests

The tests require a **disposable** PostgreSQL database. They create/drop randomly named test schemas; never set this variable to the course database.

```bash
A3_TEST_DSN='host=/PATH/TO/PRIVATE/SOCKET port=55439 dbname=postgres' \
  .venv/bin/python -m unittest discover -s tests -p test_check_assignment3.py -v
```

Without `A3_TEST_DSN`, database integration tests are skipped. Tests cover a correct schema, incorrect defaults, missing constraints, cascading deletion, missing references, overstrict uniqueness, absent generated IDs, deferred constraints, missing schemas, Q10 changes, quoted schema names, report escaping, private output, and unchanged table data after all probes.

For the additional catalog audit tests, use the same command with
`-p test_inspect_assignment3_schemas.py`. These check alternate names, distinct
required fields, domains/enums, cross-schema ownership, insufficient permissions,
unexecuted student views/functions/triggers, unchanged data and sequence state,
manifest password exclusion and private report files.
