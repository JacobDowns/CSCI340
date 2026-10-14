"""Behavioral integration tests against an explicitly supplied disposable database.

PYTHONPATH=scripts A3_TEST_DSN='host=/tmp/... dbname=postgres' \
  python -m unittest discover -s tests -p test_check_assignment3.py
Never point A3_TEST_DSN at the course database. Tests create/drop random schemas.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

SPEC = importlib.util.spec_from_file_location("check_assignment3", Path(__file__).resolve().parents[1] / "scripts/check_assignment3.py")
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

DDL = """
CREATE TABLE escape_room (
 room_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 room_code text NOT NULL UNIQUE CHECK (btrim(room_code)<>''),
 room_name text NOT NULL CHECK (btrim(room_name)<>''),
 capacity integer NOT NULL CHECK (capacity BETWEEN 2 AND 8),
 difficulty text NOT NULL CHECK (difficulty IN ('introductory','standard','challenging')),
 is_active boolean NOT NULL DEFAULT true);
CREATE TABLE escape_team (
 team_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 team_name text NOT NULL CHECK (btrim(team_name)<>''),
 contact_email text NOT NULL CHECK (btrim(contact_email)<>''));
CREATE TABLE escape_booking (
 booking_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 room_id bigint NOT NULL REFERENCES escape_room,
 team_id bigint NOT NULL REFERENCES escape_team,
 starts_at timestamp NOT NULL, ends_at timestamp NOT NULL CHECK (ends_at>starts_at),
 party_size integer NOT NULL CHECK (party_size BETWEEN 1 AND 8),
 total_price numeric(6,2) NOT NULL CHECK (total_price>=0),
 status text NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved','completed','cancelled')),
 special_requests text);
INSERT INTO escape_room(room_code,room_name,capacity,difficulty) VALUES
 ('LIB-01','The Library After Midnight',4,'standard'),('LIB-02','The Library After Midnight',5,'challenging');
INSERT INTO escape_team(team_name,contact_email) VALUES
 ('The Vipers','vipers@example.com'),('The Clue Crew','clues@example.com'),('The Vipers','vipers@example.com');
INSERT INTO escape_booking(room_id,team_id,starts_at,ends_at,party_size,total_price,status) VALUES
 (1,1,'2026-10-01 10:00','2026-10-01 11:00',3,79.50,'completed'),
 (1,1,'2026-10-02 10:00','2026-10-02 11:00',3,0,'reserved'),
 (2,2,'2026-10-01 10:00','2026-10-01 11:00',3,45,'reserved');
"""


class FileTests(unittest.TestCase):
    def test_manifest_drops_password_and_reports_escape_html(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "roster.csv"
            manifest.write_text('Student,Database Username,Password\n"<Ada>",csci_ada,SECRET\n')
            self.assertEqual(M.read_schema_file(manifest), [("csci_ada", "<Ada>")])
            M.write_reports(root / "report", [{"schema": "csci_ada", "student": "<Ada>", "checks": []}], "read-only")
            report = (root / "report/report.html").read_text()
            self.assertIn("&lt;Ada&gt;", report)
            self.assertNotIn("SECRET", report)
            self.assertEqual((root / "report/results.json").stat().st_mode & 0o777, 0o600)

    def test_duplicate_schemas_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "roster.csv"
            p.write_text("schema\na\na\n")
            with self.assertRaises(ValueError):
                M.read_schema_file(p)

    def test_email_override_requires_one_explicit_schema(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(M.psycopg, "connect") as connect:
            for selector in (["--schema-prefix", "csci340_"], ["--schema", "one", "--schema", "two"]):
                with self.assertRaises(SystemExit) as raised:
                    M.main([*selector, "--team-email-column", "email", "--output", str(Path(temp)/"report")])
                self.assertEqual(raised.exception.code, 2)
            connect.assert_not_called()

    def test_name_map_validation(self):
        invalid = [
            {"unknown": {}}, {"tables": {"wrong_table": "rooms"}},
            {"tables": {"escape_room": "escape_team"}},
            {"columns": {"escape_room": {"room_id": "room_code"}}},
            {"columns": {"escape_room": {"room_nam": "name"}}},
            {"columns": {"escape_team": {"contact_email": ""}}},
            {"tables": {"escape_room": 123}},
            {"tables": {"escape_room": "bad\x00name"}},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                M.validate_name_map(value)
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/"map.toml"
            p.write_text('[schemas.student.columns.escape_team]\ncontact_email = "email"\n')
            self.assertEqual(M.read_name_map(p)["student"]["columns"], {"escape_team":{"contact_email":"email"}})
            p.write_text('[schema.student]\n')
            with self.assertRaises(ValueError):M.read_name_map(p)


@unittest.skipUnless(os.environ.get("A3_TEST_DSN"), "Set A3_TEST_DSN to an isolated test database")
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.environ["A3_TEST_DSN"], autocommit=True, row_factory=dict_row)
        # Embedded quote proves identifiers are quoted rather than interpolated.
        self.schema = 'a3_test_' + uuid.uuid4().hex[:10] + '"x'
        self.conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.conn.execute(sql.SQL("SET search_path TO {}, pg_catalog").format(sql.Identifier(self.schema)))
        self.conn.execute(DDL)

    def tearDown(self):
        self.conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
        self.conn.close()

    def checks(self, **kwargs):
        result = M.check_schema(self.conn, self.schema, **kwargs)
        return {c["check"]: c for c in result["checks"]}

    def snapshot(self):
        return {t: self.conn.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(sql.Identifier(self.schema,t))).fetchall() for t in M.FIELDS}

    def test_good_schema_passes_and_rows_rollback(self):
        before = self.snapshot()
        c = self.checks(probes=True)
        self.assertGreater(len(c), 95)
        self.assertEqual({k: v for k, v in c.items() if v["status"] != "PASS"}, {})
        self.assertEqual(before, self.snapshot())

    def test_alternate_email_runs_checks_preserves_names_and_rolls_back(self):
        # Include a quote to exercise safe identifier handling in INSERT/UPDATE.
        alternate = 'Contact "Email'
        self.conn.execute(sql.SQL("ALTER TABLE escape_team RENAME COLUMN contact_email TO {}").format(sql.Identifier(alternate)))
        before = self.snapshot()
        result = M.check_schema(self.conn, self.schema, probes=True, team_email_column=alternate)
        checks = {c["check"]: c for c in result["checks"]}
        self.assertEqual({k:v["status"] for k,v in checks.items() if v["status"] != "PASS"}, {
            "escape_team.columns":"FAIL", "escape_team.contact_email.name_mapping":"REVIEW"})
        self.assertEqual(result["column_overrides"], {"escape_team.contact_email": alternate})
        self.assertIn(alternate, result["rows"]["escape_team"][0])
        self.assertNotIn("contact_email", result["rows"]["escape_team"][0])
        self.assertEqual(checks["escape_team.contact_email.null"]["detail"]["column"], alternate)
        self.assertEqual(before, self.snapshot())
        # Without the explicit override the default checker must still block probes.
        self.assertEqual(self.checks(probes=True)["behavior.preflight"]["status"], "SKIP")

    def test_alternate_email_does_not_hide_broken_constraints(self):
        self.conn.execute("ALTER TABLE escape_team RENAME COLUMN contact_email TO email")
        self.conn.execute("ALTER TABLE escape_team DROP CONSTRAINT escape_team_contact_email_check")
        self.conn.execute("ALTER TABLE escape_team ALTER COLUMN email DROP NOT NULL")
        checks = self.checks(probes=True, team_email_column="email")
        for case in ("null", "empty", "spaces"):
            self.assertEqual(checks["escape_team.contact_email."+case]["status"], "FAIL")
        self.assertEqual(checks["booking.defaults"]["status"], "PASS")

    def test_alternate_email_read_only_matching_and_invalid_mapping(self):
        # Both missing alternate and ambiguous alternate must fail closed.
        for extra in (False, True):
            if extra:self.conn.execute("ALTER TABLE escape_team ADD COLUMN email text")
            checks = self.checks(probes=True, team_email_column="email")
            self.assertEqual(checks["escape_team.contact_email.name_mapping"]["status"], "ERROR")
            self.assertEqual(checks["behavior.preflight"]["status"], "SKIP")
            self.assertNotIn("booking.valid_seed", checks)
        self.conn.execute("ALTER TABLE escape_team DROP COLUMN email")
        self.conn.execute("ALTER TABLE escape_team RENAME COLUMN contact_email TO email")
        before = self.conn.execute("SELECT last_value FROM escape_team_team_id_seq").fetchone()
        checks = self.checks(team_email_column="email")
        self.assertEqual(checks["final.teams"]["status"], "PASS")
        self.assertEqual(checks["final.booking_pattern"]["status"], "PASS")
        self.assertEqual(before, self.conn.execute("SELECT last_value FROM escape_team_team_id_seq").fetchone())

    def test_all_table_and_column_names_mapped_with_actual_foreign_keys(self):
        mapping = {"tables": {t:'Actual "'+t for t in M.FIELDS},
                   "columns": {t:{f:'Actual "'+t+' '+f for f in fields} for t,fields in M.FIELDS.items()}}
        for t,fields in mapping["columns"].items():
            for field,actual in fields.items():
                self.conn.execute(sql.SQL("ALTER TABLE {} RENAME COLUMN {} TO {}").format(
                    sql.Identifier(t), sql.Identifier(field), sql.Identifier(actual)))
            self.conn.execute(sql.SQL("ALTER TABLE {} RENAME TO {}").format(
                sql.Identifier(t), sql.Identifier(mapping["tables"][t])))
        def snapshot():
            return {t:self.conn.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(
                sql.Identifier(self.schema, actual))).fetchall() for t,actual in mapping["tables"].items()}
        before = snapshot()
        result = M.check_schema(self.conn, self.schema, probes=True, name_map=mapping)
        checks = {c["check"]:c for c in result["checks"]}
        self.assertGreater(len(checks), 109)
        for name,check in checks.items():
            if not name.endswith((".columns", ".name_mapping")):
                self.assertEqual(check["status"], "PASS", check)
        self.assertEqual(checks["room_id.foreign_key"]["status"], "PASS")
        self.assertEqual(checks["booking.cancelled.starts_at.None"]["status"], "PASS")
        self.assertEqual(checks["final.booking_pattern"]["status"], "PASS")
        self.assertEqual(result["rows"], before)
        self.assertEqual(before, snapshot())
        self.assertEqual({r["name"] for r in result["inventory"]}, set(mapping["tables"].values()))
        self.assertEqual(checks["escape_team.contact_email.null"]["detail"]["column"],
                         mapping["columns"]["escape_team"]["contact_email"])
        self.assertIn('Actual "escape_booking starts_at',
                      checks["booking.cancelled.starts_at.None"]["detail"]["column"])
        # Mapping a foreign-key field must still reveal an actual missing FK.
        self.conn.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT escape_booking_room_id_fkey").format(
            sql.Identifier(mapping["tables"]["escape_booking"])))
        checks = self.checks(probes=True, name_map=mapping)
        self.assertEqual(checks["booking.missing_room_id"]["status"], "FAIL")
        self.assertEqual(checks["escape_room.delete_with_cancelled_booking"]["status"], "FAIL")

    def test_stale_table_mapping_blocks_probes_and_inventory_still_shows_names(self):
        self.conn.execute("CREATE TABLE rooms (example text)")
        result = M.check_schema(self.conn, self.schema, probes=True,
                                name_map={"tables":{"escape_room":"rooms"}})
        checks = {c["check"]:c for c in result["checks"]}
        self.assertEqual(checks["escape_room.name_mapping"]["status"], "ERROR")
        self.assertEqual(checks["behavior.preflight"]["status"], "SKIP")
        self.assertNotIn("booking.valid_seed", checks)
        self.assertIn("rooms", {r["name"] for r in result["inventory"]})

    def test_roster_mapping_is_scoped_to_one_student(self):
        other = self.schema + '_other'
        self.conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(other)))
        try:
            self.conn.execute(sql.SQL("SET search_path TO {}, pg_catalog").format(sql.Identifier(other)))
            self.conn.execute(DDL)
            self.conn.execute(sql.SQL("ALTER TABLE {}.escape_team RENAME COLUMN contact_email TO email").format(sql.Identifier(self.schema)))
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                names = root/'names.toml'
                names.write_text('[schemas.'+json.dumps(self.schema)+'.columns.escape_team]\ncontact_email="email"\n')
                params = psycopg.conninfo.conninfo_to_dict(os.environ["A3_TEST_DSN"])
                env = {"PG"+k.upper():v for k,v in params.items() if k in ("host","port","user","password")}
                env["PGDATABASE"] = params.get("dbname","postgres")
                with patch.dict(os.environ,env):
                    code = M.main(["--schema",self.schema,"--schema",other,"--name-map",str(names),
                                   "--probe-writes","--output",str(root/'report')])
                self.assertEqual(code,0)
                results = json.loads((root/'report/results.json').read_text())["schemas"]
                self.assertEqual(results[0]["column_overrides"], {"escape_team.contact_email":"email"})
                self.assertEqual(results[1]["column_overrides"], {})
                self.assertTrue(all(c['status']=='PASS' for c in results[1]['checks']))
                self.assertNotIn('SKIP',{c['status'] for c in results[0]['checks']})
        finally:
            self.conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(other)))

    def test_read_only_does_not_advance_sequences(self):
        before = self.conn.execute("SELECT last_value FROM escape_room_room_id_seq").fetchone()
        c = self.checks()
        self.assertEqual(c["behavior"]["status"], "SKIP")
        self.assertEqual(before, self.conn.execute("SELECT last_value FROM escape_room_room_id_seq").fetchone())

    def test_broken_constraints_cascade_and_default(self):
        self.conn.execute("ALTER TABLE escape_booking DROP CONSTRAINT escape_booking_party_size_check")
        self.conn.execute("ALTER TABLE escape_booking DROP CONSTRAINT escape_booking_room_id_fkey")
        self.conn.execute("ALTER TABLE escape_booking ADD FOREIGN KEY(room_id) REFERENCES escape_room ON DELETE CASCADE")
        self.conn.execute("ALTER TABLE escape_room ALTER COLUMN is_active SET DEFAULT false")
        before = self.snapshot()
        c = self.checks(probes=True)
        for key in ("escape_booking.party_size.0", "escape_booking.party_size.9", "escape_room.delete_with_reserved_booking", "escape_room.delete_with_cancelled_booking", "room.default_active"):
            self.assertEqual(c[key]["status"], "FAIL", c[key])
        self.assertEqual(before, self.snapshot())

    def test_missing_fk_does_not_false_pass(self):
        self.conn.execute("ALTER TABLE escape_booking DROP CONSTRAINT escape_booking_team_id_fkey")
        c = self.checks(probes=True)
        self.assertEqual(c["booking.missing_team_id"]["status"], "FAIL")
        self.assertEqual(c["escape_team.delete_with_cancelled_booking"]["status"], "FAIL")

    def test_overstrict_uniqueness(self):
        self.conn.execute("DELETE FROM escape_booking WHERE booking_id=2")
        self.conn.execute("ALTER TABLE escape_booking ADD UNIQUE(room_id,team_id)")
        c = self.checks(probes=True)
        self.assertEqual(c["booking.repeat_visit"]["status"], "FAIL")
        self.assertEqual(c["booking.defaults"]["status"], "FAIL")

    def test_failed_fixture_blocks_dependents_without_aborting(self):
        self.conn.execute("ALTER TABLE escape_booking ALTER COLUMN booking_id DROP IDENTITY")
        c = self.checks(probes=True)
        self.assertEqual(c["booking.valid_seed"]["status"], "FAIL")
        self.assertEqual(c["booking.dependent_probes"]["status"], "SKIP")
        self.assertEqual(c["escape_room.capacity.9"]["status"], "PASS")

    def test_missing_schema_and_truncation(self):
        result = M.check_schema(self.conn, "a3_missing_schema")
        self.assertEqual(sum(c["status"] == "FAIL" for c in result["checks"]), 3)
        c = self.checks(row_limit=1)
        self.assertEqual(c["final.data"]["status"], "SKIP")

    def test_q10_change_requests_review_and_extra_rows_are_allowed(self):
        self.conn.execute("INSERT INTO escape_team(team_name,contact_email) VALUES('Practice','p@example.com')")
        self.assertEqual(self.checks()["final.booking_pattern"]["status"], "PASS")
        self.conn.execute("UPDATE escape_booking SET total_price=9999.99 WHERE booking_id=2")
        self.assertEqual(self.checks()["final.booking_pattern"]["status"], "REVIEW")

    def test_deferred_constraints_are_checked(self):
        self.conn.execute("ALTER TABLE escape_booking DROP CONSTRAINT escape_booking_room_id_fkey")
        self.conn.execute("ALTER TABLE escape_booking ADD FOREIGN KEY(room_id) REFERENCES escape_room DEFERRABLE INITIALLY DEFERRED")
        c = self.checks(probes=True)
        self.assertEqual(c["booking.missing_room_id"]["status"], "PASS")
        self.assertEqual(c["escape_room.delete_with_cancelled_booking"]["status"], "PASS")

    def test_inexact_prices_and_fractional_sizes(self):
        self.conn.execute("ALTER TABLE escape_booking ALTER COLUMN total_price TYPE real")
        self.conn.execute("ALTER TABLE escape_booking ALTER COLUMN party_size TYPE numeric")
        c = self.checks(probes=True)
        self.assertEqual(c["escape_booking.total_price.exact_type"]["status"], "FAIL")
        self.assertEqual(c["escape_booking.total_price.10000.00"]["status"], "FAIL")
        self.assertEqual(c["escape_booking.party_size.whole_number"]["status"], "FAIL")

    def test_price_range_too_small(self):
        self.conn.execute("ALTER TABLE escape_booking ALTER COLUMN total_price TYPE numeric(4,2)")
        self.assertEqual(self.checks(probes=True)["escape_booking.total_price.9999.99"]["status"], "FAIL")

    def test_rls_probes_skipped(self):
        self.conn.execute("ALTER TABLE escape_booking ENABLE ROW LEVEL SECURITY")
        c = self.checks(probes=True)
        self.assertEqual(c["behavior.preflight"]["status"], "SKIP")
        self.assertNotIn("booking.valid_seed", c)

    def test_cli_batch_continues_and_writes_private_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            params = psycopg.conninfo.conninfo_to_dict(os.environ["A3_TEST_DSN"])
            env = {"PG" + k.upper(): v for k, v in params.items() if k in ("host", "port", "user", "password")}
            env["PGDATABASE"] = params.get("dbname", "postgres")
            out = Path(temp) / "checks"
            with patch.dict(os.environ, env):
                code = M.main(["--schema", "missing_a3_student", "--schema", self.schema,
                               "--probe-writes", "--output", str(out)])
            self.assertEqual(code, 0)
            data = json.loads((out / "results.json").read_text())
            self.assertEqual(len(data["schemas"]), 2)
            good = data["schemas"][1]
            self.assertTrue(all(c["status"] == "PASS" for c in good["checks"]))


if __name__ == "__main__":
    unittest.main()
