# Student PostgreSQL account provisioning

This workflow turns a Canvas gradebook CSV export into one transactional PostgreSQL provisioning file and one private credential handout per student. It reads only `Student`, `ID`, and `SIS Login ID`; grade columns are ignored.

Generated passwords, the SQL file, the manifest, and the handouts are restricted data. Keep every generated output under `instructor-solutions/`, which this repository already excludes from version control and the course website.

## 1. Configure the connection

Copy `scripts/student-account-provisioning.example.toml` to a private location such as:

```text
instructor-solutions/student-account-provisioning.toml
```

Edit the database host and database name. Review the username prefix, login group, password expiration, personal-schema setting, and connection limit. Add a support email only if it should appear in every student's handout.

With `create_personal_schema = true`, each role receives `USAGE` and `CREATE` privileges on an identically named schema, and its search path starts there. The administrator who runs the provisioning file owns the schemas, so the workflow does not require that administrator to assume each student role. This lets the login exercise test both connection access and a simple create/insert/select/drop sequence without letting students write to one another's schemas.

## 2. Validate without creating secrets

Run the script without `--write` first:

```bash
python3 scripts/generate_student_accounts.py \
  --roster "/path/to/canvas-gradebook.csv" \
  --config instructor-solutions/student-account-provisioning.toml
```

Validation checks the required columns, skips the Canvas `Points Possible` row, rejects missing or duplicate identifiers, and confirms that every derived PostgreSQL username is valid. It reports counts only and does not print student identities.

## 3. Generate the private package

Choose a new, empty output directory for each run:

```bash
python3 scripts/generate_student_accounts.py \
  --roster "/path/to/canvas-gradebook.csv" \
  --config instructor-solutions/student-account-provisioning.toml \
  --output-dir instructor-solutions/student-accounts-2026-09-11 \
  --write
```

The output contains:

- `provision-accounts.sql`: one transaction that creates every login, grants database access, and optionally creates personal schemas;
- `credential-manifest.csv`: the private mapping among Canvas identity, database username, password, and handout filename;
- `credential-handouts/`: one text file per student for individual Canvas attachment;
- `generation-summary.txt`: a count and configuration check without individual credentials.

The script refuses to write into a nonempty directory. This prevents an accidental second run from silently replacing passwords while older handouts still exist.

## 4. Review and apply the SQL

Before applying anything, compare the manifest count with the Canvas roster and inspect the SQL header, database name, role prefix, expiration date, and schema behavior.

Connect as a PostgreSQL administrator that can create roles and schemas, then run:

```bash
psql "host=YOUR_HOST port=5432 dbname=YOUR_DATABASE user=YOUR_ADMIN sslmode=require" \
  --file instructor-solutions/student-accounts-2026-09-11/provision-accounts.sql
```

The SQL uses `ON_ERROR_STOP`, a preflight collision check, and one transaction. It creates a no-login course group and adds every student role to it so `pg_hba.conf` can match only course accounts. If any generated role already exists or any statement fails, PostgreSQL aborts the run instead of leaving a partially provisioned class.

To permit course accounts to connect over SSL from any IPv4 or IPv6 address, a server administrator can place these records before any applicable rejection record in `pg_hba.conf`:

```text
hostssl  YOUR_DATABASE  +YOUR_LOGIN_GROUP  0.0.0.0/0  scram-sha-256
hostssl  YOUR_DATABASE  +YOUR_LOGIN_GROUP  ::/0       scram-sha-256
```

Reload the PostgreSQL configuration after checking the parsed records in `pg_hba_file_rules`. Internet access may also require a matching firewall or cloud security-group rule for TCP port 5432.

## 5. Test and distribute

Test one account from the manifest in a private terminal before posting the Canvas assignment. Each handout includes the server fields, username, password, a password-prompting `psql` command, and a short connection check.

Upload only the matching text file to each student's private Canvas submission or comment. Never attach the manifest or SQL file to Canvas. After the distribution period, retain only the restricted copy you need for support and delete obsolete password-bearing exports according to your course or institutional retention practice.
