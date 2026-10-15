#!/usr/bin/env python3
"""P0 official TPEx exact-day price restore and one-owner derived Mart acceptance.

Public close is retrieved over HTTPS on the GitHub runner, not supplied by a
caller. Only one instrument and one historic day, no private ledger event write.
Cloud Run receives a signed-in-GHA verified public record through execution
override and recomputes the existing owner's derived Mart under shared fence.
"""
from __future__ import annotations
from datetime import date, datetime
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as r
from services.api.intraday_quotes import TAIPEI
from services.api.tpex_quotes import (
    TPEX_OFFICIAL_DATED_URL, _official_day, parse_tpex_daily_quote_history,
)

REQUEST=Path("ops/p0-tpex-asof-owner-acceptance.json")
JOB="janus-private-pipeline"
OUT=Path("/tmp/p0-tpex-asof-owner-acceptance.json")
OWNER_CODE=r"""
import json,os
from datetime import date,datetime
from decimal import Decimal
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import repository_from_env
from services.api.private_pipeline import CorePriceReader,PrivatePipeline,owner_price_reader,resolve_valuation_date
from services.api.store import PrivateIcebergStore
from services.api.tpex_quotes import parse_tpex_daily_quote_history
from services.api.intraday_quotes import TAIPEI
raw=json.loads(os.environ["JANUS_P0_TPEX_VERIFIED_EOD"])
symbol="00697B"
target=date(2026,10,14)
now=datetime.now(TAIPEI)
assert now.date()>=target and (now.date()-target).days<=7,"out_of_bounded_official_date"
history=parse_tpex_daily_quote_history([raw],{symbol},now)
assert len(history.get(symbol,[]))==1 and history[symbol][0]["price_date"]==target.isoformat(),"official_date_not_verified"
load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE",{
 "PRIVATE_DATABASE_URL":("pipeline_database_url","database_url"),
 "MOBILE_LEDGER_DATABASE_URL":"database_url",
 "PRIVATE_CATALOG_PASSWORD":("pipeline_catalog_password","catalog_password"),
 "CORE_CATALOG_PASSWORD":"core_catalog_password",
})
repo=repository_from_env()
identity=repo.stock_identities({symbol}).get(symbol)
if not identity or identity.get("market")!="TPEX" or identity.get("name")!="元大美債7-10" or identity.get("enabled") is not True:
 raise RuntimeError("official_etf_identity_not_verified")
with repo._connection() as connection:
 owners=connection.execute("SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s AND shares>0",(symbol,)).fetchall()
if len(owners)!=1:raise RuntimeError("owner_scope_not_exactly_one")
owner=owners[0]["user_id"]
before=int(repo.latest_ledger_version(owner))
market=CorePriceReader.from_env()
valuation=resolve_valuation_date(None,market.latest_valuation_date)
if valuation<target:raise RuntimeError("core_valuation_older_than_verified_close")
# Insert-only official price archive. NEVER overwrite the newer last-success quote.
repo.save_official_eod_quotes(history)
stored=repo.official_eod_quotes({symbol},target).get(symbol)
if (not stored or stored["price_date"]!=target.isoformat() or
 stored["record_sha256"]!=history[symbol][0]["record_sha256"] or
 stored["source_uri"]!=history[symbol][0]["source_uri"] or
 Decimal(stored["price"])!=Decimal(history[symbol][0]["price"])):
 raise RuntimeError("official_persisted_asof_provenance_invalid")
reader=owner_price_reader(repo,market)
with repo._connection() as connection:
 holdings=connection.execute("SELECT DISTINCT symbol FROM private.current_positions WHERE user_id=%s AND shares>0",(owner,)).fetchall()
symbols={row["symbol"] for row in holdings}
if symbol not in symbols or len(symbols)>50:raise RuntimeError("owner_position_scope_invalid")
prices=reader(symbols,valuation)
if symbols-set(prices):raise RuntimeError("owner_full_valuation_coverage_missing")
entry=prices.get(symbol)
if (not isinstance(entry,tuple) or entry[1]>valuation or entry[1]<target or
 entry[0]<=0 or not entry[0].is_finite()):
 raise RuntimeError("official_asof_price_not_eligible")
store=PrivateIcebergStore.from_env()
pipeline=PrivatePipeline(repo,store,reader,market.memberships,
 lambda:resolve_valuation_date(None,market.latest_valuation_date))
pipeline.run_user(owner,valuation,write_guard=repo.private_mart_write_lock)
after=int(repo.latest_ledger_version(owner))
if after!=before:raise RuntimeError("ledger_version_changed_during_mart_write")
positions=store.mart("mart_user_positions",owner)
pnl=store.mart("mart_user_unrealized_pnl",owner)
by_symbol={r.get("symbol"):r for r in positions}
by_pnl={r.get("symbol"):r for r in pnl}
if not symbols.issubset(by_symbol) or not symbols.issubset(by_pnl):
 raise RuntimeError("owner_derived_rows_incomplete")
for name in symbols:
 row,detail=by_symbol[name],by_pnl[name]
 if (row.get("market_price") is None or row.get("market_value") is None or
  detail.get("unrealized_pnl") is None or detail.get("unrealized_return") is None or
  row.get("price_status") not in {"available","stale"} or
  int(row.get("ledger_version") or 0)!=after or
  int(detail.get("ledger_version") or 0)!=after):
  raise RuntimeError("owner_derived_pnl_missing_or_checkpoint_mismatch")
if str(by_symbol[symbol].get("price_date"))!=entry[1].isoformat():
 raise RuntimeError("held_etf_mart_price_day_mismatch")
print(json.dumps({"component":"p0_tpex_asof_owner","status":"PASS",
 "symbol":"00697B","stored_official_day":target.isoformat(),
 "valuation_day":valuation.isoformat(),"used_price_day":entry[1].isoformat(),
 "holding_count":len(symbols),"missing_price_count":0,
 "complete_unrealized_pnl":True,"ledger_version_unchanged":True,
 "official_provenance_persisted":True,"owner_count":1,
 "no_ledger_writes":True},sort_keys=True))
"""

def _read_exact_official(day:date) -> tuple[dict,str]:
    rocyear=day.year-1911
    if rocyear<=0:raise ValueError("non ROC target date")
    session=f"{rocyear:03d}/{day.month:02d}/{day.day:02d}"
    url=TPEX_OFFICIAL_DATED_URL+"?"+urlencode({"l":"zh-tw","o":"json","d":session,"s":"0"})
    headers={"User-Agent":"Mozilla/5.0 (compatible; JanusResearch/1.0)",
             "Accept":"application/json","Accept-Encoding":"identity"}
    with urlopen(Request(url,headers=headers),timeout=20) as response:
        assert response.status==200,"official source response must be HTTP 200"
        body=response.read(12_000_001)
    if len(body)>12_000_000:raise ValueError("official TPEx bounded size")
    data=json.loads(body.decode("utf-8-sig"))
    if not isinstance(data,dict) or _official_day(data.get("date"))!=day:
        raise ValueError("official response date mismatch")
    tables=data.get("tables",[])
    if not isinstance(tables,list) or len(tables)>20:
        raise ValueError("official response schema mismatch")
    found=[]
    for table in tables:
        fields,rows=table.get("fields",[]),table.get("data",[])
        if not isinstance(fields,list) or not isinstance(rows,list) or len(rows)>25000:
            raise ValueError("official response table mismatch")
        for values in rows:
            if not isinstance(values,list) or len(values)!=len(fields):
                continue
            row=dict(zip(fields,values))
            if str(row.get("代號") or "").strip()=="00697B":
                found.append(row)
    if len(found)!=1:raise ValueError("exact official symbol record unavailable")
    item={"Date":session,"SecuritiesCompanyCode":"00697B",
          "Close":found[0].get("收盤"),"_official_source_uri":url}
    history=parse_tpex_daily_quote_history([item],{"00697B"},datetime.now(TAIPEI))
    if len(history.get("00697B",[]))!=1 or history["00697B"][0]["price_date"]!=day.isoformat():
        raise ValueError("official close/date not eligible")
    return item,history["00697B"][0]["record_sha256"]

def main():
    rq=json.loads(REQUEST.read_text())
    if not (rq.get("intent")=="official-one-owner-p0-asof-eod" and
      rq.get("approved") is True and rq.get("symbol")=="00697B" and
      rq.get("trade_date")=="2026-10-14" and rq.get("no_ledger_mutation") is True and
      rq.get("no_job_template_mutation") is True and rq.get("single_owner_only") is True and
      rq.get("private_mart_write_only") is True and
      rq.get("environment")=="dev"):
        raise ValueError("one_owner_scope_not_authorized")
    sha=rq["source_sha"]
    required_image=os.environ["P0_PRIVATE_PIPELINE_IMAGE"]
    if not required_image.startswith("ghcr.io/tommylin15/janus-private-pipeline@sha256:"):
        raise ValueError("immutable_private_pipeline_digest_not_verified")
    job=r.job(JOB)
    if r.image(job)!=required_image:
        raise ValueError("private_pipeline_runtime_sha_drift")
    if r.scheduler()["state"]!="ENABLED":
        raise ValueError("scheduler_not_enabled")
    r.fence()
    # Source retrieved and parsed before any GCP write or lease acquisition.
    item,digest=_read_exact_official(date(2026,10,14))
    OUT.write_text(json.dumps({"status":"SOURCE_VERIFIED_ONLY","source_sha":sha,
        "official_record_hash":digest,"no_ledger_mutation":True},sort_keys=True))
    r.command(r.LEASE+["acquire"])
    r.fence()
    container=job["template"]["template"]["containers"][0]
    cmd=container.get("command")
    if cmd not in (None,[],["python"]):
        raise ValueError("unsupported_job_entrypoint_retain_lease")
    override={"args":(["-c",OWNER_CODE] if cmd==["python"] else ["python","-c",OWNER_CODE]),
              "env":[{"name":"JANUS_P0_TPEX_VERIFIED_EOD","value":json.dumps(item,ensure_ascii=False)}]}
    if container.get("name"):override["name"]=container["name"]
    op=r.cloud(f"{r.ROOT}/jobs/{JOB}:run",{
        "etag":job["etag"],"overrides":{"taskCount":1,"timeout":"900s",
        "containerOverrides":[override]}}, "POST")
    operation=op.get("name","")
    if not isinstance(operation,str) or not operation.startswith(r.ROOT+"/operations/"):
        raise RuntimeError("owner_job_dispatch_unknown_retain_lease")
    OUT.write_text(json.dumps({"status":"DISPATCHED_UNKNOWN","operation":operation.split("/")[-1],
        "source_sha":sha,"official_record_hash":digest,
        "no_ledger_mutation":True},sort_keys=True))
    deadline=time.monotonic()+1100
    while not op.get("done") and time.monotonic()<deadline:
        time.sleep(8)
        op=r.cloud(operation)
    if not op.get("done") or op.get("error"):
        raise RuntimeError("owner_job_not_proven_complete_retain_lease")
    execution=op.get("response") or {}
    if execution.get("name","").startswith(r.ROOT+f"/jobs/{JOB}/executions/"):
        execution=r.cloud(execution["name"])
    if not r.terminal(execution) or execution.get("succeededCount")!=1 or execution.get("failedCount",0)!=0:
        raise RuntimeError("owner_job_no_success_terminal_retain_lease")
    r.fence()
    r.command(r.LEASE+["release","--safe-to-release"])
    OUT.write_text(json.dumps({"status":"PASS_JOB_TERMINAL","source_sha":sha,
       "execution":str(execution["name"]).split("/")[-1],
       "official_record_hash":digest,"no_ledger_mutation":True},sort_keys=True))
    print(json.dumps({"status":"PASS_JOB_TERMINAL","execution":str(execution["name"]).split("/")[-1],
       "source_sha":sha,"no_ledger_mutation":True},sort_keys=True))

if __name__=="__main__":main()
