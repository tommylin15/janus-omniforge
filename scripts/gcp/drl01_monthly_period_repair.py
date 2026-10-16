#!/usr/bin/env python3
"""One-shot bounded DRL-01 month-key repair from existing canonical fiscal period.

Cloud Run per-execution override, existing identity only. No new provider,
trading, schema, scheduler, Job template or API traffic changes.
"""
import json,sys,time,subprocess
from pathlib import Path
from ghcr_jobs_rollout import cloud,job,terminal,ROOT

PROBE=r'''
import os,json
from datetime import date,datetime
from collections import Counter
from uuid import uuid4
from ingestion_core.__main__ import _iceberg_core
mode=os.environ["DRL01_MONTH_MODE"]
out={"component":"drl01_fiscal_month_repair","mode":mode,"status":"UNKNOWN",
     "no_owner_writes":True,"no_source_fetch":True,"no_job_template_mutation":True}
core=None
try:
    core=_iceberg_core(os.environ["CORE_BUCKET"],read_only=mode=="dry-run")
    table=core.catalog.load_table(core.table_identifier("financials"))
    snap=table.current_snapshot()
    out["snapshot_before"]=str(snap.snapshot_id)
    allrows=table.scan(snapshot_id=snap.snapshot_id).to_arrow().to_pylist()
    if len(allrows)>120000:
        raise ValueError("unbounded_financial_rows")
    out["total_records"]=len(allrows)
    out["missing_month_before"]=sum(row.get("fiscal_month") is None and
        row.get("statement_type")=="monthly_revenue" for row in allrows)
    eligible=[]
    reasons=Counter()
    for row in allrows:
        if row.get("statement_type")!="monthly_revenue" or row.get("fiscal_month") is not None:
            continue
        if row.get("metric") not in ("monthly_revenue","previous_month_revenue"):
            reasons["unrecognized_metric"]+=1
            continue
        if row.get("source_id")!="mops" or not row.get("provenance_id"):
            reasons["unverified_existing_source"]+=1
            continue
        raw=row.get("fiscal_period_end")
        try:
            period=raw if isinstance(raw,date) else date.fromisoformat(str(raw)[:10])
            if (period.year!=int(row["fiscal_year"]) or
                (period.month-1)//3+1!=int(row["fiscal_quarter"])):
                raise ValueError("period_identity")
            from calendar import monthrange
            if period.day!=monthrange(period.year,period.month)[1]:
                raise ValueError("not_month_end")
            if row.get("unit")!="TWD_thousands" or row.get("value") is None:
                raise ValueError("unit_or_value")
            if not row.get("version_at") and not row.get("published_at") and not row.get("availability_at"):
                raise ValueError("missing_version")
        except Exception as e:
            reasons["invalid_period_or_unit"]+=1
            continue
        eligible.append({**row,"fiscal_month":period.month,"period_basis":"monthly"})
    out["repair_candidates"]=len(eligible)
    out["unrepaired_reason_counts"]=dict(reasons)
    if len(eligible)>4200:
        raise ValueError("repair_cardinality_over_budget")
    if mode=="dry-run":
        out["status"]="PASS_DRY_RUN"
    elif mode=="apply":
        if not eligible:
            out["status"]="ALREADY_REPAIRED"
        else:
            # Existing provenance/execution/version stay unchanged in each row.
            # Iceberg commits a new snapshot; source observations remain intact.
            commit=core.write(dataset_id="financials",rows=eligible,
                execution_id="drl01-fiscal-repair-"+str(uuid4()),
                provenance_id="existing-official-provenance",
                source_id="mops",partition_date=date.today())
            newer=core.catalog.load_table(core.table_identifier("financials"))
            check=newer.scan(snapshot_id=newer.current_snapshot().snapshot_id,
                selected_fields=("statement_type","fiscal_month","metric")).to_arrow().to_pylist()
            out["missing_month_after"]=sum(r.get("fiscal_month") is None and
                r.get("statement_type")=="monthly_revenue" for r in check)
            out["snapshot_after"]=str(newer.current_snapshot().snapshot_id)
            out["updated"]=int(commit.updated)
            out["inserted"]=int(commit.inserted)
            out["status"]="PASS" if (
                out["missing_month_after"]<=out["missing_month_before"]-len(eligible)
                and len(check)==out["total_records"]
            ) else "PARTIAL_READBACK"
    else:
        out["status"]="BLOCKED_MODE"
except Exception as exc:
    out["status"]="ERROR_"+type(exc).__name__
finally:
    if core is not None:
        try:core.close()
        except Exception:pass
    print(json.dumps(out,sort_keys=True,ensure_ascii=False),flush=True)
'''

def main():
    req=json.loads(Path(sys.argv[1]).read_text())
    if (req.get("intent")!="drl01-existing-month-identity-repair"
        or req.get("approved") is not True
        or req.get("mode") not in ("dry-run","apply")
        or req.get("no_source_fetch") is not True
        or req.get("no_owner_writes") is not True):
        raise ValueError("invalid_month_scope")
    current=job("janus-ingestion-core")
    c=current["template"]["template"]["containers"]
    if len(c)!=1 or c[0].get("command") not in (None,[],["python"]):
        raise ValueError("job_entrypoint_unexpected")
    override={"args":(["python"] if not c[0].get("command") else [])+["-c",PROBE],
              "env":[{"name":"QUEUE_CONSUMER","value":"false"},
                     {"name":"DRL01_MONTH_MODE","value":req["mode"]}]}
    if c[0].get("name"):override["name"]=c[0]["name"]
    op=cloud(f"{ROOT}/jobs/janus-ingestion-core:run",
        {"etag":current["etag"],"overrides":{"taskCount":1,"timeout":"450s",
                           "containerOverrides":[override]}},"POST")
    name=op.get("name","")
    if not name.startswith(ROOT+"/operations/"):
        raise RuntimeError("invalid_execution_operation")
    deadline=time.monotonic()+505
    while not op.get("done") and time.monotonic()<deadline:
        time.sleep(6)
        op=cloud(name)
    if not op.get("done") or op.get("error"):
        raise RuntimeError("repair_job_not_complete")
    exe=op.get("response",{})
    if not terminal(exe) or exe.get("succeededCount")!=1 or exe.get("failedCount",0):
        raise RuntimeError("repair_job_not_verified")
    name=exe.get("name","").rsplit("/",1)[-1]
    filt='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+name+'"'
    receipt=None
    for _ in range(5):
        r=subprocess.run(["gcloud","logging","read",filt,
                          "--project=gen-lang-client-0593591102","--limit=120","--format=json"],
                         capture_output=True,text=True,timeout=40)
        if r.returncode==0:
            for row in json.loads(r.stdout):
                value=row.get("jsonPayload")
                if not isinstance(value,dict):
                    try:value=json.loads(row.get("textPayload",""))
                    except (TypeError,ValueError):continue
                if isinstance(value,dict) and value.get("component")=="drl01_fiscal_month_repair":
                    receipt=value
        if receipt is not None:break
        time.sleep(5)
    if receipt is None:raise RuntimeError("month_repair_receipt_not_observed")
    report={"execution":name,"receipt":receipt}
    Path("/tmp/drl01-fiscal-month.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    expected="PASS_DRY_RUN" if req["mode"]=="dry-run" else "PASS"
    if receipt.get("status") not in (expected,"ALREADY_REPAIRED"):
        raise RuntimeError("fiscal_month_repair_not_accepted")

if __name__=="__main__":
    main()
