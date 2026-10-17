#!/usr/bin/env python3
"""Independent bounded official EPS Core snapshot audit after the existing ingestion Job."""
import json
import subprocess
import sys
import time
from pathlib import Path
from ghcr_jobs_rollout import ROOT, cloud, job, terminal

PROBE=r"""
import json,os
from decimal import Decimal,InvalidOperation
from collections import defaultdict
from pyiceberg.expressions import In
from ingestion_core.__main__ import _iceberg_core
symbols=json.loads(os.environ['DRL01_EPS_SYMBOLS'])
out={'component':'drl01_eps_period_verification','read_only':True,
     'status':'PARTIAL','target_count':len(symbols),'qualified_count':0,'quarter_counts':[],
     'owner_mutation':False,'historical_pit_certified':False}
core=None
try:
    core=_iceberg_core(os.environ['CORE_BUCKET'],read_only=True)
    table=core.catalog.load_table(core.table_identifier('financials'))
    snap=table.current_snapshot()
    out['snapshot_id']=str(snap.snapshot_id)
    rows=table.scan(snapshot_id=snap.snapshot_id,row_filter=In('symbol',symbols),
        selected_fields=('symbol','fiscal_year','fiscal_quarter','fiscal_period_end',
                         'metric','period_basis','statement_type','unit','value','source_id',
                         'provenance_id','availability_at')).to_arrow().to_pylist()
    periods=defaultdict(set)
    for row in rows:
        if (row.get('symbol') not in symbols or row.get('source_id')!='mops'
            or not row.get('provenance_id') or not row.get('availability_at')
            or row.get('unit')!='TWD_per_share'
            or row.get('statement_type') not in ('income','financial')):continue
        try:
            if not Decimal(str(row.get('value'))).is_finite():continue
            y,q=int(row['fiscal_year']),int(row['fiscal_quarter'])
            end=str(row.get('fiscal_period_end') or '')[:10]
            if not 1<=q<=4 or end!=f"{y}-{('03-31','06-30','09-30','12-31')[q-1]}":continue
        except (TypeError,ValueError,InvalidOperation):continue
        metric=str(row.get('metric') or '')
        basis=str(row.get('period_basis') or '')
        if ((metric=='eps_single_quarter' and basis=='single_quarter')
            or q==1 and basis in ('','year_to_date')
            and ('每股盈餘' in metric or metric=='eps_year_to_date')):
            periods[row['symbol']].add(y*4+q-1)
    for sym in symbols:
        indices=periods[sym]
        ok=any({i,i-1,i-2,i-3}<=indices for i in indices)
        out['quarter_counts'].append({'symbol':sym,'valid_single_quarters':len(indices),
                                     'four_contiguous':ok,
                                     'has_2025_q4':2025*4+3 in indices})
        out['qualified_count']+=int(ok)
    out['status']='PASS' if out['qualified_count']==len(symbols) else 'PARTIAL_FOUR_QUARTERS'
except Exception as error:
    out['status']='BLOCKED_'+type(error).__name__
finally:
    if core:
        try:core.close()
        except Exception:pass
    print(json.dumps(out,sort_keys=True,ensure_ascii=False),flush=True)
"""

def main():
    req=json.loads(Path(sys.argv[1]).read_text())
    if (req.get("intent")!="drl01-existing-mops-eps-history" or req.get("approved") is not True
        or req.get("no_new_provider") is not True or req.get("no_job_template_change") is not True
        or not isinstance(req.get("symbols"),list) or not 1<=len(req["symbols"])<=2):
        raise ValueError("unapproved_eps_scope")
    current=job("janus-ingestion-core")
    containers=current["template"]["template"]["containers"]
    if len(containers)!=1 or containers[0].get("command") not in (None,[],["python"]):
        raise ValueError("job_entrypoint_drift")
    override={"args":(["python"] if not containers[0].get("command") else [])+["-c",PROBE],
              "env":[{"name":"QUEUE_CONSUMER","value":"false"},
                     {"name":"DRL01_EPS_SYMBOLS","value":json.dumps(req["symbols"])}]}
    if containers[0].get("name"):override["name"]=containers[0]["name"]
    op=cloud(f"{ROOT}/jobs/janus-ingestion-core:run",
        {"etag":current["etag"],"overrides":{"taskCount":1,"timeout":"400s",
        "containerOverrides":[override]}},"POST")
    name=op.get("name","")
    if not name.startswith(ROOT+"/operations/"):raise RuntimeError("bad_core_audit_operation")
    deadline=time.monotonic()+480
    while not op.get("done") and time.monotonic()<deadline:
        time.sleep(8)
        op=cloud(name)
    if not op.get("done") or op.get("error"):raise RuntimeError("eps_core_audit_unverified")
    exe=op.get("response",{})
    if not terminal(exe) or exe.get("succeededCount")!=1 or exe.get("failedCount",0):
        raise RuntimeError("eps_core_audit_failed")
    execution=exe.get("name","").rsplit("/",1)[-1]
    if not execution.startswith("janus-ingestion-core-"):raise ValueError("unknown_execution")
    query='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+execution+'"'
    report=None
    for _ in range(5):
        cp=subprocess.run(["gcloud","logging","read",query,"--project=gen-lang-client-0593591102",
                           "--limit=180","--format=json"],text=True,capture_output=True,timeout=50)
        if cp.returncode==0:
            for event in json.loads(cp.stdout):
                val=event.get("jsonPayload")
                if not isinstance(val,dict):
                    try:val=json.loads(event.get("textPayload",""))
                    except (TypeError,ValueError):continue
                if isinstance(val,dict) and val.get("component")=="drl01_eps_period_verification":
                    report=val;break
        if report:break
        time.sleep(5)
    if report is None:raise RuntimeError("eps_core_receipt_missing")
    out={"execution":execution,"receipt":report}
    Path("/tmp/drl01-eps-core-readback.json").write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print(json.dumps(out,sort_keys=True))
    if report.get("status")!="PASS":raise RuntimeError("eps_four_quarters_partial")

if __name__=="__main__":main()
