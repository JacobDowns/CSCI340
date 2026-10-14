"""Catalog audit tests. A3_TEST_DSN must point to a disposable local database."""
import os
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import inspect_assignment3_schemas as audit
from test_check_assignment3 import DDL


class ReportTests(unittest.TestCase):
    def test_private_escaped_report(self):
        r = {"student": "<script>bad</script>", "schema": "s", "relations": [],
             "findings": [], "errors": [], "complete": True}
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "report"
            audit.write_reports(out, [r])
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            for p in out.iterdir():
                self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            page = (out / "report.html").read_text()
            self.assertNotIn("<script>bad</script>", page)
            self.assertIn("&lt;script&gt;bad&lt;/script&gt;", page)
            with self.assertRaises(FileExistsError):
                audit.write_reports(out, [r])


@unittest.skipUnless(os.environ.get("A3_TEST_DSN"), "Set A3_TEST_DSN to an isolated test database")
class AuditDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.environ["A3_TEST_DSN"], autocommit=True, row_factory=dict_row)
        self.schema = 'a3_audit_' + uuid.uuid4().hex[:12] + '"x'
        self.outside = 'a3_elsewhere_' + uuid.uuid4().hex[:12]
        self.role_created = False
        self.conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.conn.execute(sql.SQL("SET search_path TO {}, pg_catalog").format(sql.Identifier(self.schema)))
        self.conn.execute(DDL)

    def tearDown(self):
        self.conn.execute("RESET ROLE")
        self.conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(self.outside)))
        self.conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
        if self.role_created:
            self.conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(self.schema)))
        self.conn.close()

    def inspect(self, **kwargs):
        r = audit.inspect_schema(self.conn, self.schema, **kwargs)
        self.assertTrue(r["complete"], r["errors"])
        return r

    def test_good_schema_no_mutations_or_sequence_advances(self):
        snapshot = lambda: {t: self.conn.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(
            sql.Identifier(self.schema, t))).fetchall() for t in audit.FIELDS}
        seq = lambda: self.conn.execute(sql.SQL("SELECT last_value,is_called FROM {}").format(
            sql.Identifier(self.schema, "escape_room_room_id_seq"))).fetchone()
        before, before_seq = snapshot(), seq()
        r = self.inspect()
        self.assertEqual(r["findings"], [])
        self.assertEqual(snapshot(), before)
        self.assertEqual(seq(), before_seq)
        self.assertEqual(len(r["sequences"]), 3)
        booking = next(t for t in r["relations"] if t["name"] == "escape_booking")
        fk = next(c for c in booking["constraints"] if c["columns"] == ["room_id"])
        self.assertEqual(fk["referenced_columns"], ["room_id"])
        self.assertEqual(fk["referenced_schema"], self.schema)

    def test_naming_candidates_and_confirmed_map(self):
        self.conn.execute('ALTER TABLE escape_team RENAME COLUMN contact_email TO "E-mail"')
        self.conn.execute('ALTER TABLE escape_booking RENAME COLUMN special_requests TO special_request')
        self.conn.execute('ALTER TABLE escape_room RENAME TO "Escape Rooms"')
        r = self.inspect()
        room = next(f for f in r["findings"] if f.get("table") == "escape_room")
        self.assertEqual(room["candidates"][0]["table"], "Escape Rooms")
        email = next(f for f in r["findings"] if f.get("field") == "contact_email")
        self.assertEqual(email["candidates"], ["E-mail"])
        r = self.inspect(name_map={"tables": {"escape_room": "Escape Rooms"}, "columns": {
            "escape_team": {"contact_email": "E-mail"}, "escape_booking": {"special_requests": "special_request"}}})
        self.assertEqual(len(r["findings"]), 3)
        self.assertTrue(all(f["kind"] == "mapped_name" for f in r["findings"]))

    def test_distinct_required_field_never_reused(self):
        self.conn.execute("ALTER TABLE escape_room DROP COLUMN room_id CASCADE")
        r = self.inspect()
        f = next(f for f in r["findings"] if f.get("field") == "room_id")
        self.assertEqual(f["candidates"], [])
        self.assertTrue(any(f["kind"] == "key_design" for f in r["findings"]))

    def test_domains_enums_views_and_triggers_are_catalog_only(self):
        self.conn.execute("CREATE DOMAIN nonblank AS text NOT NULL CHECK (btrim(VALUE)<>'')")
        self.conn.execute("CREATE TYPE room_state AS ENUM ('active','retired','unavailable')")
        self.conn.execute("ALTER TABLE escape_room ALTER COLUMN is_active DROP DEFAULT")
        self.conn.execute("ALTER TABLE escape_room ALTER COLUMN is_active TYPE room_state USING 'active'::room_state")
        self.conn.execute("ALTER TABLE escape_room ALTER COLUMN is_active SET DEFAULT 'active'")
        self.conn.execute("CREATE TABLE extra (email nonblank, state room_state DEFAULT 'active')")
        # Any attempt to execute this view/function during auditing fails the test.
        self.conn.execute("""CREATE FUNCTION must_not_run() RETURNS int LANGUAGE plpgsql AS
            $$ BEGIN RAISE EXCEPTION 'Audit executed student code'; END $$""")
        self.conn.execute("CREATE VIEW dangerous_view AS SELECT must_not_run() AS x")
        self.conn.execute("""CREATE FUNCTION no_insert() RETURNS trigger LANGUAGE plpgsql AS
            $$ BEGIN RAISE EXCEPTION 'Audit inserted'; END $$""")
        self.conn.execute("CREATE TRIGGER extra_guard BEFORE INSERT ON extra FOR EACH ROW EXECUTE FUNCTION no_insert()")
        r = self.inspect()
        self.assertTrue(any(f["kind"] == "representation" and f.get("field") == "is_active" for f in r["findings"]))
        extra = next(t for t in r["relations"] if t["name"] == "extra")
        domain = extra["columns"][0]["type_chain"]
        self.assertEqual([t["name"] for t in domain], ["nonblank", "text"])
        self.assertTrue(domain[0]["not_null"])
        self.assertIn("btrim", domain[0]["domain_constraints"][0]["definition"])
        self.assertEqual(extra["columns"][1]["type_chain"][0]["enum_values"], ["active", "retired", "unavailable"])
        self.assertEqual(extra["triggers"][0]["name"], "extra_guard")
        view = next(t for t in r["relations"] if t["name"] == "dangerous_view")
        self.assertIn("must_not_run", view["view_definition"])

    def test_other_schema_student_owned_and_missing_access(self):
        self.conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(self.schema)))
        self.role_created = True
        self.conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.outside)))
        self.conn.execute(sql.SQL("CREATE TABLE {} (team_id int,team_name text,email text)").format(
            sql.Identifier(self.outside, "teams")))
        self.conn.execute(sql.SQL("ALTER TABLE {} OWNER TO {}").format(
            sql.Identifier(self.outside, "teams"), sql.Identifier(self.schema)))
        self.conn.execute("DROP TABLE escape_team CASCADE")
        self.conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(self.schema)))
        r = self.inspect()
        self.assertFalse(r["schema_info"]["usage"])
        self.assertTrue(any(f["kind"] == "access" for f in r["findings"]))
        team = next(f for f in r["findings"] if f.get("table") == "escape_team")
        self.assertEqual(team["candidates"][0]["schema"], self.outside)
        self.assertEqual(team["candidates"][0]["table"], "teams")

    def test_missing_schema_has_complete_inventory_and_location_note(self):
        r = audit.inspect_schema(self.conn, "absent_" + uuid.uuid4().hex)
        self.assertTrue(r["complete"])
        self.assertIsNone(r["schema_info"])
        self.assertEqual(r["relations"], [])
        self.assertEqual(r["findings"][0]["kind"], "location")

    def test_cli_roster_keeps_password_out_of_reports(self):
        import csv
        real_connect = psycopg.connect
        def connect(**kwargs):
            return real_connect(os.environ["A3_TEST_DSN"], **kwargs)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (root / "roster.csv").open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Student", "Database Username", "Password"])
                writer.writerow(["Example Student", self.schema, "DO_NOT_EXPORT_PASSWORD"])
                writer.writerow(["Missing Student", "absent_" + uuid.uuid4().hex, "SECOND_SECRET"])
            with patch.object(audit.psycopg, "connect", side_effect=connect):
                code = audit.main(["--schema-file", str(root / "roster.csv"), "--output", str(root / "report")])
            self.assertEqual(code, 0)
            payload = json.loads((root / "report/schema-audit.json").read_text())
            self.assertEqual(len(payload["schemas"]), 2)
            self.assertEqual(payload["schemas"][0]["student"], "Example Student")
            for p in (root / "report").iterdir():
                self.assertNotIn("DO_NOT_EXPORT_PASSWORD", p.read_text())
                self.assertNotIn("SECOND_SECRET", p.read_text())


if __name__ == "__main__":
    unittest.main()
