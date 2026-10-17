#!/usr/bin/env python3
"""DRL-01 bounded existing-dev TWSE focus 120-day official Core OHLCV repair.

Only approved current market symbols and official STOCK_DAY; Stage raw first,
write versioned Core, independent after-snapshot readback. No Owner mutations.
"""
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from ghcr_jobs_rollout import ROOT, cloud, job, terminal

PROJECT = "gen-lang-client-0593591102"
PROBE = r"""
import json,os
from datetime import date,datetime,timezone
from uuid import uuid4
from collections import defaultdict
from pyiceberg.expressions import And,GreaterThanOrEqual,In
from ingestion_core.__main__ import _control_plane,_iceberg_core
from ingestion_core.sources import twse_ohlcv_adapter
from ingestion_core.adapters import CollectionRequest
from ingestion_core.first_batch import stage_raw_response
from ingestion_core.stage import GcsObjectStore,StageWriter
from ingestion_core.dq import validate_ohlcv,ALLOWED_COLUMNS

req=json.loads(os.environ["DRL01_FOCUS_REQUEST"])
symbols=set(req["symbols"])
first=date.fromisoformat(req["start_date"])
as_of=date.fromisoformat(req["as_of"])
report={"component":"drl01_focus_120_day_official","status":"PARTIAL",
        "market":"TWSE","target_count":len(symbols),"month_receipts":[],
        "owner_mutation":False,"job_template_mutation":False}
control=None
core=None
try:
    control=_control_plane()
    if not control.source_is_approved("twse"):
        raise RuntimeError("official_source_not_approved")
    with control.connection.cursor() as cursor:
        cursor.execute("SELECT symbol FROM control.stock_master WHERE enabled AND market='TWSE' AND symbol=ANY(%s)",(sorted(symbols),))
        allowed={str(r[0]) for r in cursor.fetchall()}
    if allowed!=symbols:
        raise RuntimeError("unapproved_focus_membership")
    core=_iceberg_core(os.environ["CORE_BUCKET"])
    stage=GcsObjectStore(os.environ["STAGE_BUCKET"])
    writer=StageWriter(stage)
    def coverage():
        table=core.catalog.load_table(core.table_identifier("ohlcv"))
        snapshot=table.current_snapshot()
        records=table.scan(snapshot_id=snapshot.snapshot_id,
            row_filter=And(GreaterThanOrEqual("trade_date",first),In("symbol",sorted(symbols))),
            selected_fields=("symbol","market","trade_date","close","source_id","provenance_id")).to_arrow().to_pylist()
        dated=defaultdict(set)
        for row in records:
            day=date.fromisoformat(str(row["trade_date"])[:10])
            if (row.get("market")=="TWSE" and row["symbol"] in symbols and day<=as_of and
                row.get("close") is not None and row.get("source_id")=="twse" and row.get("provenance_id")):
                dated[row["symbol"]].add(day)
        return dated, str(snapshot.snapshot_id)
    before,_=coverage()
    report["qualified_before"]=sum(len(before[s])>=120 for s in symbols)
    months=[]
    month=first.replace(day=1)
    while month<=as_of:
        months.append(month)
        month=date(month.year+(month.month==12), month.month%12+1,1)
    adapter=twse_ohlcv_adapter()
    for month in months:
        needed=sorted(s for s in symbols if len(before[s])<120)
        if not needed:break
        item={"month":month.isoformat()[:7],"requested":len(needed),"qualified_rows":0,"quarantined_rows":0}
        for symbol in needed:
            # One official complete calendar-month STOCK_DAY document per symbol.
            execution=str(uuid4())
            request=CollectionRequest(execution,execution,adapter.source_id,"ohlcv","TWSE",
                                      (symbol,),month,month,35)
            try:
                response=adapter.fetch(request)
                projected=[{k:r.get(k) for k in ALLOWED_COLUMNS if k!="change_percent"}|
                           {"change_percent":None,"source_id":"twse","observed_at":r["trade_date"]+"T00:00:00Z"}
                           for r in response.rows if first<=date.fromisoformat(str(r["trade_date"]))<=as_of
                           and date.fromisoformat(str(r["trade_date"])) not in before[symbol]]
                if not projected:continue
                dq=validate_ohlcv(projected,analysis_as_of=as_of)
                item["quarantined_rows"]+=len(dq.quarantined)
                accepted=list(dq.accepted)
                if not accepted:continue
                staged,_=stage_raw_response(response,request,bucket=os.environ["STAGE_BUCKET"],
                                            store=stage,execution_scoped=True)
                commit=core.write(dataset_id="ohlcv",rows=accepted,execution_id=execution,
                                  provenance_id=staged.idempotency_key,source_id="twse",
                                  partition_date=month)
                writer.mark_core_committed(execution,stage_results=[staged])
                item["qualified_rows"]+=len(accepted)
                item["snapshot_id"]=str(commit.snapshot_id)
                before[symbol].update(date.fromisoformat(str(row["trade_date"])) for row in accepted)
            except Exception as error:
                item.setdefault("errors",{}).setdefault(type(error).__name__,0)
                item["errors"][type(error).__name__]+=1
        report["month_receipts"].append(item)
    after,snapshot_id=coverage()
    report["final_snapshot_id"]=snapshot_id
    report["qualified_after"]=sum(len(after[s])>=120 for s in symbols)
    report["minimum_dates"]=min(len(after[s]) for s in symbols)
    report["max_dates"]=max(len(after[s]) for s in symbols)
    report["status"]="PASS" if report["qualified_after"]==len(symbols) else "PARTIAL_FOCUS_COVERAGE"
except Exception as error:
    report["status"]="BLOCKED_"+type(error).__name__
finally:
    if core is not None:
        try:core.close()
        except Exception:pass
    if control is not None:
        try:control.close()
        except Exception:pass
    print(json.dumps(report,sort_keys=True,ensure_ascii=False),flush=True)
"""

def checked(path):
    req=json.loads(Path(path).read_text())
    symbols=req.get("symbols")
    if (req.get("intent")!="drl01-approved-focus-twse-120d"
        or req.get("approved") is not True
        or req.get("no_owner_mutation") is not True
        or req.get("no_job_template_mutation") is not True
        or not isinstance(symbols,list) or not 1<=len(symbols)<=12
        or symbols!=sorted(set(symbols))
        or any(not re.fullmatch(r"[1-9][0-9]{3}",s) for s in symbols)
        or req.get("as_of")!="2026-10-16"
        or not date(2026,3,1)<=date.fromisoformat(req["start_date"])<=date(2026,5,1)):
        raise ValueError("invalid_bounded_focus_scope")
    return req

def main():
    req=checked(sys.argv[1])
    current=job("janus-ingestion-core")
    containers=current["template"]["template"]["containers"]
    if len(containers)!=1 or containers[0].get("command") not in (None,[],["python"]):
        raise ValueError("job_entrypoint_drift")
    override={"args":(["python"] if not containers[0].get("command") else [])+["-c",PROBE],
              "env":[{"name":"QUEUE_CONSUMER","value":"false"},
                     {"name":"DRL01_FOCUS_REQUEST","value":json.dumps(req,separators=(",",":"))}]}
    if containers[0].get("name"):override["name"]=containers[0]["name"]
    op=cloud(f"{ROOT}/jobs/janus-ingestion-core:run",
        {"etag":current["etag"],"overrides":{"taskCount":1,"timeout":"1200s",
        "containerOverrides":[override]}},"POST")
    name=op.get("name","")
    if not name.startswith(ROOT+"/operations/"):raise RuntimeError("invalid_operation")
    deadline=time.monotonic()+1270
    while not op.get("done") and time.monotonic()<deadline:
        time.sleep(8)
        op=cloud(name)
    if not op.get("done") or op.get("error"):raise RuntimeError("focus_operation_status_unknown")
    exe=op.get("response",{})
    if not terminal(exe) or exe.get("succeededCount")!=1 or exe.get("failedCount",0):
        raise RuntimeError("focus_job_failed")
    ename=exe.get("name","").rsplit("/",1)[-1]
    if not ename.startswith("janus-ingestion-core-"):raise ValueError("unexpected_execution_name")
    filt='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+ename+'"'
    receipt=None
    for _ in range(5):
        proc=subprocess.run(["gcloud","logging","read",filt,"--project="+PROJECT,
                             "--limit=180","--format=json"],capture_output=True,text=True,timeout=45)
        if proc.returncode==0:
            for event in json.loads(proc.stdout):
                val=event.get("jsonPayload")
                if not isinstance(val,dict):
                    try:val=json.loads(event.get("textPayload",""))
                    except (ValueError,TypeError):continue
                if isinstance(val,dict) and val.get("component")=="drl01_focus_120_day_official":
                    receipt=val;break
        if receipt is not None:break
        time.sleep(5)
    if receipt is None:raise RuntimeError("focus_receipt_missing")
    out={"execution":ename,"receipt":receipt}
    Path("/tmp/drl01-focus-120d.json").write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print(json.dumps(out,sort_keys=True))
    if receipt.get("status")!="PASS":raise RuntimeError("focus_core_readback_partial")

if __name__=="__main__":main()
