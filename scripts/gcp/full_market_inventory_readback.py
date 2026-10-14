#!/usr/bin/env python3
"""Read-only post-failure inventory proof using existing ingestion identity.

The runner only starts an existing Cloud Run Job with per-execution override.
The override itself performs PostgreSQL SELECT + immutable GCS object GET.
No bootstrap, cursor movement, publication, owner or ledger mutation.
"""
import json
import time
from pathlib import Path
from ghcr_jobs_rollout import cloud, job, terminal, ROOT

JOB = "janus-ingestion-core"
PROBE = r'''
import json, os
from ingestion_core.__main__ import _control_plane
from ingestion_core.stage import GcsObjectStore
control = _control_plane()
try:
    with control.connection.cursor() as cursor:
        cursor.execute("""SELECT execution_id::text, status, error_code, requested_at
        FROM control.executions WHERE requested_at >= %s::timestamptz AND requested_at < %s::timestamptz
        ORDER BY requested_at DESC LIMIT 8""",
        ("2026-10-14T11:58:00Z","2026-10-14T12:20:00Z"))
        rows=cursor.fetchall()
    store = GcsObjectStore(os.environ["CORE_BUCKET"])
    out=[]
    for execution_id,status,error_code,requested_at in rows:
        record={"execution_id":execution_id,"status":str(status),
                "error_code":str(error_code)[:64] if error_code else None,
                "requested_at":requested_at.isoformat()}
        try:
            raw=store.read("executions/"+execution_id+"/coverage-inventory.json")
            x=json.loads(raw)
            allow={"date","dataset","market","source","status","reason",
                   "expected_count","received_count","missing_count",
                   "max_missing_ratio","coverage_accepted","cache_hit"}
            items=[]
            for item in x.get("items",[]):
                if not isinstance(item,dict): continue
                d={k:v for k,v in item.items() if k in allow and
                   isinstance(v,(str,int,float,bool,type(None)))}
                if isinstance(d.get("reason"),str):d["reason"]=d["reason"][:80]
                items.append(d)
            record["inventory"]={"status":x.get("coverage_status"),
                 "coverage_accepted":x.get("coverage_accepted"),
                 "universe_status":x.get("universe_status"),
                 "members":len(x.get("effective_symbols",[])),
                 "items":items[:50]}
        except Exception as error:
            record["inventory_error"]=type(error).__name__
        out.append(record)
    print(json.dumps({"component":"full_market_inventory_readback",
          "status":"PASS","executions":out},sort_keys=True))
finally:
    control.close()
'''

def main():
    current=job(JOB)
    c=current["template"]["template"]["containers"]
    if len(c)!=1 or c[0].get("command") not in (None, [], ["python"]):
        raise ValueError("unknown_job_entrypoint")
    override={"args":(["python"] if not c[0].get("command") else [])+["-c",PROBE],
              "env":[{"name":"QUEUE_CONSUMER","value":"false"}]}
    if c[0].get("name"): override["name"]=c[0]["name"]
    op=cloud(f"{ROOT}/jobs/{JOB}:run",
             {"etag":current["etag"],"overrides":{"taskCount":1,"timeout":"300s",
                                             "containerOverrides":[override]}},"POST")
    name=op.get("name","")
    if not name.startswith(ROOT+"/operations/"):raise ValueError("operation_unverified")
    print(json.dumps({"operation":name,"phase":"read_only_inventory","status":"STARTED"}),flush=True)
    until=time.monotonic()+390
    while not op.get("done") and time.monotonic()<until:
        time.sleep(5)
        op=cloud(name)
    if not op.get("done") or op.get("error"):raise RuntimeError("read_only_inventory_job_not_successful")
    exe=op.get("response",{})
    if not terminal(exe) or exe.get("succeededCount")!=1 or exe.get("failedCount",0):
        raise RuntimeError("read_only_inventory_job_not_verified")
    print(json.dumps({"operation":name,"execution":exe.get("name"),"status":"PASS",
                      "phase":"read_only_inventory","runtime_configuration_changed":False}),flush=True)
if __name__=="__main__":
    main()
