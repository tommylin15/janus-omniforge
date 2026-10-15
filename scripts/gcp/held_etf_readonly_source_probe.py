#!/usr/bin/env python3
"""Read-only official TPEx/Core/private quote provenance diagnosis in live dev Job.

Do not mutate operational quote tables, market Core, owner ledger or Private Mart.
Use one existing immutable Job with execution-only override and shared lease.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as r

REQUEST=Path("ops/held-etf-readonly-source-probe.json")
SOURCE="536598f2528550fd60c73786597fdf2740860c9e"
IMAGE="ghcr.io/tommylin15/janus-private-pipeline@sha256:9b33e5fe97457b9d039070078dd36c0ee1785a988b6f74da1fc53de321486b9a"
JOB="janus-private-pipeline"
CODE=r"""
import json
from datetime import datetime, date
from services.api.intraday_quotes import TAIPEI
from services.api.tpex_quotes import TpexDailyQuotes, parse_tpex_daily_quotes
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import repository_from_env
from services.api.private_pipeline import CorePriceReader, resolve_valuation_date
data={'scope':'official_00697B_read_only','symbol':'00697B','data_write':False,
      'private_read':'metadata_only_no_owner_id','status':'READ_ONLY_OBSERVED'}
now=datetime.now(TAIPEI)
data['taipei_day']=now.date().isoformat()
try:
    official=TpexDailyQuotes()._download()
    data['official_document_kind']=type(official).__name__
    data['official_row_count']=len(official) if isinstance(official,list) else None
    parsed=parse_tpex_daily_quotes(official,{'00697B'},now)
    data['official_parse_eligible']='00697B' in parsed
    data['official_price_date']=parsed.get('00697B',{}).get('price_date')
except Exception as e:
    data['official_error_type']=type(e).__name__
load_postgres_bundle('JANUS_API_POSTGRES_BUNDLE',{
 'PRIVATE_DATABASE_URL':('pipeline_database_url','database_url'),
 'MOBILE_LEDGER_DATABASE_URL':'database_url',
 'PRIVATE_CATALOG_PASSWORD':('pipeline_catalog_password','catalog_password'),
 'CORE_CATALOG_PASSWORD':'core_catalog_password',
})
repo=repository_from_env()
try:
    identity=repo.stock_identities({'00697B'}).get('00697B',{})
    data['identity_market']=identity.get('market')
    data['identity_enabled']=identity.get('enabled')
    data['identity_present']=bool(identity)
except Exception as e:data['identity_error_type']=type(e).__name__
try:
    row=repo.last_quotes({'00697B':{}}).get('00697B',{})
    data['last_quote_present']=bool(row)
    data['last_quote_source']=row.get('source')
    data['last_quote_day']=str(row.get('quote_at') or '')[:10] or None
except Exception as e:data['last_quote_error_type']=type(e).__name__
try:
    core=CorePriceReader.from_env()
    valuation=resolve_valuation_date(None,core.latest_valuation_date)
    data['core_valuation_day']=valuation.isoformat()
    matched=core({'00697B'},valuation).get('00697B')
    data['core_symbol_available']=matched is not None
    data['core_symbol_day']=matched[1].isoformat() if matched else None
except Exception as e:data['core_error_type']=type(e).__name__
print(json.dumps(data,sort_keys=True))
"""
def main():
    q=json.loads(REQUEST.read_text())
    if not(q.get("intent")=="read-only-held-etf-official-runtime-probe" and
      q.get("approved") is True and q.get("no_data_write") is True and
      q.get("no_job_template_change") is True and q.get("source_sha")==SOURCE and
      q.get("previous_jobs_rollout_run")=="38692371269"):
        raise ValueError("read_only_scope_drift")
    r.fence()
    if r.scheduler().get("state")!="ENABLED":
        raise ValueError("scheduler_not_enabled")
    j=r.job(JOB)
    if r.image(j)!=IMAGE:
        raise ValueError("live_immutable_job_image_drift")
    r.command(r.LEASE+["acquire"])
    r.fence()
    container=j["template"]["template"]["containers"][0]
    cmd=container.get("command")
    if cmd not in (None,[],["python"]):raise ValueError("unsupported_entrypoint_retain_lease")
    args=["-c",CODE] if cmd==["python"] else ["python","-c",CODE]
    override={"args":args,"env":[]}
    if container.get("name"): override["name"]=container["name"]
    receipt=Path("/tmp/held-etf-readonly-source-probe.json")
    outcome={"status":"UNKNOWN","no_data_write":True,"symbol":"00697B","source_sha":SOURCE}
    receipt.write_text(json.dumps(outcome))
    op=r.cloud(f"{r.ROOT}/jobs/{JOB}:run",{
     "etag":j["etag"],"overrides":{"taskCount":1,"timeout":"900s",
     "containerOverrides":[override]}}, "POST")
    name=op.get("name","")
    if not isinstance(name,str) or not name.startswith(r.ROOT+"/operations/"):
        raise RuntimeError("read_only_execution_unknown_retain_lease")
    end=time.monotonic()+1050
    while not op.get("done") and time.monotonic()<end:
        time.sleep(8)
        op=r.cloud(name)
    if not op.get("done") or op.get("error"):
        raise RuntimeError("read_only_job_failed_or_unknown_retain_lease")
    e=op.get("response",{})
    if e.get("name","").startswith(r.ROOT+f"/jobs/{JOB}/executions/"):
        e=r.cloud(e["name"])
    if not r.terminal(e) or e.get("succeededCount")!=1 or e.get("failedCount",0)!=0:
        raise RuntimeError("read_only_job_not_terminal_success_retain_lease")
    r.fence()
    r.command(r.LEASE+["release","--safe-to-release"])
    outcome.update(status="PASS_READ_ONLY",execution=str(e["name"]).split("/")[-1])
    receipt.write_text(json.dumps(outcome,sort_keys=True))
    print(json.dumps(outcome,sort_keys=True))
if __name__=="__main__":main()
