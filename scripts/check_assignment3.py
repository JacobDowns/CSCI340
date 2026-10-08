#!/usr/bin/env python3
"""Inspect Assignment 3 schemas; optionally run rolled-back behavioral probes.

Requires psycopg 3. Uses libpq environment variables / a service for credentials.
Never commits a transaction. See assignment3-checks.md before --probe-writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import html
import json
import os
from pathlib import Path
import sys
import tomllib
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


FIELDS = {
    "escape_room": "room_id room_code room_name capacity difficulty is_active".split(),
    "escape_team": "team_id team_name contact_email".split(),
    "escape_booking": ("booking_id room_id team_id starts_at ends_at party_size "
                       "total_price status special_requests").split(),
}
GROUP_DATA = "Accessible tables and final data (2 points)"
GROUP_DEFAULT = "Defaults and permitted duplicates (2 points)"
GROUP_INVALID = "Invalid data rejection (4 points)"
GROUP_HISTORY = "Protected booking history (2 points)"


def money(value):
    try:
        amount = Decimal(str(value))
        return amount if amount.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def final_data_checks(rows):
    """Find candidate assignment records by business values, never guessed IDs.

    Additional practice rows are permitted. Missing/ambiguous patterns are REVIEW,
    since Q10 changes or a reset can explain them. Return evidence, not grades.
    """
    rooms, teams, bookings = (rows[t] for t in FIELDS)
    findings = []
    selected = {}
    for code in ("LIB-01", "LIB-02"):
        hits = [r for r in rooms if r.get("room_code") == code]
        selected[code] = hits
        okay = len(hits) == 1 and hits[0].get("room_name") == "The Library After Midnight"
        findings.append((f"final.{code}", "PASS" if okay else "REVIEW",
                         {"candidates": hits, "expected_name": "The Library After Midnight"}))
    vipers = [t for t in teams if t.get("team_name") == "The Vipers"
              and t.get("contact_email") == "vipers@example.com"]
    clues = [t for t in teams if t.get("team_name") == "The Clue Crew"
             and t.get("contact_email") == "clues@example.com"]
    findings.append(("final.teams", "PASS" if len(vipers) == 2 and len(clues) == 1 else "REVIEW",
                     {"vipers": vipers, "clue_crew": clues}))
    candidates = []
    for r1 in selected["LIB-01"]:
        for r2 in selected["LIB-02"]:
            for team in vipers:
                linked = [b for b in bookings if b.get("team_id") == team.get("team_id")
                          and b.get("room_id") == r1.get("room_id")]
                paid = [b for b in linked if money(b.get("total_price")) == Decimal("79.50")
                        and b.get("status") == "completed"]
                free = [b for b in linked if money(b.get("total_price")) == 0
                        and b.get("status") == "reserved"]
                crew = [b for b in bookings if b.get("room_id") == r2.get("room_id")
                        and any(b.get("team_id") == c.get("team_id") for c in clues)
                        and b.get("status") == "reserved"
                        and money(b.get("total_price")) is not None
                        and 0 <= money(b.get("total_price")) <= Decimal("9999.99")]
                unbooked = [v for v in vipers if v.get("team_id") != team.get("team_id")
                            and not any(b.get("team_id") == v.get("team_id") for b in bookings)]
                for p in paid:
                    for f in free:
                        # A later Q10 change is deliberately sent for review.
                        different_dates = str(p.get("starts_at"))[:10] != str(f.get("starts_at"))[:10]
                        for c in crew:
                            if different_dates and unbooked:
                                candidates.append({"paid": p, "free": f, "clue_crew": c,
                                                   "unbooked_vipers": unbooked})
    findings.append(("final.booking_pattern", "PASS" if len(candidates) == 1 else "REVIEW",
                     {"matching_sets": candidates,
                      "note": "Compare generated IDs with submission; review Q10 changes and ambiguous matches."}))
    return findings


class Checker:
    def __init__(self, conn, schema, student="", row_limit=1000):
        self.conn, self.schema = conn, schema
        self.result = {"schema": schema, "student": student, "checks": [],
                       "columns": {}, "constraints": {}, "rows": {}}
        self.row_limit = row_limit
        self.trace = None

    def add(self, group, name, status, detail):
        self.result["checks"].append(dict(group=group, check=name, status=status, detail=detail))

    def table(self, table):
        return sql.Identifier(self.schema, table)

    def query(self, statement, params=None):
        if self.trace is not None:
            self.trace.append({"sql": statement.as_string(self.conn) if isinstance(statement, sql.Composable) else statement,
                               "parameters": params})
        return self.conn.execute(statement, params).fetchall()

    def inspect(self):
        complete = True
        for table, fields in FIELDS.items():
            try:
                with self.conn.transaction(force_rollback=True):
                    rel = self.query("""
                        SELECT c.oid, c.relkind, c.relpersistence, c.relrowsecurity,
                               EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgrelid=c.oid
                                      AND NOT t.tgisinternal AND t.tgenabled <> 'D') AS user_triggers,
                               EXISTS(SELECT 1 FROM pg_rewrite r WHERE r.ev_class=c.oid) AS rules,
                               EXISTS(SELECT 1 FROM pg_inherits i
                                      WHERE i.inhparent=c.oid OR i.inhrelid=c.oid) AS inheritance
                        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                        WHERE n.nspname=%s AND c.relname=%s
                    """, (self.schema, table))
                    if not rel or rel[0]["relkind"] != "r" or rel[0]["relpersistence"] != "p":
                        self.add(GROUP_DATA, f"{table}.accessible", "FAIL",
                                 "Missing permanent ordinary table, or unsupported relation kind.")
                        complete = False
                        continue
                    oid = rel[0]["oid"]
                    cols = self.query("""
                        SELECT a.attname AS name, format_type(a.atttypid,a.atttypmod) AS type,
                               a.attnotnull AS not_null, a.attidentity AS identity,
                               a.attgenerated AS generated, pg_get_expr(d.adbin,d.adrelid) AS default
                        FROM pg_attribute a LEFT JOIN pg_attrdef d
                          ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                        WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum
                    """, (oid,))
                    constraints = self.query("""
                        SELECT c.conname AS name, c.contype AS kind, c.convalidated AS validated,
                               pg_get_constraintdef(c.oid) AS definition, c.confdeltype AS delete_action,
                               fn.nspname AS referenced_schema, fc.relname AS referenced_table,
                               ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(num,pos)
                                     JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.num
                                     ORDER BY pos) AS columns,
                               ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY k(num,pos)
                                     JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.num
                                     ORDER BY pos) AS referenced_columns
                        FROM pg_constraint c LEFT JOIN pg_class fc ON fc.oid=c.confrelid
                        LEFT JOIN pg_namespace fn ON fn.oid=fc.relnamespace WHERE c.conrelid=%s
                    """, (oid,))
                    self.result["columns"][table] = cols
                    self.result["constraints"][table] = constraints
                    self.result.setdefault("relations", {})[table] = rel[0]
                    by_name = {c["name"]: c for c in cols}
                    missing = sorted(set(fields) - set(by_name))
                    self.add(GROUP_DATA, f"{table}.columns", "FAIL" if missing else "PASS",
                             {"missing": missing})
                    complete &= not missing
                    key = fields[0]
                    pk = any(c["kind"] == "p" and c["columns"] == [key] for c in constraints)
                    self.add(GROUP_INVALID, f"{table}.primary_key", "PASS" if pk else "FAIL",
                             f"Expected primary key on {key}.")
                    for field in fields:
                        if field not in by_name:
                            continue
                        col = by_name[field]
                        if field != "special_requests":
                            self.add(GROUP_INVALID, f"{table}.{field}.required",
                                     "PASS" if col["not_null"] else "REVIEW",
                                     "NOT NULL present." if col["not_null"] else
                                     "No column NOT NULL; check domain/constraints or behavioral result.")
                    if key in by_name:
                        col = by_name[key]
                        self.add(GROUP_DEFAULT, f"{table}.generated_id",
                                 "PASS" if col["identity"] or col["default"] else "FAIL", col)
                    if not missing:
                        data = self.query(sql.SQL("SELECT * FROM {} ORDER BY {} LIMIT %s").format(
                            self.table(table), sql.Identifier(key)), (self.row_limit + 1,))
                        self.result["rows"][table] = data[:self.row_limit]
                        truncated = len(data) > self.row_limit
                        self.add(GROUP_DATA, f"{table}.accessible", "PASS", {"rows_captured": min(len(data), self.row_limit)})
                        if truncated:
                            complete = False
                            self.add(GROUP_DATA, f"{table}.snapshot", "REVIEW",
                                     "Row limit reached; increase --row-limit for final-data matching.")
            except psycopg.Error as exc:
                complete = False
                self.add(GROUP_DATA, f"{table}.accessible", "ERROR", db_error(exc))
        if complete:
            for name, status, detail in final_data_checks(self.result["rows"]):
                self.add(GROUP_DATA, name, status, detail)
        else:
            self.add(GROUP_DATA, "final.data", "SKIP", "Requires all expected columns and complete snapshots.")
        self.inspect_types_and_fks()
        return complete

    def inspect_types_and_fks(self):
        for table, field, allowed in [
            ("escape_room", "is_active", ("boolean",)),
            ("escape_booking", "starts_at", ("timestamp without time zone", "timestamp with time zone")),
            ("escape_booking", "ends_at", ("timestamp without time zone", "timestamp with time zone")),
        ]:
            col = next((c for c in self.result["columns"].get(table, []) if c["name"] == field), None)
            if col:
                self.add(GROUP_INVALID, f"{table}.{field}.type",
                         "PASS" if col["type"] in allowed else "REVIEW", col)
        col = next((c for c in self.result["columns"].get("escape_booking", []) if c["name"] == "total_price"), None)
        if col:
            self.add(GROUP_INVALID, "escape_booking.total_price.exact_type",
                     "FAIL" if col["type"] in ("real", "double precision") else
                     "PASS" if col["type"].startswith("numeric") or col["type"] == "money" else "REVIEW", col)
        for field, parent in (("room_id", "escape_room"), ("team_id", "escape_team")):
            fks = [c for c in self.result["constraints"].get("escape_booking", [])
                   if c["kind"] == "f" and c["columns"] == [field]
                   and c["referenced_schema"] == self.schema and c["referenced_table"] == parent
                   and c["referenced_columns"] == [field]]
            okay = any(c["delete_action"] in ("a", "r") and c["validated"] for c in fks)
            self.add(GROUP_HISTORY, f"{field}.foreign_key", "PASS" if okay else "REVIEW",
                     {"matching_foreign_keys": fks, "expected": "Validated FK to own parent table; NO ACTION or RESTRICT."})

    def insert(self, table, values):
        return self.query(sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            self.table(table), sql.SQL(", ").join(map(sql.Identifier, values)),
            sql.SQL(", ").join(sql.Placeholder() for _ in values)), tuple(values.values()))[0]

    def update(self, table, row, values):
        key = FIELDS[table][0]
        return self.query(sql.SQL("UPDATE {} SET {} WHERE {} = %s RETURNING *").format(
            self.table(table), sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in values),
            sql.Identifier(key)), (*values.values(), row[key]))

    def probe(self, group, name, action, *, reject=None, verify=None, column=None):
        """Rollback every individual attempt; flush deferred constraints before success."""
        self.trace = []
        try:
            with self.conn.transaction(force_rollback=True):
                value = action()
                self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                if reject:
                    self.add(group, name, "FAIL", {"reason": "Invalid operation accepted", "returned": value})
                elif verify and not verify(value):
                    self.add(group, name, "FAIL", {"reason": "Stored result differs from requirement", "returned": value})
                else:
                    self.add(group, name, "PASS", {"returned": value})
        except psycopg.Error as exc:
            correct_error = reject and exc.sqlstate in reject
            wrong_column = column and exc.diag.column_name and exc.diag.column_name != column
            status = "PASS" if correct_error and not wrong_column else "REVIEW" if reject else "FAIL"
            if exc.sqlstate in ("42501", "57014", "55P03") or (exc.sqlstate or "").startswith("08"):
                status = "ERROR"
            self.add(group, name, status, db_error(exc))
        finally:
            if self.result["checks"] and self.result["checks"][-1]["check"] == name:
                self.result["checks"][-1]["detail"]["statements"] = self.trace
            self.trace = None

    def behavior(self):
        relations = self.result.get("relations", {})
        if any(t not in relations or any(relations[t][k] for k in
               ("relrowsecurity", "user_triggers", "rules", "inheritance")) for t in FIELDS):
            self.add(GROUP_DEFAULT, "behavior.preflight", "SKIP",
                     "Probes support ordinary tables without RLS, enabled user triggers, rules or inheritance. Review manually.")
            return
        if any(set(FIELDS[t]) - {c["name"] for c in self.result["columns"].get(t, [])} for t in FIELDS):
            self.add(GROUP_DEFAULT, "behavior.preflight", "SKIP", "Missing required columns; inspect catalog findings.")
            return
        tag = uuid.uuid4().hex[:4].upper()
        rv = dict(room_code="I" + tag + "A", room_name="Check " + tag, capacity=8,
                  difficulty="standard", is_active=True)
        tv = dict(team_name="Check " + tag, contact_email=tag.lower() + "@example.com")
        seeds = {}
        for table, values in (("escape_room", rv), ("escape_team", tv)):
            try:
                with self.conn.transaction():
                    seeds[table] = self.insert(table, values)
                    self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                self.add(GROUP_DEFAULT, f"{table}.valid_seed", "PASS", seeds[table])
            except psycopg.Error as exc:
                self.add(GROUP_DEFAULT, f"{table}.valid_seed", "ERROR" if exc.sqlstate == "42501" else "FAIL", db_error(exc))
        if "escape_room" in seeds:
            omitted = {k: v for k, v in rv.items() if k != "is_active"}
            omitted["room_code"] = "I" + tag + "B"
            # A distinct name avoids mixing the default and duplicate-name tests.
            omitted["room_name"] = "Other " + tag
            self.probe(GROUP_DEFAULT, "room.default_active", lambda: self.insert("escape_room", omitted),
                       verify=lambda r: r["is_active"] is True)
            self.probe(GROUP_DEFAULT, "room.duplicate_name", lambda: self.insert("escape_room", {**rv, "room_code": "I" + tag + "B"}))
            self.probe(GROUP_INVALID, "room.duplicate_code", lambda: self.insert("escape_room", {**rv, "room_name": "Other " + tag}), reject={"23505"})
        if "escape_team" in seeds:
            self.probe(GROUP_DEFAULT, "team.duplicate_name_and_email", lambda: self.insert("escape_team", tv))
        if "escape_room" in seeds and "escape_team" in seeds:
            start = datetime(2090, 1, 1, 10)
            bv = dict(room_id=seeds["escape_room"]["room_id"], team_id=seeds["escape_team"]["team_id"],
                      starts_at=start, ends_at=start + timedelta(hours=1), party_size=3,
                      total_price=Decimal("89.50"), status="reserved", special_requests=None)
            try:
                with self.conn.transaction():
                    seeds["escape_booking"] = self.insert("escape_booking", bv)
                    self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                self.add(GROUP_DEFAULT, "booking.valid_seed", "PASS", seeds["escape_booking"])
            except psycopg.Error as exc:
                self.add(GROUP_DEFAULT, "booking.valid_seed", "ERROR" if exc.sqlstate == "42501" else "FAIL", db_error(exc))
            if "escape_booking" in seeds:
                later = {**bv, "starts_at": start + timedelta(days=1), "ends_at": start + timedelta(days=1, hours=1)}
                self.probe(GROUP_DEFAULT, "booking.repeat_visit", lambda: self.insert("escape_booking", later))
                default = {k: v for k, v in later.items() if k not in ("status", "special_requests")}
                self.probe(GROUP_DEFAULT, "booking.defaults", lambda: self.insert("escape_booking", default),
                           verify=lambda b: b["status"] == "reserved" and b["special_requests"] is None)
        for table, row in seeds.items():
            for field in FIELDS[table]:
                if field == "special_requests":
                    self.probe(GROUP_DEFAULT, "booking.optional_requests", lambda t=table, r=row: self.update(t, r, {"special_requests": None}))
                    continue
                self.probe(GROUP_INVALID, f"{table}.{field}.null", lambda t=table, r=row, f=field: self.update(t, r, {f: None}),
                           reject={"23502", "23514", "428C9"} if field == FIELDS[table][0] else {"23502", "23514"}, column=field)
        for table, fields in (("escape_room", ("room_code", "room_name")), ("escape_team", ("team_name", "contact_email"))):
            if table in seeds:
                for field in fields:
                    for label, value in (("empty", ""), ("spaces", "   ")):
                        self.probe(GROUP_INVALID, f"{table}.{field}.{label}",
                                   lambda t=table, f=field, v=value: self.update(t, seeds[t], {f: v}), reject={"23514"})
        cases = [
            ("escape_room", "capacity", [(2, True), (8, True), (1, False), (9, False)]),
            ("escape_room", "difficulty", [("introductory", True), ("standard", True), ("challenging", True), ("expert", False)]),
            ("escape_room", "is_active", [(False, True)]),
            ("escape_booking", "party_size", [(1, True), (8, True), (0, False), (9, False)]),
            ("escape_booking", "total_price", [("0.00", True), ("79.50", True), ("9999.99", True), ("-0.01", False), ("10000.00", False)]),
            ("escape_booking", "status", [("reserved", True), ("completed", True), ("cancelled", True), ("pending", False)]),
        ]
        for table, field, values in cases:
            if table not in seeds:
                continue
            for value, valid in values:
                self.probe(GROUP_INVALID, f"{table}.{field}.{value}",
                           lambda t=table, f=field, v=value: self.update(t, seeds[t], {f: v}),
                           reject=None if valid else {"23514", "22003", "22P02"},
                           verify=(lambda rows, v=value: len(rows) == 1 and money(rows[0]["total_price"]) == Decimal(v))
                           if valid and field == "total_price" else None)
        # Fractional numeric input must not remain fractional; integer coercion is legal.
        for table, field in (("escape_room", "capacity"), ("escape_booking", "party_size")):
            if table in seeds:
                try:
                    with self.conn.transaction(force_rollback=True):
                        returned = self.update(table, seeds[table], {field: Decimal("3.5")})
                        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                        v = money(returned[0][field])
                        self.add(GROUP_INVALID, f"{table}.{field}.whole_number", "PASS" if v is not None and v == v.to_integral_value() else "FAIL", returned)
                except psycopg.Error as exc:
                    self.add(GROUP_INVALID, f"{table}.{field}.whole_number", "PASS" if exc.sqlstate in {"23514", "22P02"} else "REVIEW", db_error(exc))
        if "escape_booking" not in seeds:
            self.add(GROUP_HISTORY, "booking.dependent_probes", "SKIP", "No valid booking fixture; remaining booking and deletion checks blocked.")
            return
        booking = seeds["escape_booking"]
        for label, end in (("equal", start), ("earlier", start - timedelta(minutes=1))):
            self.probe(GROUP_INVALID, "booking.ends_at." + label,
                       lambda e=end: self.update("escape_booking", booking, {"ends_at": e}), reject={"23514"})
        for field, value in (("starts_at", None), ("ends_at", None), ("ends_at", start)):
            self.probe(GROUP_INVALID, f"booking.cancelled.{field}.{value}",
                       lambda f=field, v=value: self.update("escape_booking", booking, {"status": "cancelled", f: v}),
                       reject={"23502", "23514"}, column=field)
        for field, parent in (("room_id", "escape_room"), ("team_id", "escape_team")):
            # A deleted, newly generated parent ID has the correct type and is known absent.
            def missing_reference(f=field, p=parent):
                vals = {**rv, "room_code": "I" + tag + "C", "room_name": "Missing " + tag} if p == "escape_room" else {"team_name": "Missing " + tag, "contact_email": "missing" + tag + "@example.com"}
                temp = self.insert(p, vals)
                self.conn.execute(sql.SQL("DELETE FROM {} WHERE {}=%s").format(self.table(p), sql.Identifier(f)), (temp[f],))
                absent = self.query(sql.SQL("SELECT 1 FROM {} WHERE {}=%s").format(self.table(p), sql.Identifier(f)), (temp[f],))
                if absent:
                    raise RuntimeError("Missing-reference fixture was not deleted")
                return self.update("escape_booking", booking, {f: temp[f]})
            self.probe(GROUP_INVALID, "booking.missing_" + field, missing_reference, reject={"23503"})
            for status in ("reserved", "cancelled"):
                def deletion(p=parent, f=field, st=status):
                    self.update("escape_booking", booking, {"status": st})
                    return self.query(sql.SQL("DELETE FROM {} WHERE {}=%s RETURNING *").format(
                        self.table(p), sql.Identifier(f)), (seeds[p][f],))
                self.probe(GROUP_HISTORY, f"{parent}.delete_with_{status}_booking", deletion, reject={"23503"})


def db_error(exc):
    # Avoid full connection errors/DSNs and server context that can expose secrets.
    return {"sqlstate": exc.sqlstate, "message": exc.diag.message_primary,
            "constraint": exc.diag.constraint_name, "column": exc.diag.column_name}


def check_schema(conn, schema, student="", *, probes=False, row_limit=1000, timeout_ms=5000):
    checker = Checker(conn, schema, student, row_limit)
    try:
        with conn.transaction(force_rollback=True):
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" + ("" if probes else " READ ONLY"))
            conn.execute("SELECT set_config('statement_timeout', %s, true)", (str(timeout_ms),))
            conn.execute("SELECT set_config('lock_timeout', '2000', true)")
            conn.execute("SELECT set_config('search_path', 'pg_catalog', true)")
            checker.inspect()
            if probes:
                checker.behavior()
            else:
                checker.add(GROUP_DEFAULT, "behavior", "SKIP", "Read-only mode; use --probe-writes for behavioral checks.")
    except psycopg.Error as exc:
        checker.add(GROUP_DATA, "schema.execution", "ERROR", db_error(exc))
    return checker.result


def read_schema_file(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        key = "schema" if "schema" in columns else "Database Username"
        if key not in columns:
            raise ValueError("CSV must have 'schema' or 'Database Username' column.")
        # Credential manifest may contain passwords; do not retain/export other fields.
        records = [(r.get(key, "").strip(), r.get("student", r.get("Student", "")).strip()) for r in reader]
    if any(not s or "\x00" in s for s, _ in records):
        raise ValueError("CSV contains empty or invalid schema names.")
    if len({s for s, _ in records}) != len(records):
        raise ValueError("CSV contains duplicate schema names.")
    return records


def write_reports(directory, results, mode):
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    payload = {"created_utc": datetime.now(timezone.utc).isoformat(), "mode": mode,
               "note": "Evidence, not grades. Review Q10 changes. Behavioral checks roll back table changes; sequence advances persist.",
               "schemas": results}
    (directory / "results.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    with (directory / "checks.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["schema", "student", "group", "check", "status", "detail"])
        for r in results:
            for c in r["checks"]:
                cells = [r["schema"], r["student"], c["group"], c["check"], c["status"], json.dumps(c["detail"], default=str)]
                writer.writerow(["'" + v if v.startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in cells])
    esc = lambda x: html.escape(str(x))
    sections = []
    for r in results:
        counts = Counter(c["status"] for c in r["checks"])
        lines = []
        for c in r["checks"]:
            lines.append(f'<tr><td class="{c["status"]}">{esc(c["status"])}</td><td>{esc(c["group"])}</td><td>{esc(c["check"])}</td><td><pre>{esc(json.dumps(c["detail"], indent=2, default=str))}</pre></td></tr>')
        sections.append(f'<section><h2>{esc(r["student"] or r["schema"])}</h2><p>{esc(r["schema"])} · {esc(dict(counts))}</p><details><summary>Check results</summary><table><thead><tr><th>Status</th><th>Group</th><th>Check</th><th>Evidence</th></tr></thead><tbody>{"".join(lines)}</tbody></table></details><details><summary>Stored rows and definitions</summary><pre>{esc(json.dumps({k:v for k,v in r.items() if k != "checks"}, indent=2, default=str))}</pre></details></section>')
    (directory / "report.html").write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Assignment 3 instructor checks</title>
<style>body{{font:16px system-ui;max-width:1400px;margin:2rem auto;padding:0 1rem;color:#162b3c;background:#f4f7fa}}section{{background:white;padding:1rem;margin:1rem 0;border:1px solid #ccd7df;border-radius:8px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd7df;padding:.5rem;vertical-align:top;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;max-width:70ch;font-size:13px}}.FAIL,.ERROR{{color:#a42121;font-weight:bold}}.REVIEW{{color:#815100;font-weight:bold}}.PASS{{color:#176137}}summary{{cursor:pointer;padding:.5rem}}input{{padding:.7rem;width:min(35rem,90%)}}</style>
<h1>Assignment 3 instructor checks</h1><p>{esc(payload["created_utc"])} · {esc(mode)} · {len(results)} schemas</p><p>{esc(payload["note"])}</p><p>PASS: this check succeeded. FAIL: observed requirement mismatch. REVIEW: ambiguous evidence or unexpected rejection. ERROR: access/execution problem. SKIP: not tested. Counts are not scores; catalog and behavioral checks can overlap.</p><label>Filter schemas or students <input id="filter" type="search"></label>{"".join(sections)}
<script>document.getElementById('filter').addEventListener('input',e=>{{for(const s of document.querySelectorAll('section'))s.hidden=!s.querySelector('h2').textContent.concat(s.querySelector('p').textContent).toLowerCase().includes(e.target.value.toLowerCase())}})</script></html>''', encoding="utf-8")
    for path in directory.iterdir():
        path.chmod(0o600)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--schema", action="append", help="Exact schema; repeat for multiple schemas")
    source.add_argument("--schema-file", type=Path, help="CSV: schema,student; also accepts provisioning manifest")
    source.add_argument("--schema-prefix", help="Discover existing schemas with this literal prefix (missing schemas cannot be detected)")
    parser.add_argument("--service", help="libpq service name; otherwise use PGHOST/PGDATABASE/PGUSER etc.")
    parser.add_argument("--config", type=Path, help="Provisioning TOML: read database host/port/name/sslmode only; PGUSER selects instructor")
    parser.add_argument("--probe-writes", action="store_true", help="Run rolled-back DML probes; sequence numbers may advance")
    parser.add_argument("--output", type=Path, default=Path("instructor-solutions") / ("assignment3-checks-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
    parser.add_argument("--row-limit", type=int, default=1000)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    args = parser.parse_args(argv)
    if args.row_limit < 1 or args.timeout_ms < 1 or args.schema_prefix == "":
        parser.error("Limits and schema prefix must be nonempty/positive.")
    if args.output.exists():
        parser.error("Output directory already exists; choose a new directory.")
    if args.service and args.config:
        parser.error("Choose --service or --config, not both.")
    os.umask(0o077)
    try:
        schemas = read_schema_file(args.schema_file) if args.schema_file else [(s, "") for s in dict.fromkeys(args.schema or [])]
        kwargs = {"service": args.service} if args.service else {}
        if args.config:
            with args.config.open("rb") as stream:
                database = tomllib.load(stream).get("database", {})
            if not database.get("host") or not database.get("name"):
                raise ValueError("Connection config requires [database] host and name.")
            kwargs = {"host": database["host"], "dbname": database["name"],
                      "port": database.get("port", 5432), "sslmode": database.get("sslmode", "require")}
        with psycopg.connect(autocommit=True, row_factory=dict_row, connect_timeout=10, **kwargs) as conn:
            if args.schema_prefix:
                schemas = [(r["nspname"], "") for r in conn.execute(
                    "SELECT nspname FROM pg_namespace WHERE left(nspname,length(%s))=%s ORDER BY nspname",
                    (args.schema_prefix, args.schema_prefix))]
            if not schemas:
                raise ValueError("No schemas selected.")
            results = []
            for i, (schema, student) in enumerate(schemas, 1):
                result = check_schema(conn, schema, student, probes=args.probe_writes,
                                      row_limit=args.row_limit, timeout_ms=args.timeout_ms)
                results.append(result)
                print(f"[{i}/{len(schemas)}] {schema}: {dict(Counter(c['status'] for c in result['checks']))}", flush=True)
        write_reports(args.output, results, "behavioral probes" if args.probe_writes else "read-only")
        print(f"Report: {args.output.resolve() / 'report.html'}")
        return 2 if any(c["status"] == "ERROR" for r in results for c in r["checks"]) else 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except psycopg.Error as exc:
        print(f"Database connection/execution error ({exc.sqlstate or type(exc).__name__}). Check credentials, connectivity and privileges.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
