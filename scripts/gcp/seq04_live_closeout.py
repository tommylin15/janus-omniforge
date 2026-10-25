#!/usr/bin/env python3
"""SEQ-04 bounded one-shot Dev closeout through already-deployed workers.

No new GCP resources, Scheduler changes, Job image updates, Owner mutation,
or Iceberg mutation. A failed worker dispatch is not retried.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from urllib.error import HTTPError
from datetime import datetime, timezone

sys.path.insert(0, "scripts/gcp")
from seq04_immediate_readonly import (
    BUCKETS, list_bucket, get_token, stage_dry_run,
    backup_retention_dry_run, vm_query, iceberg_buckets, controller_pg_readback,
)
from ghcr_jobs_rollout import ROOT, cloud, job, fence, scheduler, terminal

PROJECT = "gen-lang-client-0593591102"
OUT = Path("seq04-closeout-live-receipt.json")

def emit(result):
    OUT.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n")
    print("SEQ04_CLOSEOUT_RECEIPT=" + json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)

def objects(token):
    inv = list_bucket(token, BUCKETS["stage"], pages=20, limit=1000)
    if not inv["complete"] or len(inv["items"]) > 20000:
        raise RuntimeError("stage_inventory_incomplete_or_over_budget")
    return {(x["name"], str(x["generation"])): int(x["size"]) for x in inv["items"]}

def stage_apply(token):
    """Run existing janus-ingestion-core once with Stage-only env override."""
    before_plan = stage_dry_run(token)
    if before_plan.get("status") != "PASS_DRY_RUN":
        raise RuntimeError("stage_dry_run_preflight_blocked")
    if before_plan["planned_objects"] > 6000 or before_plan["planned_bytes"] > 256*1024*1024:
        raise RuntimeError("stage_bounded_budget_exceeded")
    before = objects(token)
    if before_plan["scanned_objects"] != len(before) or before_plan["scanned_bytes"] != sum(before.values()):
        raise RuntimeError("stage_preflight_inventory_drift")
    fence()  # Every existing active writer must be terminal; no blind replay.
    if before_plan["planned_objects"] == 0:
        return {"status": "PASS_NOOP", "dry_run": before_plan, "before_objects": len(before),
                "after_objects": len(before), "deleted_objects": 0, "deleted_bytes": 0}
    current = job("janus-ingestion-core")
    containers = current["template"]["template"]["containers"]
    if len(containers) != 1:
        raise RuntimeError("existing_ingestion_container_shape_drift")
    container = containers[0]
    if container.get("command") not in (None, [], ["python"]):
        raise RuntimeError("existing_ingestion_entrypoint_unknown")
    args = ["-m", "ingestion_core.entrypoint"]
    if not container.get("command"):
        args = ["python"] + args
    override = {
        "args": args,
        "env": [
            {"name":"ICEBERG_MAINTENANCE_MODE","value":"stage-only-apply"},
            {"name":"JANUS_DATA_SUPPLEMENT_MODE","value":""},
            {"name":"JANUS_UNIFIED_COLLECTION","value":"false"},
            {"name":"JANUS_CONTROL_MIGRATION","value":""},
            {"name":"JANUS_ANALYSIS_REPLAY_CONFIG","value":""},
            {"name":"QUEUE_CONSUMER","value":"false"},
            {"name":"MART_JOB","value":""},
        ],
    }
    if container.get("name"):
        override["name"] = container["name"]
    # Final read-only topology fence before a single, no-retry dispatch.
    s = scheduler()
    if s.get("state") != "ENABLED" or s.get("schedule") != "30 */2 * * *":
        raise RuntimeError("scheduler_topology_drift")
    fence()
    operation = cloud(f"{ROOT}/jobs/janus-ingestion-core:run", {
        "etag": current["etag"],
        "overrides": {"taskCount":1, "timeout":"900s", "containerOverrides":[override]}
    }, "POST")
    operation_name = str(operation.get("name", ""))
    if not operation_name.startswith(ROOT + "/operations/"):
        raise RuntimeError("stage_dispatch_response_unknown_no_retry")
    record = {"status":"DISPATCHED_PENDING_TERMINAL", "operation_id":operation_name.rsplit("/",1)[-1],
              "dry_run": before_plan, "before_objects":len(before), "before_bytes":sum(before.values())}
    emit({"component":"seq04-closeout","stage":record,"mutation_scope":"existing-dev-stage-only"})
    deadline = time.monotonic()+1000
    while not operation.get("done") and time.monotonic()<deadline:
        time.sleep(8)
        operation = cloud(operation_name)
    if not operation.get("done"):
        return {**record, "status":"AMBIGUOUS_OPERATION_TIMEOUT"}
    if operation.get("error"):
        return {**record, "status":"FAILED_CLOUD_RUN_OPERATION"}
    response = operation.get("response", {})
    if not terminal(response) or response.get("succeededCount") != 1 or response.get("failedCount", 0) != 0:
        return {**record, "status":"FAILED_WORKER_OR_NONTERMINAL",
                "execution_id":str(response.get("name","")).rsplit("/",1)[-1]}
    after = objects(token)
    missing = {k:v for k,v in before.items() if k not in after}
    if any(k in after and after[k] != v for k,v in before.items()):
        return {**record, "status":"PARTIAL_GENERATION_DRIFT"}
    deleted_objects=len(missing)
    deleted_bytes=sum(missing.values())
    result={**record, "status":"PASS" if (deleted_objects==before_plan["planned_objects"]
                                       and deleted_bytes==before_plan["planned_bytes"]) else "PARTIAL_READBACK_MISMATCH",
            "execution_id":str(response.get("name","")).rsplit("/",1)[-1],
            "after_objects":len(after),"after_bytes":sum(after.values()),
            "deleted_objects":deleted_objects,"deleted_bytes":deleted_bytes,
            "generation_fenced_worker":"stage-only-apply"}
    return result

def private_retention_apply(token):
    before = backup_retention_dry_run(token)
    if before.get("status") != "DRY_RUN_PASS":
        raise RuntimeError("private_backup_retention_dry_run_blocked")
    cmd = (
        "set -eu; "
        "sudo systemctl is-active --quiet janus-ledger-backup-executor.timer; "
        "if sudo systemctl is-active --quiet janus-ledger-backup-executor.service; "
        "then echo BACKUP_EXECUTOR_RUNNING; exit 5; fi; "
        "sudo env GCP_ENVIRONMENT=dev GCP_PROJECT_ID="+PROJECT+" "
        "JANUS_BACKUP_RETENTION_SCHEDULED_APPLY=true "
        "PYTHONPATH=/var/lib/janus python3 -c " +
        shlex.quote(
          "import json,subprocess; import ledger_backup_executor as b; "
          "day=b.sql(\"SELECT backup_date::text FROM control.ledger_backup_requests "
          "WHERE status='succeeded' AND coalesce(retention_status,'pending') <> 'succeeded' "
          "ORDER BY backup_date DESC LIMIT 1\"); "
          "assert day and len(day)==10, 'no_pending_successful_backup'; "
          "print('VM_RETENTION_RESULT='+json.dumps({'backup_date':day,'status':b.retain(day)}))"
        )
    )
    p = subprocess.run(["gcloud","compute","ssh","janus-postgres-dev",
           "--project="+PROJECT, "--zone=us-central1-a","--tunnel-through-iap",
           "--quiet","--command="+cmd],
           capture_output=True,text=True,timeout=240,check=False)
    # Never expose VM stderr or credential-bearing command text.
    if p.returncode:
        return {"status":"BLOCKED_VM_RETENTION_EXECUTION","dry_run":before,
                "return_code":p.returncode}
    receipt_lines=[line.split("VM_RETENTION_RESULT=",1)[1] for line in p.stdout.splitlines()
                   if "VM_RETENTION_RESULT=" in line]
    if len(receipt_lines)!=1:
        return {"status":"AMBIGUOUS_VM_RETENTION_RECEIPT","dry_run":before}
    result=json.loads(receipt_lines[0])
    after=backup_retention_dry_run(token)
    pg=vm_query("SELECT backup_date::text || '|' || status || '|' || coalesce(retention_status,'?') "
                "FROM control.ledger_backup_requests ORDER BY backup_date DESC LIMIT 8")
    success=(result.get("status")=="succeeded" and
             any(x==result["backup_date"]+"|succeeded|succeeded" for x in pg) and
             all(before["count_before"][k]-after["count_before"][k] == before["planned_deletes"][k]
                 for k in ("daily","weekly","monthly")) and
             all(before["bytes_before"][k]-after["bytes_before"][k]>=0
                 for k in ("daily","weekly","monthly")))
    return {"status":"PASS" if success else "PARTIAL_READBACK_MISMATCH",
            "backup_date":result.get("backup_date"), "executor_status":result.get("status"),
            "dry_run":before,
            "count_after":after.get("count_before"),
            "bytes_after":after.get("bytes_before"),
            "deleted_objects":{k:before["count_before"][k]-after["count_before"][k]
                               for k in ("daily","weekly","monthly")},
            "deleted_bytes":{k:before["bytes_before"][k]-after["bytes_before"][k]
                             for k in ("daily","weekly","monthly")},
            "pg_latest_retention_rows": [x.rsplit("|",1)[-1] for x in pg[:8]]}


def catalog_current_pointer_readback(token):
    """Read current PostgreSQL SqlCatalog pointers, then actual GCS metadata."""
    import re
    from urllib.parse import urlsplit
    from ingestion_core.stage import GcsObjectStore
    from seq04_immediate_readonly import api_json, BASE
    from urllib.parse import quote
    output={"status":"NOT_VERIFIED","by_role":{role:{"pointers":0,"readable":0,"current_snapshot_valid":0,
                    "empty_snapshot":0,"failed":0} for role in ("core","mart","private")},
            "private_names_exported":0}
    try:
        dbnames=vm_query("SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate ORDER BY datname")
        dbnames=[d for d in dbnames if re.fullmatch(r"[a-z][a-z0-9_]{0,40}",d)][:8]
        found=0
        total=0
        for db in dbnames:
            remote=("sudo docker exec --user postgres janus-postgres psql -X -qAt "
                    "-v ON_ERROR_STOP=1 -d "+shlex.quote(db)+" -c ")
            inspect_sql=("SELECT table_schema FROM information_schema.tables "
                         "WHERE table_name='iceberg_tables' ORDER BY table_schema LIMIT 3")
            command=["gcloud","compute","ssh","janus-postgres-dev",
                     "--project="+PROJECT,"--zone=us-central1-a","--tunnel-through-iap","--quiet",
                     "--command="+remote+shlex.quote(inspect_sql)]
            proc=subprocess.run(command,capture_output=True,text=True,timeout=100,check=False)
            if proc.returncode:
                continue
            schemas=[x.strip() for x in proc.stdout.splitlines()
                     if re.fullmatch(r"[a-z][a-z0-9_]{0,40}",x.strip())]
            for schema in schemas:
                found += 1
                sql=("SELECT metadata_location FROM "+schema+
                     ".iceberg_tables WHERE metadata_location IS NOT NULL ORDER BY metadata_location LIMIT 81")
                command[-1]="--command="+remote+shlex.quote(sql)
                p=subprocess.run(command,capture_output=True,text=True,timeout=100,check=False)
                if p.returncode:
                    continue
                entries=[x.strip() for x in p.stdout.splitlines() if x.strip()]
                if len(entries)>80:
                    raise RuntimeError("catalog_pointer_scope_exceeds_80")
                total += len(entries)
                for uri in entries:
                    u=urlsplit(uri)
                    role=next((r for r in output["by_role"] if u.scheme=="gs" and
                               u.netloc==BUCKETS[r]),None)
                    if role is None:
                        continue
                    row=output["by_role"][role]
                    row["pointers"]+=1
                    try:
                        object_name=u.path.lstrip("/")
                        meta=api_json(token, BASE+"/b/"+quote(u.netloc,safe="")+
                                      "/o/"+quote(object_name,safe=""))
                        if int(meta.get("size",0))>2*1024*1024:
                            raise ValueError("metadata_over_budget")
                        store=GcsObjectStore(u.netloc)
                        store._token=lambda:token
                        doc=json.loads(store.read(object_name))
                        if "format-version" not in doc or "table-uuid" not in doc:
                            raise ValueError("iceberg_metadata_invalid")
                        row["readable"]+=1
                        current=doc.get("current-snapshot-id")
                        if current is None or current==-1:
                            row["empty_snapshot"]+=1
                        elif any(x.get("snapshot-id")==current for x in doc.get("snapshots",[])):
                            row["current_snapshot_valid"]+=1
                        else:
                            raise ValueError("current_snapshot_not_in_metadata")
                    except (ValueError,KeyError,TypeError,HTTPError,RuntimeError):
                        row["failed"]+=1
        output["catalog_db_count"]=len(dbnames)
        output["catalog_table_count"]=found
        output["pointer_rows_seen"]=total
        valid=sum(v["pointers"] for v in output["by_role"].values())
        output["status"]=("PASS" if found and valid and
                          all(v["failed"]==0 for v in output["by_role"].values()) and
                          all(v["pointers"]>0 for v in output["by_role"].values()) else
                          "PARTIAL_CATALOG_SCOPE_OR_POINTER")
    except Exception as error:
        output["status"]="BLOCKED_CATALOG_"+type(error).__name__.upper()
    return output

def main():
    request=json.loads(Path("ops/seq04-live-closeout-request.json").read_text())
    if not (
        request.get("intent")=="seq04-existing-dev-bounded-closeout"
        and request.get("approved")==True
        and request.get("project")==PROJECT
        and request.get("no_new_gcp_resources")==True
        and request.get("no_scheduler_changes")==True
        and request.get("no_owner_mutation")==True
        and request.get("stage_max_objects")==6000
        and request.get("stage_max_bytes")==268435456
        and request.get("private_daily_cap")==3
        and request.get("private_weekly_cap")==1
        and request.get("private_monthly_cap")==1
        and request.get("phase") in ("readback","stage","private","all")
    ):
        raise RuntimeError("unauthorized_closeout_request")
    phase=request["phase"]
    receipt={"component":"seq04-closeout", "phase":phase,
             "observed_utc":datetime.now(timezone.utc).isoformat(),
             "scheduler_changes":0,"new_gcp_resources":0,"owner_mutations":0,
             "stage":{"status":"NOT_ATTEMPTED"},"private_retention":{"status":"NOT_ATTEMPTED"},
             "iceberg":{"status":"NOT_ATTEMPTED"}, "pg":{"status":"NOT_ATTEMPTED"}}
    token=get_token()
    receipt["pg"]=controller_pg_readback()
    receipt["iceberg"]={"catalog":catalog_current_pointer_readback(token),\n                         "gcs_metadata_only":iceberg_buckets(token)}
    emit(receipt)
    for name, fn in (("stage",stage_apply),("private_retention",private_retention_apply)):
        if phase not in ("all",name if name=="stage" else "private"):
            continue
        try:
            receipt[name]=fn(token)
        except Exception as error:
            # Do not retry ambiguous jobs or DELETE operations.
            receipt[name]={"status":"BLOCKED_OR_AMBIGUOUS",
                           "reason_class":type(error).__name__,
                           "reason_code":str(error)[:100] if isinstance(error,RuntimeError) else "unexpected_error"}
        emit(receipt)
    emit(receipt)
    if any(receipt[k].get("status") not in ("PASS","PASS_NOOP") for k in
           (("stage",) if phase=="stage" else ("private_retention",) if phase=="private"
            else ("stage","private_retention") if phase=="all" else ())):
        raise SystemExit(1)

if __name__=="__main__":
    main()
