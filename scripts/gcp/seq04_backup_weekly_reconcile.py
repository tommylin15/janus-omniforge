#!/usr/bin/env python3
"""One-shot SEQ-04 bounded Dev repair: archived first-week daily to weekly,
and a CAS reconcile of one verified completed backup occurrence.

No dump, owner write, scheduler/job changes, GCS delete or overwrite.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from uuid import NAMESPACE_URL, uuid5
import json
import os
import re
import shlex
import subprocess
import sys

PROJECT = "gen-lang-client-0593591102"
BUCKET = PROJECT + "-dev-private"
WEEK = "2026-10-19"
DAY = "2026-10-19"
OCC = "ledger-backup/2026-10-25/00"
CURRENT = "2026-10-25"
SOURCE = "pilot-ledger-backups/daily/" + DAY + ".dump"
TARGET = "pilot-ledger-backups/weekly/" + WEEK + ".dump"
ROOT = "https://storage.googleapis.com"
OUT = Path("seq04-backup-weekly-reconcile-receipt.json")


def guard():
    x = json.loads(Path("ops/seq04-backup-weekly-reconcile-request.json").read_text())
    assert x == {
        "intent": "seq04-dev-existing-weekly-backfill-and-occurrence-cas",
        "approved": True, "project": PROJECT, "week": WEEK, "source_day": DAY,
        "occurrence_id": OCC, "backup_date": CURRENT,
        "if_generation_match_zero": True, "max_weekly_objects_created": 1,
        "max_source_bytes": 67_108_864,
        "no_backup_execution": True, "no_scheduler_or_job_changes": True,
        "no_owner_mutation": True, "no_gcs_deletion": True,
        "no_new_resources": True, "attempt": 1,
    }


def gcloud_sql(statement: str, *, timeout: int = 115) -> list[str]:
    remote = (
        "sudo docker exec --user postgres janus-postgres "
        "psql -X -qAt -v ON_ERROR_STOP=1 -d janus_control -c "
        + shlex.quote(statement)
    )
    command = ["gcloud", "compute", "ssh", "janus-postgres-dev",
               "--project=" + PROJECT, "--zone=us-central1-a",
               "--tunnel-through-iap", "--quiet", "--command=" + remote]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("VM_PG_QUERY_OR_CAS_UNAVAILABLE")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def quote_sql(value):
    return "'" + str(value).replace("'", "''") + "'"


def pg_backup(day: str) -> dict:
    sql = ("SELECT row_to_json(z)::text FROM (SELECT backup_date::text AS day, status,"
           " retention_status, size_bytes, sha256, completed_at::text AS completed"
           " FROM control.ledger_backup_requests WHERE backup_date=" + quote_sql(day) + "::date) z")
    data = [json.loads(x) for x in gcloud_sql(sql) if x.startswith("{")]
    if len(data) != 1:
        raise RuntimeError("BACKUP_REQUEST_MISSING_OR_AMBIGUOUS")
    row = data[0]
    if (row["status"] != "succeeded" or not isinstance(row["size_bytes"], int)
            or not 1024 <= row["size_bytes"] <= 67_108_864
            or not re.fullmatch(r"[a-f0-9]{64}", row.get("sha256") or "")
            or not row["completed"]):
        raise RuntimeError("BACKUP_RECEIPT_NOT_COMPLETE")
    return row


def pg_occurrence() -> dict:
    sql = ("SELECT row_to_json(z)::text FROM (SELECT occurrence_id,scheduled_at::text AS scheduled,"
           " state FROM control.batch_occurrences WHERE occurrence_id=" + quote_sql(OCC) + ") z")
    data = [json.loads(x) for x in gcloud_sql(sql) if x.startswith("{")]
    if len(data) != 1:
        raise RuntimeError("OCCURRENCE_MISSING_OR_AMBIGUOUS")
    row = data[0]
    state = row.get("state") or {}
    if (row["occurrence_id"] != OCC or state.get("batch") != "ledger-backup"
            or state.get("backup_date") != CURRENT or
            state.get("status") not in ("running", "succeeded") or
            not str(row["scheduled"]).startswith("2026-10-24 16:30:00")):
        raise RuntimeError("OCCURRENCE_IDENTITY_OR_STATE_DRIFT")
    return row


def token() -> str:
    result = subprocess.run(["gcloud", "auth", "print-access-token"],
                            capture_output=True, text=True, timeout=35)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("EXISTING_WIF_TOKEN_UNAVAILABLE")
    return result.stdout.strip()


def call(auth: str, url: str, *, method="GET"):
    try:
        with urlopen(Request(url, headers={"Authorization": "Bearer " + auth},
                             method=method), timeout=90) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError("GCS_HTTP_" + str(error.code)) from None
    except (URLError, TimeoutError):
        raise RuntimeError("GCS_TRANSPORT_UNAVAILABLE") from None


def meta(auth: str, name: str) -> dict | None:
    url = ROOT + "/storage/v1/b/" + quote(BUCKET, safe="") + "/o/" + quote(name, safe="")
    return call(auth, url)


def digest(auth: str, name: str, max_size: int) -> tuple[int, str]:
    url = ROOT + "/download/storage/v1/b/" + quote(BUCKET, safe="") + "/o/" + quote(name, safe="") + "?alt=media"
    h = sha256()
    length = 0
    try:
        with urlopen(Request(url, headers={"Authorization": "Bearer " + auth}), timeout=100) as response:
            while True:
                chunk = response.read(1024*1024)
                if not chunk:
                    break
                length += len(chunk)
                if length > max_size:
                    raise RuntimeError("SOURCE_TOO_LARGE")
                h.update(chunk)
    except HTTPError as error:
        raise RuntimeError("BACKUP_DOWNLOAD_HTTP_" + str(error.code)) from None
    return length, h.hexdigest()


def weekly(auth: str, receipt: dict) -> dict:
    request = pg_backup(DAY)
    obj = meta(auth, SOURCE)
    if obj is None:
        raise RuntimeError("SOURCE_DAILY_OBJECT_MISSING")
    if int(obj.get("size") or 0) != request["size_bytes"]:
        raise RuntimeError("SOURCE_DAILY_SIZE_MISMATCH")
    generation = str(obj.get("generation") or "")
    if not generation.isdigit():
        raise RuntimeError("SOURCE_GENERATION_MISSING")
    size, checksum = digest(auth, SOURCE, 67_108_864)
    if size != request["size_bytes"] or checksum != request["sha256"]:
        raise RuntimeError("SOURCE_DAILY_SHA256_MISMATCH")
    dest = meta(auth, TARGET)
    created = False
    if dest is None:
        url = (ROOT + "/storage/v1/b/" + quote(BUCKET,safe="") + "/o/" +
               quote(SOURCE,safe="") + "/rewriteTo/b/" + quote(BUCKET,safe="") +
               "/o/" + quote(TARGET,safe=""))
        query = {"ifGenerationMatch": "0", "ifSourceGenerationMatch": generation}
        for _ in range(8):
            result = call(auth, url + "?" + urlencode(query), method="POST")
            if result is None:
                raise RuntimeError("GCS_REWRITE_UNEXPECTED_NOT_FOUND")
            if result.get("done"):
                created = True
                break
            rewrite_token = result.get("rewriteToken")
            if not rewrite_token:
                raise RuntimeError("GCS_REWRITE_TOKEN_MISSING")
            query["rewriteToken"] = rewrite_token
        if not created:
            raise RuntimeError("GCS_REWRITE_NOT_TERMINAL")
        dest = meta(auth, TARGET)
    if dest is None or int(dest.get("size") or 0) != size:
        raise RuntimeError("WEEKLY_OBJECT_READBACK_MISMATCH")
    after_size, after_hash = digest(auth, TARGET, 67_108_864)
    if (after_size, after_hash) != (size, checksum):
        raise RuntimeError("WEEKLY_SHA256_READBACK_MISMATCH")
    result = {"status":"PASS", "week_key":WEEK, "source_day":DAY,
              "created":created, "weekly_objects_created":int(created),
              "bytes":after_size, "sha256_verified":True,
              "source_generation_fenced":True, "destination_generation":str(dest.get("generation",""))}
    receipt["weekly"] = result
    return result


def reconcile(receipt: dict):
    row = pg_occurrence()
    backup = pg_backup(CURRENT)
    if backup["retention_status"] != "succeeded":
        raise RuntimeError("RETENTION_STATUS_NOT_SUCCEEDED")
    old = row["state"]
    if old["status"] == "succeeded":
        result={"status":"PASS_ALREADY_RECONCILED","state":"succeeded",
                "occurrence_id":OCC,"backup_day":CURRENT,"cas_updates":0}
        receipt["occurrence"] = result
        return result
    state = {**old, "status":"succeeded", "backup_status":"succeeded",
             "reason":"backup_retention_succeeded",
             "size_bytes":backup["size_bytes"], "sha256":backup["sha256"],
             "completion_time":backup["completed"],
             "retention_cleanup":{"status":"succeeded","executor":"existing_postgres_vm"}}
    tick = datetime.now(timezone.utc).replace(second=0,microsecond=0)
    tick = tick.replace(minute=tick.minute//10*10).isoformat()
    payload = {"schema_version":"batch-event-v1","tick":tick, "occurrence_id":OCC,
               "action":"reconcile", "controller_execution":"seq04-20261025-bounded-cas",
               **state}
    state_hash = sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()
    event = str(uuid5(NAMESPACE_URL,f"janus-batch-v1/{tick}/{OCC}/reconcile/{state_hash}"))
    old_sql = quote_sql(json.dumps(old, sort_keys=True))
    new_sql = quote_sql(json.dumps(state,sort_keys=True))
    payload_sql = quote_sql(json.dumps(payload,sort_keys=True))
    sql = f"""
    BEGIN;
    SET LOCAL lock_timeout = '5s';
    SELECT pg_advisory_xact_lock(1835102836,3);
    WITH upd AS (
       UPDATE control.batch_occurrences o
          SET state={new_sql}::jsonb,updated_at=now()
        WHERE o.occurrence_id={quote_sql(OCC)} AND o.state={old_sql}::jsonb
          AND o.state->>'status'='running'
          AND o.state->>'batch'='ledger-backup'
          AND o.state->>'backup_date'={quote_sql(CURRENT)}
          AND o.scheduled_at='2026-10-24T16:30:00Z'::timestamptz
          AND EXISTS (
            SELECT 1 FROM control.ledger_backup_requests b
            WHERE b.backup_date={quote_sql(CURRENT)}::date
              AND b.status='succeeded' AND b.retention_status='succeeded'
              AND b.size_bytes={backup['size_bytes']}
              AND b.sha256={quote_sql(backup['sha256'])}
              AND b.completed_at IS NOT NULL
          )
        RETURNING o.occurrence_id
    ), evt AS (
       INSERT INTO control.batch_event_outbox(event_id,payload)
       SELECT {quote_sql(event)}::uuid,{payload_sql}::jsonb FROM upd
       ON CONFLICT DO NOTHING RETURNING event_id
    )
    SELECT 'SEQ04_CAS|' || (SELECT count(*) FROM upd) || '|' || (SELECT count(*) FROM evt);
    COMMIT;
    """
    lines = gcloud_sql(sql)
    result_line = [x for x in lines if x.startswith("SEQ04_CAS|")]
    after = pg_occurrence()
    if after["state"].get("status") != "succeeded":
        raise RuntimeError("OCCURRENCE_CAS_READBACK_FAILED")
    if result_line != ["SEQ04_CAS|1|1"]:
        raise RuntimeError("OCCURRENCE_CAS_NOT_SINGLE_WRITE")
    result={"status":"PASS", "occurrence_id":OCC, "backup_day":CURRENT,
            "backup_sha_verified":True,"retention_status":"succeeded",
            "cas_updates":1,"outbox_events":1, "readback_status":"succeeded"}
    receipt["occurrence"] = result
    return result


def main():
    guard()
    receipt={"component":"seq04-weekly-and-occurrence-reconcile","project":PROJECT,
             "observed_utc":datetime.now(timezone.utc).isoformat(),
             "weekly":{"status":"NOT_ATTEMPTED"},"occurrence":{"status":"NOT_ATTEMPTED"},
             "new_gcp_resources":0,"new_scheduler":0,"new_job":0,
             "backup_executions":0,"deleted_objects":0}
    try:
        weekly(token(), receipt)
        print("SEQ04_WEEKLY_RECEIPT="+json.dumps(receipt["weekly"],sort_keys=True),flush=True)
    except Exception as error:
        receipt["weekly"]={"status":"BLOCKED","error_class":type(error).__name__,
                           "error_code":str(error)[:100] if isinstance(error,RuntimeError) else "UNEXPECTED"}
    try:
        reconcile(receipt)
        print("SEQ04_OCCURRENCE_RECEIPT="+json.dumps(receipt["occurrence"],sort_keys=True),flush=True)
    except Exception as error:
        receipt["occurrence"]={"status":"BLOCKED","error_class":type(error).__name__,
                               "error_code":str(error)[:100] if isinstance(error,RuntimeError) else "UNEXPECTED"}
    OUT.write_text(json.dumps(receipt,sort_keys=True,indent=2,ensure_ascii=False)+"\n")
    print("SEQ04_BACKUP_REPAIR_FINAL="+json.dumps(receipt,sort_keys=True,ensure_ascii=False),flush=True)
    if receipt["weekly"]["status"]!="PASS" or not receipt["occurrence"]["status"].startswith("PASS"):
        raise SystemExit(1)

if __name__=="__main__":
    main()
