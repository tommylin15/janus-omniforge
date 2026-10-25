#!/usr/bin/env python3
"""SEQ-05 one bounded failure diagnosis and Core/Serving readback. No data writes.

Uses existing dev Job for one ephemeral read-only probe; no Job configuration,
Registry, Scheduler or source data changes. Never redispatch failed backfill.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import time
from ghcr_jobs_rollout import ROOT, PROJECT, cloud, fingerprint, job, terminal

OP = ROOT + "/operations/ede50d67-23a1-4da4-bff7-7577a3d2c06f"
OUT = Path("/tmp/seq05-failed-job-readback.json")
PREFIX = "JANUS_SEQ05_DIAG_V1:"
PROBE = r'''
import calendar,json,os
from collections import defaultdict,Counter
from datetime import date,datetime,timezone
from pyiceberg.expressions import And,In,GreaterThanOrEqual,LessThanOrEqual
from ingestion_core.__main__ import _iceberg_core,_control_plane
out={"probe":"JANUS_SEQ05_DIAG_V1","read_only":True,"symbols":["2330","2882"],
     "start":"2024-10-01","end":"2026-09-30","stocks":[]}
core=control=None
try:
 core=_iceberg_core(os.environ["CORE_BUCKET"],read_only=True)
 control=_control_plane()
 valuation=core.catalog.load_table(core.table_identifier("valuation"))
 snap=valuation.current_snapshot()
 if snap is None:raise RuntimeError("no_core_current_snapshot")
 out["core_snapshot_id"]=str(snap.snapshot_id)
 cols={f.name for f in valuation.schema().fields}
 selection=tuple(k for k in ("symbol","observed_date","pe_ratio","pb_ratio",
       "source_id","provenance_id","execution_id") if k in cols)
 rows=valuation.scan(snapshot_id=snap.snapshot_id,
     row_filter=And(In("symbol",["2330","2882"]),
       GreaterThanOrEqual("observed_date",date(2024,10,1)),
       LessThanOrEqual("observed_date",date(2026,9,30))),
     selected_fields=selection,limit=8001).to_arrow().to_pylist()
 if len(rows)>8000:raise RuntimeError("bounded_valuation_scan_limit")
 # Confirm whether Core already holds usable direct-reported quarterly EPS or
 # BVPS before authorizing any new source fetch. Read-only, two exact symbols.
 financial=core.catalog.load_table(core.table_identifier("financials"))
 financial_snapshot=financial.current_snapshot()
 if financial_snapshot is None:raise RuntimeError("financial_core_snapshot_missing")
 fincols={f.name for f in financial.schema().fields}
 wanted=("symbol","metric","period_basis","fiscal_year","fiscal_quarter",
         "fiscal_period_end","period_end","unit","share_basis","share_basis_status",
         "report_scope","source_id","provenance_id","statement_type","value")
 selected=tuple(k for k in wanted if k in fincols)
 finrows=financial.scan(snapshot_id=financial_snapshot.snapshot_id,
     row_filter=In("symbol",["2330","2882"]),selected_fields=selected,
     limit=2501).to_arrow().to_pylist()
 if len(finrows)>2500:raise RuntimeError("bounded_financial_core_scan_limit")
 out["financial_core_snapshot_id"]=str(financial_snapshot.snapshot_id)
 out["financial_core_rows_scanned"]=len(finrows)
 out["financial_core"]=[]
 for code in ("2330","2882"):
  own=[r for r in finrows if str(r.get("symbol"))==code]
  metric_counts=Counter(str(r.get("metric")) for r in own)
  candidates=[]
  for r in own:
   label=str(r.get("metric",""))
   if ("eps" in label.lower() or "earningspershare" in label.lower()
       or "每股盈餘" in label or "bvps" in label.lower()
       or "book_value_per_share" in label.lower() or "每股淨值" in label):
    candidates.append({"metric":label,"fiscal_year":r.get("fiscal_year"),
     "fiscal_quarter":r.get("fiscal_quarter"),"period_basis":r.get("period_basis"),
     "unit":r.get("unit"),"has_share_basis":bool(r.get("share_basis")),
     "share_basis_status":r.get("share_basis_status"),
     "report_scope":r.get("report_scope"),"source_id":r.get("source_id"),
     "value":str(r.get("value"))[:35]})
  out["financial_core"].append({"symbol":code,"row_count":len(own),
     "source_ids":sorted({str(r.get("source_id")) for r in own if r.get("source_id")}),
     "metric_counts":dict(metric_counts),"candidates":candidates[:120]})
 with control.connection.cursor() as cur:
  for symbol in ("2330","2882"):
   cur.execute("""SELECT payload_json,source_id,provenance_id
     FROM control.market_serving_recent WHERE dataset_id='financials'
     AND symbol=%s AND sort_at < %s ORDER BY sort_at DESC LIMIT 301""",
     (symbol,datetime(2026,10,25,tzinfo=timezone.utc)))
   f=cur.fetchall()
   if len(f)>300:raise RuntimeError("bounded_serving_financial_limit")
   bymonth=defaultdict(list)
   own=[r for r in rows if str(r.get("symbol"))==symbol]
   for row in own:
    d=str(row.get("observed_date"))[:10]
    bymonth[d[:7]].append(row)
   metric="pe_ratio" if symbol=="2330" else "pb_ratio"
   valid=[]
   month_summary={}
   for month,values in sorted(bymonth.items()):
    valid_days=[r for r in values if r.get(metric) is not None]
    last=max((str(r["observed_date"])[:10] for r in valid_days),default=None)
    count_at_last=sum(1 for r in valid_days if str(r["observed_date"])[:10]==last)
    close=date.fromisoformat(month+"-"+str(calendar.monthrange(int(month[:4]),int(month[5:]))[1]).zfill(2))
    near=bool(last and 0<=(close-date.fromisoformat(last)).days<=7)
    if near and count_at_last==1:valid.append(month)
    month_summary[month]={"row_count":len(values),"last_valid_observation":last,
                           "latest_day_count":count_at_last,"valid_month_end":near and count_at_last==1}
   metrics=Counter()
   periods={}
   source_counts=Counter()
   for payload,source,provenance in f:
    if isinstance(payload,dict):
     key=str(payload.get("metric","UNKNOWN"))
     metrics[key]+=1
     if key in ("eps_single_quarter","eps","eps_year_to_date","bvps","book_value_per_share"):
      k=str(payload.get("fiscal_year"))+"Q"+str(payload.get("fiscal_quarter"))
      periods.setdefault(key,[]).append({"period":k,"period_basis":payload.get("period_basis"),
        "unit":payload.get("unit"),"has_share_basis":bool(payload.get("share_basis")),
        "scope":payload.get("report_scope"),"source_id":source,
        "has_provenance":bool(provenance)})
     source_counts[str(source)]+=1
   out["stocks"].append({"symbol":symbol,"core_rows":len(own),
     "months":month_summary,"valid_month_end":valid,"valid_month_count":len(valid),
     "core_execution_ids":sorted({str(r.get("execution_id")) for r in own if r.get("execution_id")})[:30],
     "core_source_ids":sorted({str(r.get("source_id")) for r in own if r.get("source_id")}),
     "serving_financial_rows":len(f),"serving_source_counts":dict(source_counts),
     "serving_metrics":dict(metrics),"financial_candidate_periods":periods})
except Exception as exc:
 out["status"]="BLOCKED_"+type(exc).__name__
 out["failure_code"]=re.sub(r"[^A-Za-z0-9_]", "_",str(exc))[:100] if False else type(exc).__name__
finally:
 if core is not None:
  try:core.close()
  except Exception:pass
 if control is not None:
  try:control.close()
  except Exception:pass
print("JANUS_SEQ05_DIAG_V1:"+json.dumps(out,sort_keys=True,default=str),flush=True)
'''

def logs(execution_name):
    q=('resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'
       +execution_name+'"')
    cp=subprocess.run(["gcloud","logging","read",q,"--project="+PROJECT,
          "--limit=250","--format=json"],capture_output=True,text=True,timeout=65,check=False)
    if cp.returncode: return {"status":"LOG_READ_FAILED"}
    entries=json.loads(cp.stdout)
    selected=[]
    for ent in entries:
        raw=ent.get("jsonPayload")
        if isinstance(raw,dict):
            allowed=("operation","status","phase","error_code","component","execution_id",
                     "core_created","core_reused","core_updated","valuation_periods_requested",
                     "symbols","analysis_as_of","stage","message_type")
            obj={key:raw[key] for key in allowed if key in raw}
            if obj:selected.append(obj)
        message=ent.get("textPayload")
        if isinstance(message,str):
            for line in message.splitlines():
                match=re.search(r"(?:ValueError|RuntimeError|TimeoutError|PermissionError|MemoryError|KeyError|TypeError|ImportError|ModuleNotFoundError|psycopg\.[A-Za-z]+|Exception):\s*([a-zA-Z0-9_ -]{0,100})",line)
                if match:
                    selected.append({"exception":match.group(0)[:150]})
    return {"status":"READ","summaries":selected[-25:],"entries_scanned":len(entries)}

def probe_readback(execution_name):
    q=('resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'
       +execution_name+'"')
    for attempt in range(5):
        cp=subprocess.run(["gcloud","logging","read",q,"--project="+PROJECT,
                "--limit=200","--format=json"],capture_output=True,text=True,timeout=65,check=False)
        if cp.returncode: raise RuntimeError("seq05_probe_log_read_failed")
        for entry in json.loads(cp.stdout):
            raw=entry.get("textPayload") or ""
            if PREFIX not in raw:continue
            try:
                obj=json.loads(raw.split(PREFIX,1)[1].strip())
                if obj.get("probe")==PREFIX[:-1] and obj.get("symbols")==["2330","2882"]:
                    return obj
            except ValueError:pass
        time.sleep(attempt+3)
    raise RuntimeError("seq05_probe_receipt_missing")

def main():
    op=cloud(OP)
    target=op.get("metadata",{}).get("target")
    listing=cloud(ROOT+"/jobs/janus-ingestion-core/executions?pageSize=100")
    candidates=[e for e in listing.get("executions",[])
         if "2026-10-25T06:22:00" <= e.get("createTime","") <= "2026-10-25T06:31:00"]
    safe=[{"name":e.get("name","").rsplit("/",1)[-1],
        "create_time":e.get("createTime"),"complete_time":e.get("completionTime"),
        "succeeded":e.get("succeededCount"),"failed":e.get("failedCount"),
        "running":e.get("runningCount"),
        "conditions":[{"state":c.get("state"),"reason":c.get("reason"),
                       "message":str(c.get("message",""))[:220]}
                       for c in e.get("conditions",[]) if c.get("type")=="Completed"]}
        for e in candidates]
    report={"scope":"seq05_failed_execution_diagnosis_v1","target_operation":OP,
        "operation_done":op.get("done",False),"operation_error_code":(op.get("error") or {}).get("code"),
        "operation_target":target,"candidate_executions":safe,"read_only":True,
        "data_mutations":0}
    # If the operation has no explicit execution target, only use a single
    # time-bounded candidate. Never accidentally attribute another Job's logs.
    matched=[e for e in candidates if target and e.get("name")==target]
    if len(matched)!=1 and not target and len(candidates)==1:matched=candidates
    if len(matched)==1:
        report["failed_job_logs"]=logs(matched[0]["name"].rsplit("/",1)[-1])
    else:
        report["failed_job_logs"]={"status":"AMBIGUOUS_EXECUTION"}
    job_data=job("janus-ingestion-core")
    before=fingerprint(job_data)
    containers=job_data["template"]["template"]["containers"]
    if len(containers)!=1 or containers[0].get("command") not in (None,[],["python"]):
        raise RuntimeError("seq05_job_template_unexpected")
    override={"args":["-c",PROBE] if containers[0].get("command") else ["python","-c",PROBE],
              "env":[{"name":"QUEUE_CONSUMER","value":"false"}]}
    if containers[0].get("name"):override["name"]=containers[0]["name"]
    new=cloud(ROOT+"/jobs/janus-ingestion-core:run",
        {"etag":job_data["etag"],"overrides":{"taskCount":1,"timeout":"350s",
          "containerOverrides":[override]}},"POST")
    name=new.get("name","")
    report["read_only_probe_operation"]=name
    if not name.startswith(ROOT+"/operations/"):
        OUT.write_text(json.dumps(report,indent=2)+"\n")
        raise RuntimeError("seq05_unknown_probe_submission_do_not_repeat")
    limit=time.monotonic()+420
    while not new.get("done") and time.monotonic()<limit:
        time.sleep(8)
        new=cloud(name)
    if not new.get("done") or new.get("error"):
        report["read_only_probe_status"]="FAILED_OR_UNKNOWN"
        OUT.write_text(json.dumps(report,indent=2)+"\n")
        raise RuntimeError("seq05_probe_not_successful")
    execution=new.get("response") or {}
    if not terminal(execution) or execution.get("succeededCount")!=1:
        raise RuntimeError("seq05_probe_execution_failed")
    en=execution.get("name","").rsplit("/",1)[-1]
    if not re.fullmatch(r"janus-ingestion-core-[a-z0-9-]+",en):
        raise RuntimeError("seq05_probe_bad_execution_identity")
    report["read_only_probe_execution"]=en
    report["core_readback"]=probe_readback(en)
    report["job_template_unchanged"]=before==fingerprint(job("janus-ingestion-core"))
    if not report["job_template_unchanged"]:
        raise RuntimeError("seq05_job_template_drift")
    OUT.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2,default=str)+"\n")
    print("JANUS_SEQ05_READBACK:"+json.dumps(report,sort_keys=True,ensure_ascii=False,default=str),flush=True)
    if report["core_readback"].get("status","").startswith("BLOCKED_"):
        raise RuntimeError("seq05_core_probe_blocked")

if __name__=="__main__":
    main()
