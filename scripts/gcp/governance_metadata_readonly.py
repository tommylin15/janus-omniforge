#!/usr/bin/env python3
"""Bounded C0 governance metadata readback via an EXISTING dev Cloud Run Job.

GitHub Actions -> existing dev WIF -> existing ingestion-core Job override -> metadata-only
PostgreSQL read-only transactions and Iceberg *metadata* reads -> sanitized logs/artifact.
No Cloud Run template updates, deployments, schema changes or row-level private reads.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as gcp

REQUEST = Path("ops/governance-metadata-readonly-request.json")
OUTPUT = Path("governance-metadata-readonly-receipt.json")
JOB = "janus-ingestion-core"
PREFIX = "JANUS_GOVERNANCE_METADATA_RECEIPT_V1:"
SCHEMA_ALLOWLIST = ("audit", "catalog", "control", "private", "publication", "public")

# This is sent as bounded Python -c inside the existing dev Job; it is not deployed.
# Private schema is inspected through pg_catalog metadata ONLY, never table rows.
PROBE = r'''
import json, os
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from packages.postgres_bundle import load_postgres_bundle

PREFIX = "JANUS_GOVERNANCE_METADATA_RECEIPT_V1:"
STAMP = datetime.now(timezone.utc).isoformat()
SOURCE_SHA = os.environ.get("JANUS_GOVERNANCE_SOURCE_SHA", "UNKNOWN")
PROJECT = os.environ.get("GCP_PROJECT_ID", "UNKNOWN")
PREFIXES = ("catalog", "control", "publication", "audit", "private", "public")
OUT = {"component": "janus_governance_metadata_readonly_v1", "checked_at_utc": STAMP,
       "git_sha": SOURCE_SHA, "project": PROJECT, "environment": "dev",
       "read_only": True, "tables": {}, "errors": {}, "roles": {}}

def error_code(error):
    return {"error_class": type(error).__name__[:64],
            "sqlstate": str(getattr(error, "sqlstate", None) or "")[:5] or None}

def emit(section, data, status="PASS"):
    rows = data if isinstance(data, list) else [data]
    total = max(1, (len(rows) + 29) // 30)
    for i in range(total):
        item = {"component": OUT["component"], "checked_at_utc": STAMP,
                "git_sha": SOURCE_SHA, "project": PROJECT, "section": section,
                "status": status, "chunk": i + 1, "chunks": total,
                "items": rows[i * 30:(i + 1) * 30]}
        print(PREFIX + json.dumps(item, sort_keys=True, ensure_ascii=False, default=str), flush=True)

def connect_fields(layer):
    prefix = layer.upper()
    needed = ("HOST", "NAME", "USER", "PASSWORD")
    if any(not os.environ.get(prefix + "_DB_" + f) for f in needed):
        raise RuntimeError(layer.lower() + "_db_settings_unavailable")
    return dict(host=os.environ[prefix + "_DB_HOST"],
                dbname=os.environ[prefix + "_DB_NAME"],
                user=os.environ[prefix + "_DB_USER"],
                password=os.environ[prefix + "_DB_PASSWORD"],
                sslmode=os.environ.get(prefix + "_DB_SSLMODE", "require"),
                connect_timeout=5, autocommit=True, options="-cdefault_transaction_read_only=on")

def sql_section(conn, name, sql, max_rows, params=None):
    try:
        # Every statement is in an explicitly read-only, bounded transaction.
        conn.execute("BEGIN READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '10000ms'")
        rows = conn.execute(sql, params).fetchall()
        conn.execute("ROLLBACK")
        if len(rows) > max_rows:
            OUT["errors"][name] = {"error_class": "RESULT_LIMIT_EXCEEDED"}
            emit(name, [{"error_class": "RESULT_LIMIT_EXCEEDED"}], "BLOCKED")
            return
        result = [list(row) for row in rows]
        OUT["tables"][name] = result
        emit(name, result)
    except Exception as e:
        try: conn.execute("ROLLBACK")
        except Exception: pass
        OUT["errors"][name] = error_code(e)
        emit(name, [OUT["errors"][name]], "BLOCKED")

# Read settings using only the already configured ingestion dev identity/Secrets.
# No additional IAM grants, network ingress, or secret contents in output.
try:
    load_postgres_bundle("JANUS_INGESTION_POSTGRES_BUNDLE", {
        "CONTROL_DB_PASSWORD": ("ingestion_control_password", "control_password"),
        "CATALOG_DB_PASSWORD": ("ingestion_catalog_password", "catalog_password")})
except Exception as e:
    emit("configuration", [error_code(e)], "BLOCKED")
else:
    try:
        with psycopg.connect(**connect_fields("CATALOG")) as c:
            OUT["roles"]["catalog"] = c.info.user
            sql_section(c, "pg_relations", """
                SELECT n.nspname, cls.relname, cls.relkind
                  FROM pg_catalog.pg_class cls
                  JOIN pg_catalog.pg_namespace n ON n.oid=cls.relnamespace
                 WHERE n.nspname = ANY(%s)
                   AND cls.relkind IN ('r','p','v','m','f')
                 ORDER BY n.nspname,cls.relname LIMIT 501
            """, 500, (list(PREFIXES),))
            sql_section(c, "pg_columns", """
                SELECT n.nspname,cls.relname,a.attnum,a.attname,
                       pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull
                  FROM pg_catalog.pg_class cls
                  JOIN pg_catalog.pg_namespace n ON n.oid=cls.relnamespace
                  JOIN pg_catalog.pg_attribute a ON a.attrelid=cls.oid
                 WHERE n.nspname = ANY(%s)
                   AND cls.relkind IN ('r','p','v','m','f')
                   AND a.attnum > 0 AND NOT a.attisdropped
                 ORDER BY n.nspname,cls.relname,a.attnum LIMIT 3001
            """, 3000, (list(PREFIXES),))
            sql_section(c, "pg_constraints", """
                SELECT n.nspname,cls.relname,con.conname,con.contype,
                       CASE WHEN con.contype='f' THEN ref.relname ELSE NULL END
                  FROM pg_catalog.pg_constraint con
                  JOIN pg_catalog.pg_class cls ON cls.oid=con.conrelid
                  JOIN pg_catalog.pg_namespace n ON n.oid=cls.relnamespace
                  LEFT JOIN pg_catalog.pg_class ref ON ref.oid=con.confrelid
                 WHERE n.nspname = ANY(%s)
                 ORDER BY n.nspname,cls.relname,con.conname LIMIT 1001
            """, 1000, (list(PREFIXES),))
            sql_section(c, "pg_indexes", """
                SELECT n.nspname,cls.relname,idx.relname,
                       i.indisunique,i.indisprimary
                  FROM pg_catalog.pg_index i
                  JOIN pg_catalog.pg_class cls ON cls.oid=i.indrelid
                  JOIN pg_catalog.pg_class idx ON idx.oid=i.indexrelid
                  JOIN pg_catalog.pg_namespace n ON n.oid=cls.relnamespace
                 WHERE n.nspname = ANY(%s)
                 ORDER BY n.nspname,cls.relname,idx.relname LIMIT 1001
            """, 1000, (list(PREFIXES),))
            sql_section(c, "information_schema_tables", """
                SELECT table_schema,table_name,table_type
                  FROM information_schema.tables
                 WHERE table_schema = ANY(%s)
                 ORDER BY table_schema,table_name LIMIT 501
            """, 500, (list(PREFIXES),))
            sql_section(c, "information_schema_columns", """
                SELECT table_schema,table_name,ordinal_position,column_name,data_type
                  FROM information_schema.columns
                 WHERE table_schema = ANY(%s)
                 ORDER BY table_schema,table_name,ordinal_position LIMIT 2001
            """, 2000, (list(PREFIXES),))
            sql_section(c, "iceberg_catalog", """
                SELECT catalog_name,table_namespace,table_name,
                       metadata_location,previous_metadata_location
                  FROM catalog.iceberg_tables
                 WHERE catalog_name='janus'
                   AND table_namespace IN ('core','mart')
                 ORDER BY table_namespace,table_name LIMIT 201
            """, 200)
            sql_section(c, "mart_table_identifier_constraint", """
                SELECT con.conname,pg_catalog.pg_get_constraintdef(con.oid)
                  FROM pg_catalog.pg_constraint con
                  JOIN pg_catalog.pg_class cls ON cls.oid=con.conrelid
                  JOIN pg_catalog.pg_namespace n ON n.oid=cls.relnamespace
                 WHERE n.nspname='publication'
                   AND cls.relname='mart_report_index'
                   AND con.conname='mart_report_index_table_identifier_check'
                 LIMIT 2
            """, 1)
            # These are cumulative database stats, NOT a 30-day reader trace.
            sql_section(c, "publication_pg_scan_cumulative", """
                SELECT schemaname,relname,
                       COALESCE(seq_scan,0)::bigint,
                       COALESCE(idx_scan,0)::bigint
                  FROM pg_catalog.pg_stat_user_tables
                 WHERE schemaname='publication'
                   AND relname IN ('mart_report_index','mart_report_outbox')
                 ORDER BY relname LIMIT 3
            """, 2)
    except Exception as e:
        OUT["errors"]["catalog_connection"] = error_code(e)
        emit("catalog_connection", [error_code(e)], "BLOCKED")

    try:
        with psycopg.connect(**connect_fields("CONTROL")) as c:
            OUT["roles"]["control"] = c.info.user
            sql_section(c, "schema_migrations", """
                SELECT version FROM control.schema_migrations
                 ORDER BY version LIMIT 201
            """, 200)
            # Counts/status only: no requested_symbols, owner rows, UUIDs or
            # arbitrary JSON. requested_at is the occurrence event time.
            sql_section(c, "control_execution_30d", """
                SELECT trigger_type,status,count(*)::bigint,
                       max(requested_at)::text,max(finished_at)::text
                  FROM control.executions
                 WHERE requested_at>=now()-interval '30 days'
                 GROUP BY trigger_type,status
                 ORDER BY trigger_type,status LIMIT 41
            """, 40)
    except Exception as e:
        OUT["errors"]["control_connection"] = error_code(e)
        emit("control_connection", [error_code(e)], "BLOCKED")

    # PyIceberg load_table reads metadata JSON only: no table.scan / to_arrow /
    # data-file record reads, and no catalog create_namespace operation.
    try:
        from ingestion_core.__main__ import _iceberg_core
        core = _iceberg_core(os.environ["CORE_BUCKET"], read_only=True)
        try:
            records = OUT["tables"].get("iceberg_catalog")
            if records is None:
                emit("iceberg_snapshots", [{"error_class": "CATALOG_UNAVAILABLE"}], "BLOCKED")
            else:
                metadata = []
                for record in records:
                    _, namespace, table_name, location, _ = record
                    item = {"name": namespace + "." + table_name}
                    try:
                        table = core.catalog.load_table(item["name"])
                        snap = table.current_snapshot()
                        item.update(status="READABLE", schema=[
                            [f.name, str(f.field_type), f.required] for f in table.schema().fields],
                            partition_spec=[[f.name, str(f.transform)] for f in table.spec().fields],
                            snapshot_id=str(snap.snapshot_id) if snap else None,
                            row_count=int(snap.summary["total-records"])
                                if snap and snap.summary and "total-records" in snap.summary else None,
                            metadata_location=table.metadata_location)
                    except Exception as e:
                        item.update(status="UNKNOWN", error=error_code(e))
                    metadata.append(item)
                OUT["tables"]["iceberg_snapshots"] = metadata
                emit("iceberg_snapshots", metadata,
                     "PARTIAL" if any(x["status"] != "READABLE" for x in metadata) else "PASS")
        finally:
            core.close()
    except Exception as e:
        OUT["errors"]["iceberg_metadata"] = error_code(e)
        emit("iceberg_metadata", [error_code(e)], "BLOCKED")

# A successful job may still be PARTIAL; never silently convert missing sections
# to empty arrays or claim catalog table count zero after a failed query.
required = {"pg_relations","pg_columns","pg_constraints","pg_indexes",
            "information_schema_tables","information_schema_columns",
            "iceberg_catalog","schema_migrations","iceberg_snapshots"}
missing = sorted(required - set(OUT["tables"]))
status = "PASS" if not OUT["errors"] and not missing and all(
    x.get("status") == "READABLE" for x in OUT["tables"]["iceberg_snapshots"]
) else "PARTIAL"
emit("summary", [{"status": status, "missing": missing,
                  "errors": OUT["errors"], "roles": OUT["roles"],
                  "counts": {k: len(v) for k,v in OUT["tables"].items()},
                  "data_mutations": 0}], status)
'''

def override(job: dict, source_sha: str) -> dict:
    containers = job["template"]["template"]["containers"]
    if len(containers) != 1:
        raise ValueError("single_container_required")
    container = containers[0]
    command = container.get("command") or []
    if command not in ([], ["python"]):
        raise ValueError("readonly_entrypoint_drift")
    result = {
        "args": (["-c", PROBE] if command else ["python", "-c", PROBE]),
        "env": [{"name": "QUEUE_CONSUMER", "value": "false"},
                {"name": "JANUS_GOVERNANCE_SOURCE_SHA", "value": source_sha}],
    }
    if container.get("name"):
        result["name"] = container["name"]
    return result

def validate_request(req: dict) -> None:
    if req.get("intent") != "c0-live-readonly-governance-metadata" or (
        req.get("scope") != "existing-dev" or req.get("read_only") is not True
        or req.get("no_data_mutation") is not True
        or req.get("no_template_mutation") is not True
        or req.get("no_private_row_data") is not True
        or req.get("job") != JOB
    ):
        raise ValueError("readonly_governance_request_scope_invalid")

def main() -> None:
    req = json.loads(REQUEST.read_text(encoding="utf-8"))
    validate_request(req)
    source_sha = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("github_sha_missing")
    job = gcp.job(JOB)
    before = gcp.fingerprint(job)
    operation = gcp.cloud(gcp.ROOT + "/jobs/" + JOB + ":run", {
        "etag": job["etag"],
        "overrides": {"taskCount": 1, "timeout": "300s",
                      "containerOverrides": [override(job, source_sha)]}
    }, "POST")
    name = operation.get("name", "")
    if not name.startswith(gcp.ROOT + "/operations/"):
        raise RuntimeError("readonly_operation_identity_missing")
    deadline = time.monotonic() + 415
    while not operation.get("done") and time.monotonic() < deadline:
        time.sleep(7)
        operation = gcp.cloud(name)
    if not operation.get("done") or operation.get("error"):
        raise RuntimeError("readonly_operation_failed")
    execution = operation.get("response") or {}
    full_name = str(execution.get("name", ""))
    if not full_name.startswith(gcp.ROOT + "/jobs/" + JOB + "/executions/"):
        raise RuntimeError("readonly_execution_identity_missing")
    execution = gcp.cloud(full_name)
    if not gcp.terminal(execution) or execution.get("succeededCount") != 1 or execution.get("failedCount", 0):
        raise RuntimeError("readonly_execution_terminal_failed")
    execution_id = full_name.rsplit("/", 1)[-1]

    # Collect bounded log lines only for this execution. Credentials and SQL
    # errors are deliberately never extracted from raw runtime logs.
    selector = ('resource.type="cloud_run_job" AND '
                'labels."run.googleapis.com/execution_name"="' + execution_id + '"')
    records = []
    for attempt in range(7):
        raw = gcp.command(["gcloud", "logging", "read", selector,
                           "--project=" + gcp.PROJECT,
                           "--limit=300", "--format=json"])
        events = json.loads(raw)
        records = []
        for event in events:
            text = event.get("textPayload") or ""
            if PREFIX not in text:
                continue
            try:
                item = json.loads(text.split(PREFIX, 1)[1])
            except (ValueError, IndexError):
                continue
            if item.get("component") == "janus_governance_metadata_readonly_v1" and item.get("git_sha") == source_sha:
                records.append(item)
        if any(i.get("section") == "summary" for i in records):
            break
        time.sleep(5)
    if not any(i.get("section") == "summary" for i in records):
        raise RuntimeError("bounded_receipt_summary_unavailable")
    # Fail closed on lost/truncated chunks. No invented zero counts.
    sections = {}
    for item in records:
        sec = item["section"]
        sections.setdefault(sec, []).append(item)
    for section, chunks in sections.items():
        n = chunks[0]["chunks"]
        if len(chunks) != n or {c["chunk"] for c in chunks} != set(range(1, n + 1)):
            raise RuntimeError("bounded_receipt_chunks_missing_" + section)
    after = gcp.fingerprint(gcp.job(JOB))
    if before != after:
        raise RuntimeError("existing_job_configuration_drift")
    result = {
        "component": "janus_governance_metadata_readonly_v1",
        "source_git_sha": source_sha, "execution": execution_id,
        "job_configuration_unchanged": True, "data_mutations": 0,
        "sections": {k: {
            "status": chunks[0]["status"],
            "items": sum((c["items"] for c in sorted(chunks, key=lambda c: c["chunk"])), []),
        } for k, chunks in sections.items()}
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    for section, entry in result["sections"].items():
        # Summaries are intentionally compact. Full bounded metadata is in artifact.
        print(json.dumps({"section": section, "status": entry["status"],
                          "items": len(entry["items"]), "execution": execution_id},
                         sort_keys=True))
    # Print bounded metadata in provider logs as independent small chunks so the
    # GitHub plugin can retrieve individual tables/fields without artifact download.
    for item in sorted(records, key=lambda x: (x["section"], x["chunk"])):
        print(PREFIX + json.dumps(item, ensure_ascii=False, sort_keys=True))
    summary = result["sections"]["summary"]["items"][0]
    if summary.get("status") != "PASS":
        # Existing ingestion-core identity cannot read Mart GCS metadata. Accept
        # ONLY this known, scoped partial result when the companion Mart Job
        # probes the same registered namespace in the next workflow step.
        # Any other blocked section remains a hard failure.
        snapshots = result["sections"].get("iceberg_snapshots", {}).get("items", [])
        catalogue = result["sections"].get("iceberg_catalog", {}).get("items", [])
        expected_sections = {
            "pg_relations", "pg_columns", "pg_constraints", "pg_indexes",
            "information_schema_tables", "information_schema_columns",
            "iceberg_catalog", "schema_migrations"
        }
        section_ok = all(
            result["sections"].get(s, {}).get("status") == "PASS"
            for s in expected_sections
        )
        core = [x for x in snapshots if x.get("name", "").startswith("core.")]
        mart = [x for x in snapshots if x.get("name", "").startswith("mart.")]
        actual_catalog = sorted(str(row[1]) + "." + str(row[2]) for row in catalogue)
        actual_metadata = sorted(x.get("name", "") for x in snapshots)
        permitted_handoff = (
            summary.get("status") == "PARTIAL"
            and summary.get("missing") == [] and summary.get("errors") == {}
            and section_ok and len(core) == 9 and len(mart) == 11
            and len(catalogue) == 20 and actual_catalog == actual_metadata
            and all(x.get("status") == "READABLE" for x in core)
            and all(x.get("status") == "UNKNOWN"
                    and x.get("error", {}).get("error_class") == "PermissionError"
                    for x in mart)
        )
        if not permitted_handoff:
            raise RuntimeError("readonly_governance_metadata_partial")
        print("CORE_PG_PASS_MART_PERMISSION_HANDOFF_REQUIRED")

if __name__ == "__main__":
    main()
