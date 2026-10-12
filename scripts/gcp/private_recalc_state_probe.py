#!/usr/bin/env python3
"""Bounded read-only inspection of one failed synthetic recalculation canary.

Runs an ephemeral existing ingestion container with a Python -c override,
performing SELECT only under a PostgreSQL READ ONLY transaction. Neither
owner IDs nor request IDs nor numerical holdings are printed.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as rollout

REQUEST = json.loads(Path("ops/private-recalc-queue-state-request.json").read_text())
EXPECTED = "ghcr.io/tommylin15/janus-ingestion-core@sha256:30bfef87ee0b9fa652c5840dcd78677c021d0fc49041a108bac8cdcf2255b41f"

INSPECT = r"""
import json
from ingestion_core.serving_schema_migration import _private_api_connection
from packages.postgres_bundle import load_postgres_bundle

load_postgres_bundle("JANUS_INGESTION_POSTGRES_BUNDLE", {
  "CONTROL_DB_PASSWORD": ("ingestion_control_password","control_password"),
  "CATALOG_DB_PASSWORD": ("ingestion_catalog_password","catalog_password")
})
db=_private_api_connection()
try:
  with db.transaction(), db.cursor() as cur:
    cur.execute("SET TRANSACTION READ ONLY")
    cur.execute(
      "SELECT r.status,r.attempt_count,r.worker_task_index,r.worker_execution,"
      "r.requested_ledger_version,u.ledger_version,r.error_code,"
      "r.safe_message "
      "FROM private.recalculation_requests r JOIN private.users u ON u.user_id=r.user_id "
      "WHERE r.requested_at >= %s::timestamptz AND r.requested_at <= %s::timestamptz "
      "AND r.trigger_source='manual' ORDER BY r.requested_at DESC LIMIT 8",
      ('2026-10-12T16:29:00Z','2026-10-12T16:41:00Z'))
    found=[]
    for r in cur.fetchall():
      status,attempts,worker_idx,execution,requested,version,err,msg=r
      found.append({
        'status':str(status),
        'attempt_count':int(attempts or 0),
        'worker_index_valid':worker_idx in (0,1),
        'execution_matches':str(execution or '')=='janus-private-pipeline-45h2t',
        'checkpoint_matches':int(requested or 0)==int(version or -1),
        'error_class':str(err or '')[:60] if str(err or '').isupper() else 'none',
        'synthetic_marker': '系統驗收' in str(msg or '')
      })
    cur.execute("SELECT COUNT(*) FROM private.recalculation_requests WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED')")
    active=int(cur.fetchone()[0])
    cur.execute("SELECT active FROM private.recalculation_dispatch WHERE singleton=true")
    flag=cur.fetchone()
    dispatch=bool(flag[0]) if flag else None
    print('RECALC_P0_STATE='+json.dumps({
        'query_read_only':True,'matching_window_count':len(found),
        'rows':found, 'active_request_count':active,'dispatch_active':dispatch
      },sort_keys=True,ensure_ascii=False),flush=True)
finally:
  db.close()
"""

def main():
    req=REQUEST
    if (req.get("intent")!="inspect-one-failed-synthetic-private-recalc"
        or req.get("approved") is not True
        or req.get("read_only") is not True
        or req.get("source_sha")!="50eda171ef6ffb3971a4d140ad09bac870ead6c1"
        or req.get("failed_run")!="38274621290"):
        raise ValueError("read_only_recalc_inspection_request_not_approved")
    job=rollout.job("janus-ingestion-core")
    if rollout.image(job)!=EXPECTED:
        raise ValueError("ingestion_image_changed")
    rollout.fence()
    container=job["template"]["template"]["containers"][0]
    command=container.get("command") or []
    if command not in ([],["python"]):
        raise ValueError("ingestion_container_entrypoint_not_expected")
    args=(["-c",INSPECT] if command else ["python","-c",INSPECT])
    override={"args":args,"env":[]}
    if container.get("name"):
        override["name"]=container["name"]
    operation=rollout.cloud(
        f"{rollout.ROOT}/jobs/janus-ingestion-core:run",
        {"etag":job["etag"],"overrides":{"taskCount":1,"timeout":"240s","containerOverrides":[override]}},
        "POST")
    deadline=time.monotonic()+420
    while not operation.get("done") and time.monotonic()<deadline:
        time.sleep(6)
        operation=rollout.cloud(operation["name"])
    if not operation.get("done") or operation.get("error"):
        raise RuntimeError("read_only_probe_terminal_unknown")
    exe=operation.get("response") or {}
    if not rollout.terminal(exe) or exe.get("succeededCount")!=1:
        raise RuntimeError("read_only_probe_execution_failed")
    name=str(exe.get("name","")).split("/")[-1]
    if not re.fullmatch(r"janus-ingestion-core-[a-z0-9]+",name):
        raise RuntimeError("read_only_probe_execution_name_invalid")
    # Cloud Logging source only. No raw records printed: pick our own constant prefix.
    proc=subprocess.run(["gcloud","logging","read",
        'resource.type="cloud_run_job" AND resource.labels.job_name="janus-ingestion-core" AND timestamp>="2026-10-12T16:35:00Z"',
        "--project=gen-lang-client-0593591102","--limit=150","--format=json"],
        check=True,text=True,capture_output=True,timeout=45)
    found=[]
    for log in json.loads(proc.stdout):
        labels=log.get("labels") or {}
        if labels.get("run.googleapis.com/execution_name")!=name:
            continue
        payload=log.get("textPayload") or ""
        if not payload.startswith("RECALC_P0_STATE="):
            continue
        found.append(json.loads(payload.split("=",1)[1]))
    if len(found)!=1:
        raise RuntimeError("read_only_probe_log_readback_unavailable")
    print("recalc_p0_state="+json.dumps(found[0],sort_keys=True,ensure_ascii=False))

if __name__=="__main__":
    main()
