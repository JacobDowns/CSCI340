# Assignment 3 instructor checks

`check_assignment3.py` runs across a roster of PostgreSQL schemas and produces a searchable HTML report, a CSV with one row per check, and detailed JSON. It follows the Assignment 3 handout and Activity 3 requirements. It does **not** assign grades or send student feedback.

The report groups evidence under the handout's four instructor-check categories (2/2/4/2 points). The number of passing checks is **not a score**: some checks overlap, some depend on a valid fixture, and some require instructor interpretation.

## Setup and connection

Use Python 3.11 or newer and psycopg 3 (already listed in this repository's `requirements.txt`):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'psycopg[binary]>=3.1,<4'
```

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

## Local integration tests

The tests require a **disposable** PostgreSQL database. They create/drop randomly named test schemas; never set this variable to the course database.

```bash
A3_TEST_DSN='host=/PATH/TO/PRIVATE/SOCKET port=55439 dbname=postgres' \
  .venv/bin/python -m unittest discover -s tests -p test_check_assignment3.py -v
```

Without `A3_TEST_DSN`, database integration tests are skipped. Tests cover a correct schema, incorrect defaults, missing constraints, cascading deletion, missing references, overstrict uniqueness, absent generated IDs, deferred constraints, missing schemas, Q10 changes, quoted schema names, report escaping, private output, and unchanged table data after all probes.
