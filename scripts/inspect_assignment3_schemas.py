#!/usr/bin/env python3
"""Read-only catalog audit for Assignment 3, including unexpectedly named tables.

No student rows, defaults, views, or triggers are executed. No automatic grading
or name-map changes. Uses the same psycopg/connection setup as check_assignment3.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from difflib import SequenceMatcher
import html
import json
import os
from pathlib import Path
import re
import sys
import tomllib

import psycopg
from psycopg.rows import dict_row

from check_assignment3 import FIELDS, db_error, read_name_map, read_schema_file, validate_name_map


NOTE = (
    "Catalog evidence only; no student rows or behavioral tests. Suggestions are "
    "candidates for human review, not confirmed equivalents or grade deductions. "
    "No mappings are applied to the database or checker configuration. Tables owned "
    "by the selected schema's same-named role in other non-system schemas are also "
    "included; this cannot locate tables owned by other roles. Compare constraints, "
    "written work and behavioral results before deciding credit."
)


def normalized(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def similar(expected, actual):
    a, b = normalized(expected), normalized(actual)
    if a == b:
        return True
    return (expected == "contact_email" and b == "email") or SequenceMatcher(None, a, b).ratio() >= .78


def review_findings(result):
    """Suggest candidates without choosing ambiguous or many-to-one mappings."""
    findings = []

    def add(kind, message, **evidence):
        findings.append({"kind": kind, "message": message, **evidence})

    relations = result["relations"]
    assigned = {r["name"]: r for r in relations if r["schema"] == result["schema"]}
    mapping = result["name_map"]
    table_targets = {t: mapping["tables"].get(t, t) for t in FIELDS}
    if not result.get("schema_info"):
        add("location", "Assigned schema is absent; inspect any student-owned tables found elsewhere.")
    elif not result["schema_info"]["usage"]:
        add("access", "Current account lacks USAGE on the assigned schema.")
    for logical, expected_fields in FIELDS.items():
        target = table_targets[logical]
        rel = assigned.get(target)
        if logical != target and logical in assigned:
            add("mapping", "Both the expected table and mapped table name exist; checker mapping is ambiguous.",
                table=logical, mapped=target)
        if not rel:
            candidates = []
            for candidate in relations:
                # Do not repurpose a distinct required table or a confirmed target.
                if candidate["schema"] == result["schema"] and candidate["name"] in table_targets.values():
                    continue
                names = {c["name"] for c in candidate["columns"]}
                overlap = [f for f in expected_fields if any(similar(f, n) for n in names)]
                if similar(logical, candidate["name"]) or len(overlap) >= (len(expected_fields) + 1) // 2:
                    candidates.append({"schema": candidate["schema"], "table": candidate["name"],
                                       "similar_fields": overlap, "kind": candidate["kind"]})
            add("table_candidates", "Expected/mapped table is absent. Candidate names require manual confirmation; "
                "cross-schema tables cannot be fixed by the checker's within-schema name map.",
                table=logical, expected_actual_name=target, candidates=candidates)
            continue
        if logical != target:
            add("mapped_name", "Existing explicit table mapping; naming requirement remains a separate finding.",
                table=logical, actual=target)
        actual = {c["name"]: c for c in rel["columns"]}
        field_targets = {f: mapping["columns"].get(logical, {}).get(f, f) for f in expected_fields}
        candidates_by_field = {}
        for field, actual_name in field_targets.items():
            if field != actual_name and field in actual:
                add("mapping", "Expected and mapped column both exist; checker mapping is ambiguous.",
                    table=target, field=field, mapped=actual_name)
            if actual_name not in actual:
                candidates = [n for n in actual if n not in field_targets.values()
                              and n not in expected_fields and similar(field, n)]
                candidates_by_field[field] = candidates
            elif field != actual_name:
                add("mapped_name", "Existing explicit column mapping; inspect behavior separately.",
                    table=target, field=field, actual=actual_name)
        for field, candidates in candidates_by_field.items():
            shared = [n for n in candidates if sum(n in v for v in candidates_by_field.values()) > 1]
            add("column_candidates", "Required field absent under expected/mapped name. Suggestions are not automatically applied.",
                table=target, field=field, candidates=candidates, shared_candidates=shared)
        if rel["kind"] != "r" or rel["persistence"] != "p":
            add("representation", "Relation is not an ordinary permanent table; inspect checker compatibility.",
                table=target, kind=rel["kind"], persistence=rel["persistence"])
        if not rel["schema_usage"] or not all(rel[k] for k in ("can_select", "can_insert", "can_update", "can_delete")):
            add("access", "Schema/table privileges may prevent instructor probes; this alone is not a student rule failure.", table=target)
        if rel["row_security"] or rel["triggers"] or rel["rules"] or rel["parents"] or rel["is_partition"]:
            add("behavior_review", "RLS, user triggers, rules or inheritance need individual review before behavioral testing.", table=target)
        pk = [c for c in rel["constraints"] if c["type"] == "p"]
        id_field = expected_fields[0]
        key = actual.get(field_targets[id_field])
        if not pk:
            add("key_design", "No declared primary key. Unique/non-null alternatives and referenced keys require design review.", table=target)
        elif key and not any(c["columns"] == [key["name"]] for c in pk):
            add("key_design", "Declared primary key differs from the expected single ID field.", table=target, expected_id=key["name"])
        if key and not key["identity"] and not key["default"]:
            add("key_design", "ID has no column identity/default; inspect domain defaults and triggers before deciding whether IDs are generated.", table=target, column=key["name"])
        for field in ("is_active", "starts_at", "ends_at", "total_price"):
            col = actual.get(field_targets.get(field))
            if not col:
                continue
            base = col["type_chain"][-1]
            builtin = base["schema"] == "pg_catalog"
            expected_types = {"is_active": {"bool"}, "starts_at": {"timestamp", "timestamptz"},
                              "ends_at": {"timestamp", "timestamptz"}, "total_price": {"numeric"}}[field]
            if not builtin or base["name"] not in expected_types:
                add("representation", "Type differs from the checker's usual representation. Review meaning and allowed values; a fixture failure does not prove the corresponding rule is missing.",
                    table=target, field=field, actual_type=col["type"])
    for rel in relations:
        if rel["schema"] != result["schema"]:
            add("location", "Student-role-owned relation outside the assigned schema; verify relevance to this assignment.",
                schema=rel["schema"], table=rel["name"])
    return findings


def type_chain(conn, oid, cache):
    if oid in cache:
        return cache[oid]
    typ = conn.execute("""SELECT t.oid, n.nspname AS schema, t.typname AS name,
        t.typtype AS kind, t.typbasetype AS base_oid, t.typnotnull AS not_null,
        t.typdefault AS default, t.typtypmod AS base_type_modifier,
        CASE WHEN t.typbasetype <> 0 THEN format_type(t.typbasetype,t.typtypmod) END AS base_type
        FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE t.oid=%s""", (oid,)).fetchone()
    typ["enum_values"] = [r["enumlabel"] for r in conn.execute(
        "SELECT enumlabel FROM pg_enum WHERE enumtypid=%s ORDER BY enumsortorder", (oid,))]
    typ["domain_constraints"] = conn.execute("""SELECT conname AS name, pg_get_constraintdef(oid,true) AS definition,
        convalidated AS validated FROM pg_constraint WHERE contypid=%s ORDER BY conname""", (oid,)).fetchall()
    chain = [typ] + (type_chain(conn, typ["base_oid"], cache) if typ["base_oid"] else [])
    cache[oid] = chain
    return chain


def inspect_schema(conn, schema, student="", name_map=None, timeout_ms=10000):
    result = {"schema": schema, "student": student, "name_map": validate_name_map(name_map or {}),
              "schema_info": None, "relations": [], "sequences": [], "findings": [], "errors": [], "complete": False}
    try:
        with conn.transaction(force_rollback=True):
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SELECT set_config('search_path','pg_catalog',true)")
            conn.execute("SELECT set_config('statement_timeout',%s,true)", (str(timeout_ms),))
            conn.execute("SELECT set_config('lock_timeout','2000',true)")
            result["connection"] = conn.execute("SELECT current_user AS role, current_database() AS database, "
                                                "current_setting('server_version') AS server_version").fetchone()
            result["schema_info"] = conn.execute("""SELECT nspname AS name, pg_get_userbyid(nspowner) AS owner,
                has_schema_privilege(oid,'USAGE') AS usage FROM pg_namespace WHERE nspname=%s""", (schema,)).fetchone()
            relations = conn.execute("""SELECT c.oid, n.nspname AS schema, c.relname AS name,
                c.relkind AS kind, c.relpersistence AS persistence, pg_get_userbyid(c.relowner) AS owner,
                c.relrowsecurity AS row_security, c.relforcerowsecurity AS force_row_security,
                c.relispartition AS is_partition, has_schema_privilege(n.oid,'USAGE') AS schema_usage,
                has_table_privilege(c.oid,'SELECT') AS can_select, has_table_privilege(c.oid,'INSERT') AS can_insert,
                has_table_privilege(c.oid,'UPDATE') AS can_update, has_table_privilege(c.oid,'DELETE') AS can_delete,
                CASE WHEN c.relkind IN ('v','m') THEN pg_get_viewdef(c.oid,true) END AS view_definition
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE c.relkind IN ('r','p','v','m','f') AND (n.nspname=%s OR
                  (pg_get_userbyid(c.relowner)=%s AND n.nspname NOT LIKE 'pg_%%' AND n.nspname<>'information_schema'))
                ORDER BY n.nspname,c.relname""", (schema, schema)).fetchall()
            cache = {}
            for rel in relations:
                oid = rel["oid"]
                rel["columns"] = conn.execute("""SELECT a.attnum AS position, a.attname AS name,
                    format_type(a.atttypid,a.atttypmod) AS type, a.atttypid AS type_oid,
                    a.attnotnull AS not_null, a.attidentity AS identity, a.attgenerated AS generated,
                    pg_get_expr(d.adbin,d.adrelid,true) AS default,
                    CASE WHEN a.attcollation<>0 THEN a.attcollation::regcollation::text END AS collation
                    FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                    WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""", (oid,)).fetchall()
                for col in rel["columns"]:
                    col["type_chain"] = type_chain(conn, col["type_oid"], cache)
                rel["constraints"] = conn.execute("""SELECT con.conname AS name, con.contype AS type,
                    pg_get_constraintdef(con.oid,true) AS definition, con.convalidated AS validated,
                    con.condeferrable AS deferrable, con.condeferred AS initially_deferred,
                    ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(num,ord)
                        JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=k.num ORDER BY k.ord) AS columns,
                    rn.nspname AS referenced_schema, rc.relname AS referenced_table,
                    ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY k(num,ord)
                        JOIN pg_attribute a ON a.attrelid=con.confrelid AND a.attnum=k.num ORDER BY k.ord) AS referenced_columns,
                    con.confdeltype AS delete_action, con.confupdtype AS update_action
                    FROM pg_constraint con LEFT JOIN pg_class rc ON rc.oid=con.confrelid
                    LEFT JOIN pg_namespace rn ON rn.oid=rc.relnamespace
                    WHERE con.conrelid=%s ORDER BY con.conname""", (oid,)).fetchall()
                rel["indexes"] = conn.execute("""SELECT c.relname AS name, i.indisunique AS unique,
                    i.indisprimary AS primary, i.indisvalid AS valid, pg_get_indexdef(i.indexrelid) AS definition
                    FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE i.indrelid=%s ORDER BY c.relname""", (oid,)).fetchall()
                rel["triggers"] = conn.execute("""SELECT tgname AS name,tgenabled AS enabled,
                    pg_get_triggerdef(oid,true) AS definition FROM pg_trigger
                    WHERE tgrelid=%s AND NOT tgisinternal ORDER BY tgname""", (oid,)).fetchall()
                rel["rules"] = conn.execute("""SELECT rulename AS name,ev_enabled AS enabled,
                    pg_get_ruledef(oid,true) AS definition FROM pg_rewrite
                    WHERE ev_class=%s AND rulename<>'_RETURN' ORDER BY rulename""", (oid,)).fetchall()
                rel["policies"] = conn.execute("""SELECT polname AS name,polcmd AS command,polpermissive AS permissive,
                    ARRAY(SELECT CASE WHEN x=0 THEN 'public' ELSE pg_get_userbyid(x) END FROM unnest(polroles) x) AS roles,
                    pg_get_expr(polqual,polrelid,true) AS using_expression,
                    pg_get_expr(polwithcheck,polrelid,true) AS check_expression
                    FROM pg_policy WHERE polrelid=%s ORDER BY polname""", (oid,)).fetchall()
                rel["parents"] = conn.execute("""SELECT n.nspname AS schema,c.relname AS name
                    FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhparent
                    JOIN pg_namespace n ON n.oid=c.relnamespace WHERE i.inhrelid=%s ORDER BY i.inhseqno""", (oid,)).fetchall()
                result["relations"].append(rel)
            # Catalog parameters and dependencies only: do not read sequence state.
            result["sequences"] = conn.execute("""SELECT n.nspname AS schema,c.relname AS name,
                pg_get_userbyid(c.relowner) AS owner, format_type(s.seqtypid,NULL) AS type,
                s.seqstart AS start,s.seqincrement AS increment,s.seqmin AS minimum,s.seqmax AS maximum,
                s.seqcycle AS cycle,has_sequence_privilege(c.oid,'USAGE') AS can_use,
                has_sequence_privilege(c.oid,'SELECT') AS can_select,has_sequence_privilege(c.oid,'UPDATE') AS can_update,
                tn.nspname AS owning_schema,tc.relname AS owning_table,a.attname AS owning_column
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                JOIN pg_sequence s ON s.seqrelid=c.oid
                LEFT JOIN pg_depend d ON d.classid='pg_class'::regclass AND d.objid=c.oid
                    AND d.refclassid='pg_class'::regclass AND d.deptype IN ('a','i')
                LEFT JOIN pg_class tc ON tc.oid=d.refobjid
                LEFT JOIN pg_namespace tn ON tn.oid=tc.relnamespace
                LEFT JOIN pg_attribute a ON a.attrelid=tc.oid AND a.attnum=d.refobjsubid
                WHERE n.nspname=%s OR (pg_get_userbyid(c.relowner)=%s
                    AND n.nspname NOT LIKE 'pg_%%' AND n.nspname<>'information_schema')
                ORDER BY n.nspname,c.relname""", (schema, schema)).fetchall()
            result["complete"] = True
    except psycopg.Error as exc:
        result["errors"].append(db_error(exc))
    if result["complete"]:
        result["findings"] = review_findings(result)
    return result


def write_reports(directory, results):
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    payload = {"created_utc": datetime.now(timezone.utc).isoformat(), "mode": "read-only catalog audit",
               "note": NOTE, "schemas": results}
    esc = lambda x: html.escape(str(x))
    sections, summary = [], ["Assignment 3 schema audit", NOTE, ""]
    for r in results:
        title = f"{r['student'] or r['schema']} — {r['schema']}"
        state = "Complete" if r["complete"] else "INCOMPLETE — execution error; do not infer missing requirements"
        evidence = json.dumps(r, indent=2, ensure_ascii=False, default=str)
        finding_text = json.dumps(r["findings"], indent=2, ensure_ascii=False)
        summary.extend([title, state, f"{len(r['relations'])} relations; {len(r['findings'])} review notes",
                        finding_text, json.dumps(r["errors"], default=str) if r["errors"] else "", ""])
        sections.append(f'<section><h2>{esc(title)}</h2><p>{esc(state)} · {len(r["relations"])} relations</p>'
                        f'<h3>Review notes</h3><pre>{esc(finding_text)}</pre>'
                        f'<details><summary>Full catalog evidence</summary><pre>{esc(evidence)}</pre></details></section>')
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Assignment 3 schema audit</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#f4f7fa;color:#162b3c}section{background:white;padding:1.2rem;margin:1rem 0;border:1px solid #ccd7df;border-radius:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}summary{cursor:pointer}input{padding:.7rem;width:min(35rem,90%)}</style>
<h1>Assignment 3 schema audit</h1><p>''' + esc(payload["created_utc"]) + "</p><p>" + esc(NOTE) + '''</p>
<label>Search students, names or evidence <input type="search" id="search"></label>''' + "".join(sections) + '''
<script>document.getElementById('search').addEventListener('input',e=>{for(const s of document.querySelectorAll('section'))s.hidden=!s.textContent.toLowerCase().includes(e.target.value.toLowerCase())})</script></html>'''
    for name, content in {"schema-audit.json": json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
                          "report.html": document, "summary.txt": "\n".join(summary)}.items():
        # Private from creation, including when called outside main().
        with open(directory / name, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
            stream.write(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--schema", action="append", help="Exact schema; repeat to select several")
    source.add_argument("--schema-file", type=Path, help="Same private roster/manifest accepted by checker")
    connection = parser.add_mutually_exclusive_group()
    connection.add_argument("--config", type=Path, help="Provisioning TOML: host/port/name/sslmode only; PGUSER selects account")
    connection.add_argument("--service", help="libpq service; otherwise use PG environment variables")
    parser.add_argument("--name-map", type=Path, help="Existing confirmed mappings, for interpretation only")
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--output", type=Path, default=Path("instructor-solutions") /
                        ("assignment3-schema-audit-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
    args = parser.parse_args(argv)
    if args.timeout_ms < 1 or args.output.exists():
        parser.error("Timeout must be positive; output must be a new directory.")
    os.umask(0o077)
    try:
        schemas = read_schema_file(args.schema_file) if args.schema_file else [(s, "") for s in dict.fromkeys(args.schema)]
        if not schemas or any(not s or "\x00" in s for s, _ in schemas):
            raise ValueError("Select at least one valid nonempty schema.")
        maps = read_name_map(args.name_map) if args.name_map else {}
        kwargs = {"service": args.service} if args.service else {}
        if args.config:
            with args.config.open("rb") as stream:
                db = tomllib.load(stream).get("database", {})
            if not db.get("host") or not db.get("name"):
                raise ValueError("Connection config requires [database] host and name.")
            kwargs = {"host": db["host"], "dbname": db["name"], "port": db.get("port", 5432),
                      "sslmode": db.get("sslmode", "require")}
        results = []
        with psycopg.connect(autocommit=True, row_factory=dict_row, connect_timeout=10, **kwargs) as conn:
            for i, (schema, student) in enumerate(schemas, 1):
                r = inspect_schema(conn, schema, student, maps.get(schema), args.timeout_ms)
                results.append(r)
                print(f"[{i}/{len(schemas)}] {schema}: {len(r['relations'])} relations; "
                      f"{len(r['findings'])} review notes; {'complete' if r['complete'] else 'ERROR'}", flush=True)
        write_reports(args.output, results)
        print(f"Report: {args.output.resolve() / 'report.html'}")
        print(f"Analysis evidence: {args.output.resolve() / 'schema-audit.json'}")
        return 2 if any(r["errors"] for r in results) else 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except psycopg.Error as exc:
        print(f"Database connection/execution error ({exc.sqlstate or type(exc).__name__}). Check connection and privileges.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
