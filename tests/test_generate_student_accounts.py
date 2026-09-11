import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_student_accounts.py"
SPEC = importlib.util.spec_from_file_location("generate_student_accounts", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class StudentAccountProvisioningTests(unittest.TestCase):
    def write_roster(self, directory: Path, rows: list[str]) -> Path:
        roster = directory / "roster.csv"
        roster.write_text(
            "Student,ID,SIS User ID,SIS Login ID,Section\n" + "\n".join(rows) + "\n",
            encoding="utf-8",
        )
        return roster

    def config(self) -> MODULE.Config:
        return MODULE.Config(
            course_label="CSCI 340",
            term_label="Autumn 2026",
            host="db.school.edu",
            port=5432,
            database="csci340",
            sslmode="require",
            username_prefix="csci340_",
            login_group="csci340_students",
            password_length=24,
            create_personal_schema=True,
            connection_limit=5,
            password_valid_until="2026-12-31 23:59:59-07:00",
            support_email="instructor@school.edu",
        )

    def test_reads_students_and_skips_points_possible(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            roster = self.write_roster(
                directory,
                ['"Able, Ada",101,1001,abc123456,01', "Points Possible,,,,"],
            )
            students, ignored = MODULE.read_canvas_roster(roster, "csci340_")
            self.assertEqual(len(students), 1)
            self.assertEqual(ignored, 1)
            self.assertEqual(students[0].database_username, "csci340_abc123456")

    def test_duplicate_login_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            roster = self.write_roster(
                directory,
                [
                    '"Able, Ada",101,1001,abc123456,01',
                    '"Baker, Ben",102,1002,abc123456,01',
                ],
            )
            with self.assertRaises(MODULE.ProvisioningError):
                MODULE.read_canvas_roster(roster, "csci340_")

    def test_generated_password_meets_contract(self):
        password = MODULE.generate_password(24)
        self.assertEqual(len(password), 24)
        self.assertTrue(any(character.isupper() for character in password))
        self.assertTrue(any(character.islower() for character in password))
        self.assertTrue(any(character.isdigit() for character in password))
        self.assertTrue(set(password) <= set(MODULE.PASSWORD_ALPHABET))

    def test_sql_has_preflight_transaction_and_personal_schema(self):
        student = MODULE.Student("Able, Ada", "101", "abc123456", "csci340_abc123456")
        sql = MODULE.build_sql([student], {student.database_username: "Abcd2345-Efgh6789_Jkl"}, self.config())
        self.assertIn(r"\set ON_ERROR_STOP on", sql)
        self.assertIn("BEGIN;", sql)
        self.assertIn("Existing roles detected", sql)
        self.assertIn('CREATE ROLE "csci340_abc123456"', sql)
        self.assertIn('CREATE ROLE "csci340_students" NOLOGIN', sql)
        self.assertIn('GRANT "csci340_students" TO "csci340_abc123456";', sql)
        self.assertIn('CREATE SCHEMA "csci340_abc123456";', sql)
        self.assertNotIn('AUTHORIZATION "csci340_abc123456"', sql)
        self.assertIn('REVOKE ALL ON SCHEMA "csci340_abc123456" FROM PUBLIC;', sql)
        self.assertIn(
            'GRANT USAGE, CREATE ON SCHEMA "csci340_abc123456" TO "csci340_abc123456";',
            sql,
        )
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))

    def test_existing_account_group_migration_has_preflight_and_membership(self):
        student = MODULE.Student("Able, Ada", "101", "abc123456", "csci340_abc123456")
        sql = MODULE.build_existing_account_group_sql([student], self.config())
        self.assertIn(r"\set ON_ERROR_STOP on", sql)
        self.assertIn("Expected student roles are missing", sql)
        self.assertIn('CREATE ROLE "csci340_students" NOLOGIN', sql)
        self.assertIn('GRANT "csci340_students" TO "csci340_abc123456";', sql)
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))

    def test_outputs_are_private_and_refuse_overwrite(self):
        student = MODULE.Student("Able, Ada", "101", "abc123456", "csci340_abc123456")
        with tempfile.TemporaryDirectory() as directory_name:
            output = Path(directory_name) / "output"
            MODULE.write_outputs(output, [student], 1, self.config())
            self.assertTrue((output / "provision-accounts.sql").exists())
            self.assertTrue((output / "credential-manifest.csv").exists())
            self.assertTrue((output / "credential-handouts" / "csci340_abc123456.txt").exists())
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(output / "credential-manifest.csv").st_mode & 0o777, 0o600)
            with self.assertRaises(MODULE.ProvisioningError):
                MODULE.write_outputs(output, [student], 1, self.config())


if __name__ == "__main__":
    unittest.main()
