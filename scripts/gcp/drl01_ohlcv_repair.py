#!/usr/bin/env python3
"""Bounded official-data OHLCV history repair on the existing Janus dev Job.

Reads current effective market denominator, reuses original approved market-volume
adapters and Stage -> Core Iceberg. No source, IAM, Scheduler, Job template,
serving or owner transaction changes. All outputs are aggregate only.
"""
import json
import re
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from ghcr_jobs_rollout import ROOT, cloud, job, terminal

PROJECT = "gen-lang-client-0593591102"
JOB = "janus-ingestion-core"
MAX_DATES = 5
TARGET_CEILING = date(2026, 10, 16)

PROBE = r'''
import json
import os
from datetime import date, datetime, timezone
from uuid import uuid4
from pyiceberg.expressions import And, EqualTo
from ingestion_core.__main__ import _control_plane, _iceberg_core
from ingestion_core.first_batch import dataset_adapters, stage_raw_response
from ingestion_core.adapters import CollectionRequest
from ingestion_core.dq import validate_ohlcv
from ingestion_core.stage import GcsObjectStore, StageWriter

args = json.loads(os.environ["DRL01_REQUEST"])
market = args["market"]
dates = [date.fromisoformat(d) for d in args["dates"]]
control = None
core = None
out = {"component":"drl01_official_ohlcv_backfill",
       "market":market,"dates_requested":len(dates),"items":[],
       "read_only":False,"owner_mutation":False,"job_template_mutation":False,
       "status":"PARTIAL"}
try:
    control = _control_plane()
    if not control.source_is_approved("tpex" if market=="TPEX" else "twse"):
        raise RuntimeError("market_source_not_approved")
    with control.connection.cursor() as cursor:
        cursor.execute("SELECT symbol FROM control.stock_master WHERE enabled AND market=%s ORDER BY symbol", (market,))
        members = {str(r[0]) for r in cursor.fetchall()}
    if not 500 <= len(members) <= 1300:
        raise RuntimeError("active_market_denominator_unexpected")
    out["expected_symbols"] = len(members)
    core = _iceberg_core(os.environ["CORE_BUCKET"])
    stage_store = GcsObjectStore(os.environ["STAGE_BUCKET"])
    adapter = dataset_adapters()["tpex-market-volume" if market=="TPEX" else "twse-market-volume"]
    needed = .30 if market=="TPEX" else .10
    for target in dates:
        item={"date":target.isoformat(),"market":market,"status":"UNKNOWN"}
        try:
            table=core.catalog.load_table(core.table_identifier("ohlcv"))
            filtered=table.scan(row_filter=And(EqualTo("trade_date",target),EqualTo("market",market)),
                                selected_fields=("symbol","close")).to_arrow().to_pylist()
            present={str(r["symbol"]) for r in filtered if r.get("close") is not None} & members
            item["before_covered"]=len(present)
            if len(present) * 10 >= len(members) * (7 if market=="TPEX" else 9):
                item["after_covered"]=len(present)
                item["status"]="ALREADY_QUALIFIED"
                out["items"].append(item)
                continue
            exec_id=str(uuid4())
            request=CollectionRequest(exec_id,exec_id,adapter.source_id,adapter.dataset_id,
                                      market,tuple(sorted(members)),target,target,40)
            resp=adapter.fetch(request)
            selection=[dict(r) for r in resp.rows if r.get("symbol") in members]
            dq=validate_ohlcv(selection,analysis_as_of=date(2026,10,16))
            rows=list(dq.accepted)
            if len(rows)>1300 or not rows:
                raise RuntimeError("bounded_market_dq_rejected")
            staged,_=stage_raw_response(resp,request,bucket=os.environ["STAGE_BUCKET"],
                                        store=stage_store,execution_scoped=True)
            commit=core.write(dataset_id="ohlcv",rows=rows,execution_id=exec_id,
                              provenance_id=staged.idempotency_key,source_id=adapter.source_id,
                              partition_date=target)
            StageWriter(stage_store).mark_core_committed(exec_id,stage_results=[staged])
            refreshed=core.catalog.load_table(core.table_identifier("ohlcv"))
            checked=refreshed.scan(row_filter=And(EqualTo("trade_date",target),EqualTo("market",market)),
                                    selected_fields=("symbol","close")).to_arrow().to_pylist()
            valid={str(r["symbol"]) for r in checked if r.get("close") is not None} & members
            item.update(after_covered=len(valid), accepted=len(rows),
                        snapshot_id=str(commit.snapshot_id),
                        status="PASS" if len(valid)*10 >= len(members)*(7 if market=="TPEX" else 9)
                             else "PARTIAL_COVERAGE")
        except Exception as error:
            item["status"]="ERROR_"+type(error).__name__
        out["items"].append(item)
    out["status"]="PASS" if len(out["items"])==len(dates) and all(
        x["status"] in ("PASS","ALREADY_QUALIFIED") for x in out["items"]) else "PARTIAL"
except Exception as error:
    out["status"]="BLOCKED_"+type(error).__name__
finally:
    if core is not None:
        try: core.close()
        except Exception:pass
    if control is not None:
        try: control.close()
        except Exception:pass
    print(json.dumps(out,sort_keys=True,ensure_ascii=False),flush=True)
'''


def validated_request(path):
    request = json.loads(Path(path).read_text(encoding="utf-8"))
    if (request.get("intent") != "drl01-official-historical-ohlcv"
            or request.get("approved") is not True
            or request.get("market") not in ("TWSE","TPEX")
            or request.get("no_new_source") is not True
            or request.get("no_job_template_mutation") is not True
            or request.get("no_owner_mutation") is not True):
        raise ValueError("invalid_drl01_scope")
    dates = request.get("dates")
    if not isinstance(dates,list) or not 1<=len(dates)<=MAX_DATES:
        raise ValueError("invalid_drl01_date_count")
    days = [date.fromisoformat(x) for x in dates]
    if (days!=sorted(set(days)) or
            any(day.weekday()>4 or not TARGET_CEILING-timedelta(days=65)<=day<TARGET_CEILING for day in days)):
        raise ValueError("date_outside_bounded_historical_window")
    return request


def main():
    request = validated_request(sys.argv[1])
    current = job(JOB)
    containers = current["template"]["template"]["containers"]
    if len(containers)!=1 or containers[0].get("command") not in (None,[],["python"]):
        raise ValueError("job_entrypoint_unexpected")
    # Contract guard against future uncontrolled payload growth.
    if len(PROBE)>11500:
        raise ValueError("probe_too_large")
    override={
        "args":(["python"] if not containers[0].get("command") else [])+["-c",PROBE],
        "env":[{"name":"QUEUE_CONSUMER","value":"false"},
               {"name":"DRL01_REQUEST","value":json.dumps(request,separators=(",",":"))}],
    }
    if containers[0].get("name"):override["name"]=containers[0]["name"]
    op=cloud(f"{ROOT}/jobs/{JOB}:run",
             {"etag":current["etag"],"overrides":{"taskCount":1,"timeout":"540s",
                                             "containerOverrides":[override]}},"POST")
    name=op.get("name","")
    if not name.startswith(ROOT+"/operations/"):raise RuntimeError("missing_execution_operation")
    until=time.monotonic()+620
    while not op.get("done") and time.monotonic()<until:
        time.sleep(7)
        op=cloud(name)
    if not op.get("done") or op.get("error"):
        raise RuntimeError("drl01_operation_not_verified")
    execution=op.get("response",{})
    if not terminal(execution) or execution.get("succeededCount")!=1 or execution.get("failedCount",0):
        raise RuntimeError("drl01_execution_not_terminal_pass")
    exec_name=execution.get("name","").rsplit("/",1)[-1]
    if not exec_name.startswith("janus-ingestion-core-"):raise ValueError("invalid_execution_name")
    filt='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+exec_name+'"'
    receipt=None
    for _ in range(5):
        cp=subprocess.run(["gcloud","logging","read",filt,"--project="+PROJECT,
                           "--limit=180","--format=json"],capture_output=True,text=True,timeout=50)
        if cp.returncode==0:
            for row in json.loads(cp.stdout):
                val=row.get("jsonPayload")
                if not isinstance(val,dict):
                    try:val=json.loads(row.get("textPayload",""))
                    except (ValueError,TypeError):continue
                if isinstance(val,dict) and val.get("component")=="drl01_official_ohlcv_backfill":
                    receipt=val
                    break
        if receipt is not None:break
        time.sleep(5)
    if receipt is None:raise RuntimeError("drl01_receipt_missing")
    report={"execution":exec_name,"receipt":receipt,
            "no_job_template_mutation":True,"no_owner_mutation":True}
    Path("/tmp/drl01-ohlcv.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps(report,sort_keys=True))
    if receipt.get("status")!="PASS":raise RuntimeError("drl01_partial_readback")


if __name__=="__main__":
    main()
