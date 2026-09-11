#!/usr/bin/env python3
"""Generate PostgreSQL student roles and private credential handouts.

This script reads only the identity columns from a Canvas gradebook export. Its
default mode validates the roster and configuration without generating secrets.
Pass --write to create a SQL provisioning file, a private credential manifest,
and one text handout per student.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import secrets
import shlex
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = ("Student", "ID", "SIS Login ID")
PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_"
PLACEHOLDER_MARKERS = ("example", "replace-me", "your-")


class ProvisioningError(ValueError):
    """Raised when roster or configuration validation fails."""


@dataclass(frozen=True)
class Student:
    display_name: str
    canvas_id: str
    sis_login_id: str
    database_username: str


@dataclass(frozen=True)
class Config:
    course_label: str
    term_label: str
    host: str
    port: int
    database: str
    sslmode: str
    username_prefix: str
    login_group: str
    password_length: int
    create_personal_schema: bool
    connection_limit: int
    password_valid_until: str
    support_email: str


def _required(mapping: dict, key: str, section: str) -> object:
    if key not in mapping:
        raise ProvisioningError(f"Missing [{section}] {key!r} in configuration.")
    return mapping[key]


def load_config(path: Path, *, allow_placeholders: bool) -> Config:
    try:
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProvisioningError(f"Could not read configuration {path}: {exc}") from exc

    course = raw.get("course", {})
    database = raw.get("database", {})
    accounts = raw.get("accounts", {})
    instructions = raw.get("instructions", {})

    config = Config(
        course_label=str(_required(course, "label", "course")).strip(),
        term_label=str(_required(course, "term", "course")).strip(),
        host=str(_required(database, "host", "database")).strip(),
        port=int(database.get("port", 5432)),
        database=str(_required(database, "name", "database")).strip(),
        sslmode=str(database.get("sslmode", "require")).strip(),
        username_prefix=str(accounts.get("username_prefix", "")).strip().lower(),
        login_group=str(accounts.get("login_group", "")).strip().lower(),
        password_length=int(accounts.get("password_length", 24)),
        create_personal_schema=bool(accounts.get("create_personal_schema", True)),
        connection_limit=int(accounts.get("connection_limit", 5)),
        password_valid_until=str(accounts.get("password_valid_until", "")).strip(),
        support_email=str(instructions.get("support_email", "")).strip(),
    )

    if not config.course_label or not config.term_label:
        raise ProvisioningError("Course label and term must not be blank.")
    if not config.host or not config.database:
        raise ProvisioningError("Database host and name must not be blank.")
    if not 1 <= config.port <= 65535:
        raise ProvisioningError("Database port must be between 1 and 65535.")
    if not re.fullmatch(r"[a-z0-9_]*", config.username_prefix):
        raise ProvisioningError("Username prefix may contain only lowercase letters, digits, and underscores.")
    if not re.fullmatch(r"[a-z0-9_]+", config.login_group):
        raise ProvisioningError("Login group may contain only lowercase letters, digits, and underscores.")
    if len(config.login_group.encode("utf-8")) > 63:
        raise ProvisioningError("Login group exceeds PostgreSQL's 63-byte limit.")
    if config.password_length < 18:
        raise ProvisioningError("Password length must be at least 18 characters.")
    if not 1 <= config.connection_limit <= 50:
        raise ProvisioningError("Connection limit must be between 1 and 50.")
    if config.password_valid_until:
        try:
            datetime.fromisoformat(config.password_valid_until)
        except ValueError as exc:
            raise ProvisioningError(
                "password_valid_until must be blank or an ISO date/time, for example "
                "2026-12-31 23:59:59-07:00."
            ) from exc

    if not allow_placeholders:
        values = (config.host.casefold(), config.database.casefold())
        if any(marker in value for marker in PLACEHOLDER_MARKERS for value in values):
            raise ProvisioningError(
                "Replace the example database host and name before using --write."
            )

    return config


def make_database_username(sis_login_id: str, prefix: str) -> str:
    login = sis_login_id.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]+", login):
        raise ProvisioningError(
            f"SIS Login ID {sis_login_id!r} contains characters not allowed by this workflow."
        )
    username = f"{prefix}{login}"
    if len(username.encode("utf-8")) > 63:
        raise ProvisioningError(f"Database username {username!r} exceeds PostgreSQL's 63-byte limit.")
    return username


def read_canvas_roster(path: Path, username_prefix: str) -> tuple[list[Student], int]:
    try:
        stream = path.open(newline="", encoding="utf-8-sig")
    except OSError as exc:
        raise ProvisioningError(f"Could not open roster {path}: {exc}") from exc

    with stream:
        reader = csv.DictReader(stream)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ProvisioningError(f"Roster is missing required columns: {', '.join(missing)}")

        students: list[Student] = []
        ignored_rows = 0
        for row_number, row in enumerate(reader, start=2):
            display_name = (row.get("Student") or "").strip()
            canvas_id = (row.get("ID") or "").strip()
            sis_login_id = (row.get("SIS Login ID") or "").strip()

            if not any((display_name, canvas_id, sis_login_id)):
                ignored_rows += 1
                continue
            if display_name.casefold() == "points possible":
                ignored_rows += 1
                continue
            if not display_name or not canvas_id or not sis_login_id:
                raise ProvisioningError(
                    f"Roster row {row_number} is missing Student, ID, or SIS Login ID."
                )
            if any(ord(character) < 32 for character in display_name):
                raise ProvisioningError(f"Roster row {row_number} has control characters in Student.")

            students.append(
                Student(
                    display_name=display_name,
                    canvas_id=canvas_id,
                    sis_login_id=sis_login_id,
                    database_username=make_database_username(sis_login_id, username_prefix),
                )
            )

    if not students:
        raise ProvisioningError("Roster contains no student rows.")

    for label, values in (
        ("Canvas ID", [student.canvas_id for student in students]),
        ("SIS Login ID", [student.sis_login_id.casefold() for student in students]),
        ("database username", [student.database_username for student in students]),
    ):
        duplicates = sorted(value for value in set(values) if values.count(value) > 1)
        if duplicates:
            raise ProvisioningError(f"Duplicate {label} values detected; no output written.")

    return students, ignored_rows


def generate_password(length: int) -> str:
    while True:
        password = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))
        if (
            any(character.isupper() for character in password)
            and any(character.islower() for character in password)
            and any(character.isdigit() for character in password)
        ):
            return password


def sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_sql(students: Iterable[Student], passwords: dict[str, str], config: Config) -> str:
    student_list = list(students)
    protected_roles = [config.login_group, *(student.database_username for student in student_list)]
    role_literals = ", ".join(sql_literal(role) for role in protected_roles)
    login_group = sql_identifier(config.login_group)
    lines = [
        "-- PostgreSQL student-account provisioning",
        f"-- {config.course_label}, {config.term_label}",
        "-- Contains plaintext generated passwords. Store and transmit privately.",
        r"\set ON_ERROR_STOP on",
        "",
        "BEGIN;",
        "",
        "DO $preflight$",
        "DECLARE",
        "    conflicts text;",
        "BEGIN",
        f"    IF current_database() <> {sql_literal(config.database)} THEN",
        "        RAISE EXCEPTION 'Connected to database %, expected %. No changes were applied.',",
        f"            current_database(), {sql_literal(config.database)};",
        "    END IF;",
        "    SELECT string_agg(rolname::text, ', ' ORDER BY rolname::text)",
        "      INTO conflicts",
        "      FROM pg_catalog.pg_roles",
        f"     WHERE rolname::text = ANY (ARRAY[{role_literals}]::text[]);",
        "    IF conflicts IS NOT NULL THEN",
        "        RAISE EXCEPTION 'Existing roles detected: %. No changes were applied.', conflicts;",
        "    END IF;",
        "END",
        "$preflight$;",
        "",
        f"CREATE ROLE {login_group} NOLOGIN",
        "    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;",
        "",
    ]

    valid_until = (
        f" VALID UNTIL {sql_literal(config.password_valid_until)}"
        if config.password_valid_until
        else ""
    )
    database_identifier = sql_identifier(config.database)

    for student in student_list:
        role = sql_identifier(student.database_username)
        password = sql_literal(passwords[student.database_username])
        lines.extend(
            [
                f"CREATE ROLE {role} LOGIN PASSWORD {password}{valid_until}",
                "    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION",
                f"    CONNECTION LIMIT {config.connection_limit};",
                f"GRANT {login_group} TO {role};",
                f"GRANT CONNECT ON DATABASE {database_identifier} TO {role};",
            ]
        )
        if config.create_personal_schema:
            lines.extend(
                [
                    f"CREATE SCHEMA {role};",
                    f"REVOKE ALL ON SCHEMA {role} FROM PUBLIC;",
                    f"GRANT USAGE, CREATE ON SCHEMA {role} TO {role};",
                    f"ALTER ROLE {role} IN DATABASE {database_identifier}",
                    f"    SET search_path TO {role}, public;",
                ]
            )
        lines.append("")

    lines.extend(["COMMIT;", ""])
    return "\n".join(lines)


def build_existing_account_group_sql(students: Iterable[Student], config: Config) -> str:
    """Build a one-time migration that groups roles created by an earlier package."""
    student_list = list(students)
    role_literals = ", ".join(sql_literal(student.database_username) for student in student_list)
    login_group = sql_identifier(config.login_group)
    lines = [
        "-- Add existing student logins to the course HBA group",
        f"-- {config.course_label}, {config.term_label}",
        r"\set ON_ERROR_STOP on",
        "",
        "BEGIN;",
        "",
        "DO $preflight$",
        "DECLARE",
        "    missing_roles text;",
        "BEGIN",
        f"    IF current_database() <> {sql_literal(config.database)} THEN",
        "        RAISE EXCEPTION 'Connected to database %, expected %. No changes were applied.',",
        f"            current_database(), {sql_literal(config.database)};",
        "    END IF;",
        f"    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = {sql_literal(config.login_group)}) THEN",
        f"        RAISE EXCEPTION 'Role {config.login_group} already exists. Inspect it before continuing.';",
        "    END IF;",
        "    SELECT string_agg(expected_role, ', ' ORDER BY expected_role)",
        "      INTO missing_roles",
        f"      FROM unnest(ARRAY[{role_literals}]::text[]) AS expected_roles(expected_role)",
        "     WHERE NOT EXISTS (",
        "               SELECT FROM pg_catalog.pg_roles",
        "                WHERE rolname::text = expected_role",
        "           );",
        "    IF missing_roles IS NOT NULL THEN",
        "        RAISE EXCEPTION 'Expected student roles are missing: %. No changes were applied.', missing_roles;",
        "    END IF;",
        "END",
        "$preflight$;",
        "",
        f"CREATE ROLE {login_group} NOLOGIN",
        "    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;",
        "",
    ]
    lines.extend(
        f"GRANT {login_group} TO {sql_identifier(student.database_username)};"
        for student in student_list
    )
    lines.extend(["", "COMMIT;", ""])
    return "\n".join(lines)


def build_handout(student: Student, password: str, config: Config) -> str:
    conninfo = (
        f"host={config.host} port={config.port} dbname={config.database} "
        f"user={student.database_username} sslmode={config.sslmode}"
    )
    lines = [
        f"{config.course_label} PostgreSQL account",
        config.term_label,
        "",
        f"Student: {student.display_name}",
        f"Host: {config.host}",
        f"Port: {config.port}",
        f"Database: {config.database}",
        f"Username: {student.database_username}",
        f"Password: {password}",
        f"SSL mode: {config.sslmode}",
        "",
        "Connect with psql",
        shlex.join(["psql", conninfo]),
        "",
        "The command prompts for the password above; it does not place the password in shell history.",
        "",
        "Connection check",
        "After connecting, run:",
        "",
        "SELECT current_user AS database_user, current_database() AS database_name;",
    ]
    if config.create_personal_schema:
        lines.extend(
            [
                "",
                "Then verify that your personal schema is writable:",
                "",
                "CREATE TABLE connection_check (message text);",
                "INSERT INTO connection_check VALUES ('connected');",
                "SELECT * FROM connection_check;",
                "DROP TABLE connection_check;",
            ]
        )
    lines.extend(
        [
            "",
            "Keep this password private. Do not post it in Canvas discussions, email threads, or screenshots.",
        ]
    )
    if config.support_email:
        lines.append(f"If the connection fails, contact {config.support_email} privately.")
    lines.append("")
    return "\n".join(lines)


def _write_private_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o600)


def write_outputs(
    output_dir: Path,
    students: list[Student],
    ignored_rows: int,
    config: Config,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ProvisioningError(
            f"Output directory {output_dir} is not empty. Use a new directory to avoid replacing passwords."
        )

    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    handout_dir = output_dir / "credential-handouts"
    handout_dir.mkdir(mode=0o700)

    passwords = {
        student.database_username: generate_password(config.password_length)
        for student in students
    }

    _write_private_text(
        output_dir / "provision-accounts.sql",
        build_sql(students, passwords, config),
    )

    manifest_path = output_dir / "credential-manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "Student",
                "Canvas ID",
                "SIS Login ID",
                "Database Username",
                "Password",
                "Handout Filename",
            ]
        )
        for student in students:
            filename = f"{student.database_username}.txt"
            writer.writerow(
                [
                    student.display_name,
                    student.canvas_id,
                    student.sis_login_id,
                    student.database_username,
                    passwords[student.database_username],
                    filename,
                ]
            )
            _write_private_text(
                handout_dir / filename,
                build_handout(student, passwords[student.database_username], config),
            )
    os.chmod(manifest_path, 0o600)

    summary = "\n".join(
        [
            f"Course: {config.course_label}",
            f"Term: {config.term_label}",
            f"Student accounts generated: {len(students)}",
            f"Non-student rows ignored: {ignored_rows}",
            f"Database: {config.database} on {config.host}:{config.port}",
            f"Personal schemas: {'yes' if config.create_personal_schema else 'no'}",
            "",
            "Sensitive files: provision-accounts.sql, credential-manifest.csv, credential-handouts/",
            "Apply the SQL only after reviewing the manifest and configuration.",
            "",
        ]
    )
    _write_private_text(output_dir / "generation-summary.txt", summary)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, required=True, help="Canvas gradebook CSV export")
    parser.add_argument("--config", type=Path, required=True, help="TOML provisioning configuration")
    parser.add_argument("--output-dir", type=Path, help="Private output directory; required with --write")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Generate passwords and private files; without this flag the script only validates",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.config, allow_placeholders=not args.write)
        students, ignored_rows = read_canvas_roster(args.roster, config.username_prefix)
        if not args.write:
            print(
                f"Validated {len(students)} student rows; ignored {ignored_rows} non-student row(s); "
                f"derived {len(students)} unique database usernames. No files written."
            )
            return 0
        if args.output_dir is None:
            raise ProvisioningError("--output-dir is required when using --write.")
        write_outputs(args.output_dir, students, ignored_rows, config)
        print(
            f"Generated {len(students)} accounts and handouts in {args.output_dir}. "
            "Treat the directory as restricted because it contains plaintext passwords."
        )
        return 0
    except ProvisioningError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
