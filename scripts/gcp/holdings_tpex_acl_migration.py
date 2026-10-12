#!/usr/bin/env python3
"""Apply exact versioned, additive owner TPEx EOD schema fix via existing dev ingestion Job.

The deployed ingress container already has janus_control credentials. Invoke it
with a one-off bounded Cloud Run v2 args override, never changing its permanent
template. No access token or database secret is accepted or emitted here.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import time

import ghcr_jobs_rollout as cloud

NAME = "053_tpex_owner_eod_quote_acl"
SOURCE = "0b0855c0fdeba0294bb0bb09bf33906216d779fa"
JOB = "janus-ingestion-core"
REQUEST = Path("ops/holdings-tpex-acl-migration.json")
SQL_PATH = Path("infra/postgres/migrations") / (NAME + ".sql")
EXPECTED_IMAGE = re.compile(r"^ghcr.io/tommylin15/janus-ingestion-core@sha256:[0-9a-f]{64}$")

# Runs only inside the existing, isolated ingress container with the existing
# janus_control DB identity; no user-supplied SQL or untrusted interpolation.
INSIDE = r"""
import base64,json
from ingestion_core.__main__ import _control_plane
from ingestion_core.serving_schema_migration import _without_role_lines
encoded = %r
raw = base64.b64decode(encoded, validate=True).decode('utf-8')
migration = '053_tpex_owner_eod_quote_acl'
if not raw.startswith('\\set ON_ERROR_STOP on') or raw.count('-- PHASE: acceptance')!=1:
    raise RuntimeError('unrecognized_versioned_tpex_migration')
prepare,acceptance=raw.split('-- PHASE: acceptance',1)
checks,marker=acceptance.split('INSERT INTO control.schema_migrations',1)
with_control = _control_plane()
try:
    with with_control.connection.transaction(), with_control.connection.cursor() as cursor:
        cursor.execute('SELECT current_user')
        if cursor.fetchone()[0]!='janus_control':
            raise RuntimeError('bounded_control_identity_required')
        cursor.execute('SELECT EXISTS(SELECT 1 FROM control.schema_migrations WHERE version=%%s)',(migration,))
        already=bool(cursor.fetchone()[0])
        if not already:
            cursor.execute(_without_role_lines(prepare))
        cursor.execute(_without_role_lines(checks))
        result=cursor.fetchone()
        if result is None or not all(v is True for v in result):
            raise RuntimeError('tpex_acl_or_quote_check_constraints_acceptance_failed')
        if not already:
            cursor.execute('INSERT INTO control.schema_migrations'+_without_role_lines(marker))
    print(json.dumps({'migration':migration,'result':'PASS','existing':already,
        'official_tpex_eod_constraint':True,
        'private_pipeline_table_scoped_acl':True,
        'public_quote_acl_denied':True,'no_private_ledger_mutation':True},sort_keys=True))
finally:
    with_control.close()
"""


def main() -> None:
    request=json.loads(REQUEST.read_text())
    if (request.get("intent")!="migrate-single-quote-table-tpex-eod"
            or request.get("approved") is not True
            or request.get("scope")!="control.operational_last_quotes-only"
            or request.get("source_sha")!=SOURCE
            or request.get("new_resources") is not False
            or request.get("ledger_mutation") is not False):
        raise ValueError("tpex_quote_acl_migration_not_approved")
    sql=SQL_PATH.read_bytes()
    # Fixed SQL contract, fail closed on any other schema/role changes.
    decoded=sql.decode("utf-8")
    must_have=[
        "SET ROLE janus_control",
        "GRANT SELECT, INSERT, UPDATE ON control.operational_last_quotes TO janus_private_pipeline",
        "CHECK (source IN ('twse_mis', 'tpex_openapi_eod'))",
        "CHECK (session IN ('regular', 'off_session', 'official_close'))",
        "053_tpex_owner_eod_quote_acl",
        "NOT has_table_privilege('janus_public_api'",
    ]
    if not all(part in decoded for part in must_have):
        raise ValueError("tpex_migration_sql_contract_drift")
    if any(token in decoded.upper() for token in (
        "DROP TABLE", "TRUNCATE", "DELETE FROM", "ALL TABLES", "GRANT ALL",
        "ALTER ROLE", "CREATE ROLE", "REVOKE CONNECT")):
        raise ValueError("unsafe_quote_acl_migration_sql")
    job=cloud.job(JOB)
    image=cloud.image(job)
    if not EXPECTED_IMAGE.fullmatch(image):
        raise RuntimeError("ingestion_runtime_immutable_image_not_verified")
    if len(job["template"]["template"]["containers"])!=1:
        raise RuntimeError("unbounded_ingestion_job_shape")
    container=job["template"]["template"]["containers"][0]
    # No migration execution if ingestion/controller is already running.
    for name in ("janus-ingestion-core", "janus-batch-controller"):
        runs=cloud.cloud(f"{cloud.ROOT}/jobs/{name}/executions?pageSize=20")
        if any(not cloud.terminal(e) for e in runs.get("executions",[])):
            raise RuntimeError("active_ingestion_execution_blocks_migration")
    encoded=base64.b64encode(sql).decode("ascii")
    source=INSIDE % encoded
    args=["-c",source]
    if not container.get("command"):
        args=["python"]+args
    elif container["command"]!=["python"]:
        raise RuntimeError("unexpected_ingestion_entrypoint")
    override={"args":args,"env":[]}
    if container.get("name"):
        override["name"]=container["name"]
    response=cloud.cloud(f"{cloud.ROOT}/jobs/{JOB}:run",{
        "etag":job["etag"],
        "overrides":{"taskCount":1,"timeout":"300s","containerOverrides":[override]}
    },"POST")
    name=response.get("name")
    if not isinstance(name,str) or not name.startswith(cloud.ROOT+"/operations/"):
        raise RuntimeError("migration_operation_not_created")
    deadline=time.monotonic()+440
    while not response.get("done") and time.monotonic()<deadline:
        time.sleep(7)
        response=cloud.cloud(name)
    if not response.get("done") or response.get("error"):
        raise RuntimeError("tpex_quote_acl_migration_failed_or_unknown")
    execution=response.get("response") or {}
    if (not cloud.terminal(execution) or execution.get("succeededCount")!=1
            or execution.get("failedCount",0)!=0):
        raise RuntimeError("tpex_quote_acl_migration_execution_not_successful")
    print(json.dumps({"migration":NAME,"status":"PASS",
        "execution":str(execution.get("name","")).split("/")[-1],
        "sql_sha256":hashlib.sha256(sql).hexdigest(),
        "expected_legacy_source":SOURCE,
        "table_scope":"control.operational_last_quotes",
        "other_gcp_or_owner_mutations":False},sort_keys=True))


if __name__=="__main__":
    main()
