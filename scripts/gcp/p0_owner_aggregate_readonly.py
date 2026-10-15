#!/usr/bin/env python3
"""Owner aggregate metadata-only live dev readback after post-Mart business failure.

No calls to source refresh, price persistence, Iceberg writes, ledger writes or
auth endpoints. Existing immutable private-pipeline image; one read-only override.
"""
from __future__ import annotations
import json,os,sys,time,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as r

REQUEST=Path("ops/p0-owner-aggregate-readonly.json")
RECEIPT=Path("/tmp/p0-owner-aggregate-readonly.json")
IMAGE="ghcr.io/tommylin15/janus-private-pipeline@sha256:eba96be824ca853695b23dcbae9b989da1e7d7e2c62eb9513012a4d5155161b2"
CODE=r"""
import json
from datetime import date
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import repository_from_env
from services.api.store import PrivateIcebergStore
load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE",{
 "PRIVATE_DATABASE_URL":("pipeline_database_url","database_url"),
 "MOBILE_LEDGER_DATABASE_URL":"database_url",
 "PRIVATE_CATALOG_PASSWORD":("pipeline_catalog_password","catalog_password"),
 "CORE_CATALOG_PASSWORD":"core_catalog_password"})
repo=repository_from_env()
with repo._connection() as conn:
 owners=conn.execute("SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s AND shares>0",("00697B",)).fetchall()
if len(owners)!=1:raise RuntimeError("owner_scope_not_exactly_one")
owner=owners[0]["user_id"]
ledger=int(repo.latest_ledger_version(owner))
store=PrivateIcebergStore.from_env()
day="2026-10-14"
positions=[p for p in store.mart("mart_user_positions",owner) if str(p.get("valuation_date"))==day and int(p.get("ledger_version") or 0)==ledger]
pnl=[p for p in store.mart("mart_user_unrealized_pnl",owner) if str(p.get("valuation_date"))==day and int(p.get("ledger_version") or 0)==ledger]
totals=[p for p in store.mart("mart_user_portfolio_summary",owner) if str(p.get("valuation_date"))==day and int(p.get("ledger_version") or 0)==ledger and p.get("currency")=="TWD"]
report={"scope":"p0_owner_aggregate_metadata_only","status":"READ_ONLY","as_of":day,"ledger_version":ledger,
 "positions":len(positions),"unrealized_rows":len(pnl),
 "positions_missing_price":[p["symbol"] for p in positions if p.get("market_value") is None],
 "unrealized_missing":[p["symbol"] for p in pnl if p.get("unrealized_pnl") is None],
 "summary_count":len(totals),"no_data_mutation":True}
if len(totals)==1:
 t=totals[0]
 report.update({key:t.get(key) for key in ("aggregate_status","missing_price_count",
   "stale_price_count","affected_symbol_count","affected_symbols","coverage_status")})
 report["summary_market_value_present"]=t.get("market_value") is not None
 report["summary_unrealized_pnl_present"]=t.get("unrealized_pnl") is not None
 report["summary_unrealized_return_present"]=t.get("unrealized_return") is not None
 report["summary_keys"]=sorted(t)
print(json.dumps(report,sort_keys=True,default=str))
"""
def main():
    q=json.loads(REQUEST.read_text())
    if not(q.get("intent")=="read-only-aggregate-after-owner-mart" and
           q.get("approved") is True and q.get("environment")=="dev" and
           q.get("no_ledger_mutation") is True and q.get("no_mart_mutation") is True and
           q.get("source_job_run")=="38730741579" and
           q.get("recovery_run")=="38732315439"):
        raise ValueError("read_only_scope_invalid")
    job=r.job("janus-private-pipeline")
    if r.image(job)!=IMAGE:raise ValueError("actual_live_private_image_drift")
    if r.scheduler()["state"]!="ENABLED":raise ValueError("scheduler_not_enabled")
    r.fence()
    r.command(r.LEASE+["acquire"])
    r.fence()
    c=job["template"]["template"]["containers"][0]
    if c.get("command") not in (None,[],["python"]):
        raise ValueError("entrypoint_drift_retain_lease")
    args=["-c",CODE] if c.get("command")==["python"] else ["python","-c",CODE]
    override={"args":args,"env":[]}
    if c.get("name"):override["name"]=c["name"]
    result=r.cloud(r.ROOT+"/jobs/janus-private-pipeline:run",{
     "etag":job["etag"],"overrides":{"taskCount":1,"timeout":"900s",
     "containerOverrides":[override]}},"POST")
    op=result.get("name","")
    if not isinstance(op,str) or not op.startswith(r.ROOT+"/operations/"):
        raise RuntimeError("read_only_dispatch_unknown_retain_lease")
    RECEIPT.write_text(json.dumps({"status":"DISPATCHED_UNKNOWN","operation":op.split("/")[-1],
      "no_data_mutation":True},sort_keys=True))
    end=time.monotonic()+1020
    while not result.get("done") and time.monotonic()<end:
        time.sleep(7)
        result=r.cloud(op)
    if not result.get("done") or result.get("error"):
        raise RuntimeError("read_only_execution_failed_or_unknown_retain_lease")
    execution=result.get("response") or {}
    ex_name=str(execution.get("name") or "")
    if ex_name.startswith(r.ROOT+"/jobs/janus-private-pipeline/executions/"):
        execution=r.cloud(ex_name)
    if not r.terminal(execution) or execution.get("succeededCount")!=1 or execution.get("failedCount",0)!=0:
        raise RuntimeError("read_only_not_proven_success_retain_lease")
    execution_name=str(execution.get("name","")).rsplit("/",1)[-1]
    filters=('resource.type="cloud_run_job" AND resource.labels.job_name="janus-private-pipeline" '
             'AND timestamp>="2026-10-15T12:00:00Z"')
    logs=subprocess.run(["gcloud","logging","read",filters,
      "--project=gen-lang-client-0593591102","--format=json","--limit=250"],
      capture_output=True,text=True,timeout=60,check=True)
    payloads=[]
    for event in json.loads(logs.stdout):
        labels=event.get("labels") or {}
        resource=(event.get("resource") or {}).get("labels") or {}
        if labels.get("run.googleapis.com/execution_name")!=execution_name and resource.get("execution_name")!=execution_name:
            continue
        for value in (event.get("textPayload"),event.get("jsonPayload")):
            if isinstance(value,str):
                try: payloads.append(json.loads(value))
                except ValueError:pass
            elif isinstance(value,dict):payloads.append(value)
    findings=[x for x in payloads if isinstance(x,dict) and x.get("scope")=="p0_owner_aggregate_metadata_only"]
    if len(findings)!=1:
        raise RuntimeError("sanitized_read_only_receipt_not_available_retain_lease")
    verified=findings[0]
    if verified.get("no_data_mutation") is not True:raise RuntimeError("read_only_contract_failed_retain_lease")
    r.fence()
    r.command(r.LEASE+["release","--safe-to-release"])
    RECEIPT.write_text(json.dumps({"status":"PASS_READ_ONLY","execution":execution_name,
      "owner_aggregate_metadata":verified,"no_data_mutation":True},sort_keys=True))
    print(json.dumps({"status":"PASS_READ_ONLY","execution":execution_name,
      "owner_aggregate_metadata":verified,"no_data_mutation":True},sort_keys=True))
if __name__=="__main__":main()
