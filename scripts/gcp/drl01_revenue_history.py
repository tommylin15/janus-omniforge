#!/usr/bin/env python3
"""DRL-01 bounded official MOPS TWSE market-month archive backfill.

One existing ingestion-core Cloud Run execution, Stage immutable source first,
canonical Iceberg source-version append, per-month readback. No new provider,
owner mutation, scheduler, image or job-template update.
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
import json, os
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4
from pyiceberg.expressions import And, EqualTo
from ingestion_core.__main__ import _control_plane, _iceberg_core
from ingestion_core.data_supplement import _fetch, MonthlyRevenueTable, normalise_monthly
from ingestion_core.stage import GcsObjectStore, StageWriter
from packages.provenance import Provenance

req=json.loads(os.environ["DRL01_REVENUE_REQUEST"])
report={"component":"drl01_mops_revenue_bulk","market":req["market"],"months":[],
        "owner_mutation":False,"new_provider":False,"job_template_mutation":False,
        "status":"PARTIAL"}
control=None
core=None
try:
    control=_control_plane()
    if not control.source_is_approved("mops"):
        raise ValueError("mops_source_not_approved")
    with control.connection.cursor() as cursor:
        cursor.execute("SELECT symbol,name FROM control.stock_master WHERE enabled AND market=%s",
                       (req["market"],))
        names={str(r[0]):str(r[1]) for r in cursor.fetchall()}
    if not 500 <= len(names) <= 1300:
        raise ValueError("unexpected_official_market_denominator")
    core=_iceberg_core(os.environ["CORE_BUCKET"])
    writer=StageWriter(GcsObjectStore(os.environ["STAGE_BUCKET"]))
    for period in req["months"]:
        year,month=(int(v) for v in period.split("-"))
        line={"period":period,"eligible_symbols":len(names),"status":"PARTIAL"}
        rows={}
        staged=[]
        errors=Counter()
        for category in (0,1):
            url=("https://mopsov.twse.com.tw/nas/t21/sii/"
                 f"t21sc03_{year-1911}_{month}_{category}.html")
            try:
                raw,_=_fetch(url)
                html=raw.decode("cp950")
                if f"上市公司{year-1911}年{month}月份" not in html or "單位：千元" not in html:
                    raise ValueError("mops_period_or_unit_mismatch")
                table=MonthlyRevenueTable()
                table.feed(html)
                if not {"公司代號","公司名稱","當月營收"}.issubset(table.headers):
                    raise ValueError("mops_archive_headers_invalid")
                received=datetime.now(timezone.utc)
                provenance=Provenance(str(uuid4()),"mops",url,"financials",
                    received,None,received,"sha256:"+sha256(raw).hexdigest(),
                    False,quality_details={"request_identity":{
                        "market":req["market"],"month":period,"category":category}})
                stage_execution=str(uuid4())
                entry=writer.write_raw(payload=raw,media_type="text/html",extension="html",
                    execution_id=stage_execution,provenance=provenance,execution_scoped=True)
                staged.append((stage_execution,entry))
                for cells in table.entries:
                    if len(cells)!=11:continue
                    symbol=cells[0].strip()
                    if symbol not in names:continue
                    if symbol in rows:
                        errors["duplicate_symbol"]+=1
                        continue
                    try:
                        normalized=normalise_monthly({"code":200,"result":{
                            "yymm":f"{year-1911}{month:02d}",
                            "companyAbbreviation":cells[1],
                            "data":[["本月",cells[2]]]}},symbol,year,month,
                            received_at=received.isoformat(),expected_name=names[symbol])[0]
                        amount=Decimal(normalized["value"])/Decimal(1000)
                        if not amount.is_finite():
                            raise ValueError("nonfinite_revenue")
                        rows[symbol]={**normalized,"metric":"monthly_revenue",
                            "value":str(amount),"unit":"TWD_thousands",
                            "source_unit":"TWD_thousands","source_id":"mops",
                            "provenance_id":entry.idempotency_key,
                            "source_document_sha256":sha256(raw).hexdigest()}
                    except Exception:
                        errors["row_not_qualified"]+=1
            except Exception as error:
                errors["category_"+str(category)+"_"+type(error).__name__]+=1
        line["source_valid_rows"]=len(rows)
        line["quarantine_counts"]=dict(errors)
        if not rows:
            report["months"].append(line)
            continue
        execution=str(uuid4())
        commit=core.write(dataset_id="financials",rows=list(rows.values()),
            execution_id=execution,provenance_id=next(iter(rows.values()))["provenance_id"],
            source_id="mops",partition_date=date.today())
        for stage_execution,entry in staged:
            writer.mark_core_committed(stage_execution,stage_results=[entry])
        table=core.catalog.load_table(core.table_identifier("financials"))
        snapshot=table.current_snapshot()
        observed=table.scan(snapshot_id=snapshot.snapshot_id,
            row_filter=And(EqualTo("fiscal_year",year),EqualTo("fiscal_month",month)),
            selected_fields=("symbol","statement_type","metric","source_id","fiscal_month","value",
                             "unit","provenance_id")).to_arrow().to_pylist()
        present={r["symbol"] for r in observed
                 if r["symbol"] in names and r.get("source_id")=="mops"
                 and r.get("statement_type")=="monthly_revenue"
                 and r.get("metric")=="monthly_revenue"
                 and r.get("unit")=="TWD_thousands"
                 and r.get("provenance_id") and r.get("value") is not None}
        line.update(snapshot_id=str(snapshot.snapshot_id),after_covered=len(present),
            inserted=commit.inserted,updated=commit.updated,reused=commit.reused)
        line["status"]="PASS" if len(present)*10>=len(names)*9 else "PARTIAL_COVERAGE"
        report["months"].append(line)
    report["status"]="PASS" if len(report["months"])==len(req["months"]) and all(
        x["status"]=="PASS" for x in report["months"]) else "PARTIAL"
except Exception as e:
    report["status"]="BLOCKED_"+type(e).__name__
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
    value=json.loads(Path(path).read_text())
    if (value.get("intent")!="drl01-existing-mops-monthly-market-archive"
        or value.get("approved") is not True
        or value.get("market")!="TWSE"
        or value.get("no_new_provider") is not True
        or value.get("no_owner_mutation") is not True
        or value.get("no_job_template_change") is not True):
        raise ValueError("invalid_revenue_scope")
    months=value.get("months")
    if not isinstance(months,list) or not 1<=len(months)<=2:
        raise ValueError("invalid_month_scope")
    actual=[date.fromisoformat(x+"-01") for x in months]
    if actual!=sorted(set(actual)) or any(x<date(2025,8,1) or x>date(2026,9,1) for x in actual):
        raise ValueError("month_out_of_bounded_range")
    return value

def main():
    req=checked(sys.argv[1])
    current=job("janus-ingestion-core")
    containers=current["template"]["template"]["containers"]
    if len(containers)!=1 or containers[0].get("command") not in (None,[],["python"]):
        raise ValueError("job_entrypoint_drift")
    override={"args":(["python"] if not containers[0].get("command") else [])+["-c",PROBE],
        "env":[{"name":"QUEUE_CONSUMER","value":"false"},
               {"name":"DRL01_REVENUE_REQUEST","value":json.dumps(req,separators=(",",":"))}]}
    if containers[0].get("name"):override["name"]=containers[0]["name"]
    op=cloud(f"{ROOT}/jobs/janus-ingestion-core:run",
        {"etag":current["etag"],"overrides":{"taskCount":1,"timeout":"650s",
            "containerOverrides":[override]}},"POST")
    name=op.get("name","")
    if not name.startswith(ROOT+"/operations/"):
        raise RuntimeError("operation_unknown_do_not_retry")
    deadline=time.monotonic()+710
    while not op.get("done") and time.monotonic()<deadline:
        time.sleep(7)
        op=cloud(name)
    if not op.get("done") or op.get("error"):
        raise RuntimeError("revenue_job_status_unknown")
    execution=op.get("response",{})
    if not terminal(execution) or execution.get("succeededCount")!=1 or execution.get("failedCount",0):
        raise RuntimeError("revenue_execution_not_successful")
    ename=execution.get("name","").rsplit("/",1)[-1]
    if not ename.startswith("janus-ingestion-core-"):
        raise ValueError("execution_identity_invalid")
    filt='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+ename+'"'
    receipt=None
    for _ in range(5):
        p=subprocess.run(["gcloud","logging","read",filt,"--project="+PROJECT,"--limit=180",
            "--format=json"],capture_output=True,text=True,timeout=45)
        if p.returncode==0:
            for event in json.loads(p.stdout):
                v=event.get("jsonPayload")
                if not isinstance(v,dict):
                    try:v=json.loads(event.get("textPayload",""))
                    except (ValueError,TypeError):continue
                if isinstance(v,dict) and v.get("component")=="drl01_mops_revenue_bulk":
                    receipt=v
                    break
        if receipt is not None:break
        time.sleep(5)
    if receipt is None:
        raise RuntimeError("revenue_receipt_missing")
    out={"execution":ename,"receipt":receipt}
    Path("/tmp/drl01-revenue-history.json").write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print(json.dumps(out,sort_keys=True))
    if receipt.get("status")!="PASS":
        raise RuntimeError("revenue_core_coverage_partial")

if __name__=="__main__":
    main()
