#!/usr/bin/env python3
"""One-time dev Controller-only pinned-image rollout and six receipt-gated repairs.

No VM backup execution, GCS read/delete, extra Job, IAM grant, API deployment,
Owner data or unscoped UPDATE. The old digest is a required rollback source.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as gcp

REQUEST = Path("ops/controller-ledger-repair-request.json")
OUTPUT = Path("/tmp/controller-ledger-repair-receipt.json")
JOB = "janus-batch-controller"
COMPONENT = "ingestion-core"
SOURCE_SHA = "0e5e8a680ebf02c534a42438ee744ff2c63f1c21"
RELEASE_RUN = "39967114806"
BACKUP_DAYS = tuple("2026-10-" + str(d).zfill(2) for d in range(18, 24))
PREFIX = "JANUS_CONTROLLER_LEDGER_REPAIR_V1:"

# Runs inside the *new* Controller image on the EXISTING job using one-time
# overrides. Existing worker identity/secret attachments are left untouched.
# Only the six allowlisted receipts may change from running to succeeded.
PROBE = r'''
import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid5, NAMESPACE_URL
from ingestion_core.__main__ import _control_plane
from ingestion_core.ledger_backup import poll_backup

PREFIX = "JANUS_CONTROLLER_LEDGER_REPAIR_V1:"
DAYS = tuple("2026-10-" + str(d).zfill(2) for d in range(18, 24))
sha = os.environ.get("JANUS_CONTROLLER_LEDGER_REPAIR_SHA")
if sha != "0e5e8a680ebf02c534a42438ee744ff2c63f1c21":
    raise RuntimeError("repair_source_identity_missing")
control = _control_plane()
connection = control.connection
got_lock = False
try:
    got_lock = bool(connection.execute(
        "SELECT pg_try_advisory_lock(1835102836,3)").fetchone()[0])
    if not got_lock:
        raise RuntimeError("controller_lease_busy")
    before = {}
    with connection.cursor() as cursor:
        cursor.execute("""
           SELECT b.occurrence_id,b.state,b.state->>'backup_date',
                  l.status,l.size_bytes,l.sha256,l.completed_at
             FROM control.batch_occurrences b
             JOIN control.ledger_backup_requests l
               ON l.backup_date::text=b.state->>'backup_date'
            WHERE b.state->>'batch'='ledger-backup'
              AND b.state->>'backup_date'=ANY(%s)
              AND b.scheduled_at>=now()-interval '30 days'
            ORDER BY b.occurrence_id LIMIT 7
        """, (list(DAYS),))
        rows = cursor.fetchall()
    if len(rows) != len(DAYS) or set(r[2] for r in rows) != set(DAYS):
        raise RuntimeError("six_backup_occurrence_identity_mismatch")
    for key,state,day,status,size,checksum,completed in rows:
        if state.get("status") not in ("running","succeeded"):
            raise RuntimeError("backup_occurrence_state_drift")
        if status!="succeeded" or size is None or size<1024 or (
                not isinstance(checksum,str) or
                not __import__("re").fullmatch("[a-f0-9]{64}",checksum) or completed is None):
            raise RuntimeError("backup_receipt_invalid")
        if state.get("job")!="janus-batch-controller" or state.get("batch")!="ledger-backup":
            raise RuntimeError("backup_occurrence_job_mismatch")
        before[day]=(status,size,checksum,completed)

    updated_count=0
    # One bounded transaction: a CAS update and matching outbox audit event
    # are atomic. The controller's session advisory lock remains held.
    with connection.transaction(), connection.cursor() as cursor:
        for key,state,day,status,size,checksum,completed in rows:
            if state["status"]=="succeeded":
                continue
            revised=poll_backup(connection,state)
            if revised["status"]!="succeeded" or revised.get("retention_cleanup") != {
                "status":"not_run_in_reconcile"}:
                raise RuntimeError("new_image_backup_poll_contract_missing")
            cursor.execute("""
                UPDATE control.batch_occurrences SET state=%s::jsonb,updated_at=now()
                 WHERE occurrence_id=%s AND state=%s::jsonb
                   AND state->>'status'='running' RETURNING occurrence_id
            """, (json.dumps(revised,sort_keys=True),key,json.dumps(state,sort_keys=True)))
            if cursor.fetchone() is None:
                raise RuntimeError("backup_occurrence_cas_conflict")
            tick=datetime.now(timezone.utc).replace(second=0,microsecond=0).isoformat()
            state_hash=sha256(json.dumps(revised,sort_keys=True).encode()).hexdigest()
            event_id=str(uuid5(NAMESPACE_URL,
                "janus-batch-v1/"+tick+"/"+key+"/reconcile/"+state_hash))
            payload={"schema_version":"batch-event-v1","tick":tick,
                     "occurrence_id":key,"action":"reconcile",
                     "controller_execution":os.environ.get("CLOUD_RUN_EXECUTION",""),
                     **revised}
            cursor.execute("""INSERT INTO control.batch_event_outbox(event_id,payload)
                              VALUES (%s,%s::jsonb) ON CONFLICT DO NOTHING""",
                           (event_id,json.dumps(payload,sort_keys=True)))
            updated_count+=1
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT b.state->>'backup_date',b.state->>'status',
                   l.status,l.size_bytes,l.sha256,l.completed_at
              FROM control.batch_occurrences b
              JOIN control.ledger_backup_requests l
                ON l.backup_date::text=b.state->>'backup_date'
             WHERE b.state->>'batch'='ledger-backup'
               AND b.state->>'backup_date'=ANY(%s)
             ORDER BY b.occurrence_id LIMIT 7
        """, (list(DAYS),))
        final=cursor.fetchall()
    if len(final)!=6 or set(r[0] for r in final)!=set(DAYS):
        raise RuntimeError("repair_final_identity_mismatch")
    if any(r[1]!="succeeded" or tuple(r[2:])!=before[r[0]] for r in final):
        raise RuntimeError("repair_readback_mismatch")
    print(PREFIX+json.dumps({"status":"PASS","source_sha":sha,
        "target_dates":list(DAYS),"updated_occurrences":updated_count,
        "final_succeeded":len(final),"backup_requests_unchanged":True,
        "backup_jobs_dispatched":0,"gcs_calls":0,"gcs_deletions":0,
        "exact_scope":"six-existing-ledger-backup-occurrences"},sort_keys=True),flush=True)
finally:
    if got_lock:
        connection.execute("SELECT pg_advisory_unlock(1835102836,3)")
    control.close()
'''

def request_guard(req):
    if (req.get("intent") != "controller-ledger-backup-occurrence-repair"
        or req.get("approved") is not True
        or req.get("scope") != "existing-dev-controller-only"
        or req.get("sha") != SOURCE_SHA or str(req.get("release_run")) != RELEASE_RUN
        or req.get("backup_dates") != list(BACKUP_DAYS)
        or req.get("no_backup_execution") is not True
        or req.get("no_gcs_mutation") is not True
        or req.get("no_iam_expansion") is not True
        or req.get("no_api_deployment") is not True):
        raise ValueError("controller_repair_request_invalid")

def validate_release(req):
    meta = json.loads(gcp.command([
        "gh","run","view",RELEASE_RUN,
        "--json","headSha,status,conclusion,workflowName"]))
    if meta.get("headSha") != SOURCE_SHA or not gcp.successful_operation(
        meta, RELEASE_RUN, "Janus GHCR full-test image publication","release"):
        raise ValueError("controller_repair_full_release_not_verified")
    image_manifest = json.loads(gcp.command(["skopeo","inspect","--no-creds",
       "docker://ghcr.io/tommylin15/janus-"+COMPONENT+":sha-"+SOURCE_SHA]))
    target = "ghcr.io/tommylin15/janus-"+COMPONENT+"@"+image_manifest.get("Digest","")
    if not gcp.PIN.fullmatch(target) or image_manifest.get("Labels",{}).get(
         "org.opencontainers.image.revision") != SOURCE_SHA:
        raise ValueError("controller_repair_target_digest_unverified")
    gcp.command(["skopeo","inspect","--no-creds","docker://"+target])
    return target

def check_controller_rights():
    expected = {"run.jobs.get","run.jobs.update","run.jobs.run","run.jobs.runWithOverrides"}
    data = gcp.cloud(gcp.ROOT+"/jobs/"+JOB+":testIamPermissions",
                     {"permissions":sorted(expected)},"POST")
    if not expected.issubset(set(data.get("permissions",[]))):
        raise ValueError("controller_repair_existing_iam_insufficient")

def existing_rollback(job):
    old = gcp.image(job)
    if not gcp.PIN.fullmatch(old) or not old.startswith(
            "ghcr.io/tommylin15/janus-ingestion-core@sha256:"):
        raise ValueError("controller_repair_old_digest_not_pinned")
    item = json.loads(gcp.command(["skopeo","inspect","--no-creds","docker://"+old]))
    if item.get("Digest")!=old.rsplit("@",1)[-1] or not re.fullmatch(
            "[0-9a-f]{40}",item.get("Labels",{}).get(
                "org.opencontainers.image.revision","")):
        raise ValueError("controller_repair_old_image_not_retrievable")
    return old

def repair_override(job):
    container=job["template"]["template"]["containers"]
    if len(container)!=1:
        raise ValueError("controller_repair_container_count")
    command=container[0].get("command") or []
    if command not in ([],["python"]):
        raise ValueError("controller_repair_entrypoint_unexpected")
    result={"args":(["-c",PROBE] if command else ["python","-c",PROBE]),
      "env":[{"name":"JANUS_CONTROLLER_LEDGER_REPAIR_SHA","value":SOURCE_SHA},
             {"name":"QUEUE_CONSUMER","value":"false"}]}
    if container[0].get("name"):
        result["name"]=container[0]["name"]
    return result

def repair_six(job, save, receipt):
    gcp.writers()
    gcp.wait_for_terminal_executions()
    operation = gcp.cloud(gcp.ROOT+"/jobs/"+JOB+":run",{
        "etag":job["etag"],
        "overrides":{"taskCount":1,"timeout":"300s",
                     "containerOverrides":[repair_override(job)]}},"POST")
    name=operation.get("name","")
    if not isinstance(name,str) or not name.startswith(gcp.ROOT+"/operations/"):
        raise ValueError("repair_operation_identity_unknown")
    receipt["repair_operation"]=name.rsplit("/",1)[-1]
    save()
    deadline=time.monotonic()+425
    while not operation.get("done") and time.monotonic()<deadline:
        time.sleep(7);operation=gcp.cloud(name)
    if not operation.get("done") or operation.get("error"):
        raise RuntimeError("controller_repair_cloud_operation_failed")
    execution=operation.get("response") or {}
    full=execution.get("name","")
    if not isinstance(full,str) or not full.startswith(
       gcp.ROOT+"/jobs/"+JOB+"/executions/"):
        raise ValueError("controller_repair_execution_identity_unknown")
    identity=full.rsplit("/",1)[-1]
    execution=gcp.cloud(full)
    if not gcp.terminal(execution) or execution.get("succeededCount")!=1 or execution.get("failedCount",0):
        raise RuntimeError("controller_repair_execution_failed")
    selector=('resource.type="cloud_run_job" AND '
        'labels."run.googleapis.com/execution_name"="'+identity+'"')
    receipts=[]
    for _ in range(7):
        data=json.loads(gcp.command(["gcloud","logging","read",selector,
           "--project="+gcp.PROJECT,"--limit=100","--format=json"]))
        receipts=[]
        for row in data:
            line=row.get("textPayload") or ""
            if PREFIX in line:
                try:receipts.append(json.loads(line.split(PREFIX,1)[1]))
                except (ValueError,IndexError):pass
        if receipts:break
        time.sleep(5)
    if len(receipts)!=1:
        raise RuntimeError("controller_repair_verified_receipt_missing")
    result=receipts[0]
    if (result.get("status")!="PASS" or result.get("source_sha")!=SOURCE_SHA
        or result.get("target_dates")!=list(BACKUP_DAYS)
        or result.get("final_succeeded")!=6
        or result.get("backup_requests_unchanged") is not True
        or result.get("backup_jobs_dispatched")!=0
        or result.get("gcs_calls")!=0 or result.get("gcs_deletions")!=0
        or not isinstance(result.get("updated_occurrences"),int)
        or not 0<=result["updated_occurrences"]<=6):
        raise RuntimeError("controller_repair_receipt_not_accepted")
    receipt["repair_execution"]=identity
    receipt["backup_reconciliation"]=result
    save()

def main():
    req=json.loads(REQUEST.read_text(encoding="utf-8"))
    request_guard(req)
    journal={"source_sha":SOURCE_SHA,"release_run":RELEASE_RUN,
      "component":"existing-dev-controller-only","phase":"PRECHECK",
      "scheduler_mutation":"NOT_ATTEMPTED","image_mutation":"NOT_ATTEMPTED",
      "pg_updated":"NOT_VERIFIED","gcs_deletions":0,"backup_jobs_dispatched":0,
      "operations":[],"canaries":[]}
    def save():OUTPUT.write_text(json.dumps(journal,sort_keys=True,indent=2))
    save()
    # All permission, rollback and source checks precede Scheduler pause.
    target=validate_release(req)
    check_controller_rights()
    gcp.command(gcp.LEASE+["acquire"])
    held=True
    paused=False
    touched=False
    old=None
    config_hash=None
    scheduler_hash=None
    try:
        gcp.writers()
        schedule=gcp.scheduler()
        if schedule.get("state")!="ENABLED":
            raise ValueError("controller_repair_scheduler_not_enabled")
        scheduler_hash=gcp.scheduler_fingerprint(schedule)
        gcp.wait_for_terminal_executions()
        current=gcp.job(JOB)
        config_hash=gcp.fingerprint(current)
        old=existing_rollback(current)
        if old==target:
            raise ValueError("controller_repair_target_already_deployed")
        journal.update(old_image_digest=old.rsplit("@",1)[-1],
                       target_image_digest=target.rsplit("@",1)[-1],
                       old_source_sha="registry_verified")
        save()
        paused=True
        journal["phase"]="PAUSING_SCHEDULER";save()
        gcp.set_scheduler("pause","PAUSED")
        journal["scheduler_mutation"]="PAUSED";save()
        gcp.writers()
        gcp.wait_for_terminal_executions()
        touched=True
        journal["phase"]="UPDATING_CONTROLLER";save()
        gcp.update(JOB,target,config_hash)
        journal["image_mutation"]="CONTROLLER_ONLY";save()
        journal["phase"]="READINESS_CANARY";save()
        gcp.canary(JOB,target,config_hash,journal,save)
        journal["phase"]="REPAIRING_SIX";save()
        repair_six(gcp.job(JOB),save,journal)
        journal["pg_updated"]="SIX_SUCCESS_READBACK"
        journal["phase"]="FINAL_READBACK";save()
        gcp.checked_image(JOB,target,config_hash)
        gcp.wait_for_terminal_executions()
        if gcp.scheduler_fingerprint(gcp.scheduler())!=scheduler_hash:
            raise ValueError("controller_repair_scheduler_config_drift")
        gcp.set_scheduler("resume","ENABLED")
        journal["scheduler_mutation"]="RESTORED_ENABLED"
        journal["phase"]="PASS";save()
    except Exception:
        journal["failed_at"]=journal["phase"]
        journal["phase"]="RECOVERY_REQUIRED";save()
        # No blind restore if the state is ambiguous. Preserve paused Scheduler
        # and deployment lease if recovery cannot be proved.
        if paused and old and config_hash:
            if gcp.scheduler()["state"]!="PAUSED":
                raise RuntimeError("controller_repair_scheduler_unknown_lease_retained")
            gcp.wait_for_terminal_executions()
            current=gcp.job(JOB)
            if gcp.fingerprint(current)!=config_hash:
                raise RuntimeError("controller_repair_config_drift_lease_retained")
            if gcp.image(current) not in (old,target):
                raise RuntimeError("controller_repair_external_image_lease_retained")
            if gcp.image(current)==target:
                gcp.update(JOB,old,config_hash)
            gcp.checked_image(JOB,old,config_hash)
            if gcp.scheduler_fingerprint(gcp.scheduler())!=scheduler_hash:
                raise RuntimeError("controller_repair_schedule_drift_lease_retained")
            gcp.set_scheduler("resume","ENABLED")
            journal["phase"]="RESTORED_OLD_IMAGE";save()
        elif paused:
            raise RuntimeError("controller_repair_preflight_unknown_lease_retained")
        raise
    finally:
        if journal["phase"] in ("PASS","RESTORED_OLD_IMAGE"):
            gcp.command(gcp.LEASE+["release","--safe-to-release"])
            held=False
            journal["global_lease_released"]=True;save()
    if held or journal["phase"]!="PASS":
        raise RuntimeError("controller_repair_not_fully_accepted")
    print(json.dumps({"status":"PASS","component":JOB,
          "backup_repaired":journal["backup_reconciliation"]["updated_occurrences"],
          "backup_succeeded":6,"scheduler":"ENABLED",
          "existing_job_updated":True,"data_scope":"six-backup-occurrences",
          "gcs_deletions":0,"backup_jobs_dispatched":0},sort_keys=True))

if __name__=="__main__":
    main()
