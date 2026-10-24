#!/usr/bin/env python3
"""RV-03 two-stock bounded Dev reader; no Core/PG mutation, backfill or new service.

Runs a single temporary python -c override on the existing janus-ingestion-core
Job, reads its structured response, and calculates with the checked-out main
RV-03/RV-02 code. No deployed-image match is assumed for new RV-03 code.
"""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from ghcr_jobs_rollout import ROOT, PROJECT, cloud, fingerprint, job, terminal

SYMBOLS = ("2330", "2882")
PREFIX = "JANUS_RV03_EXISTING_FACTS_V1:"
OUT = Path("/tmp/valuation-rv03-live-readback.json")
AS_OF = date(2026, 10, 24)
PROBE = r'''
import calendar, json, os
from collections import defaultdict
from datetime import date, datetime, timezone
from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, LessThanOrEqual
from ingestion_core.__main__ import _iceberg_core, _control_plane

AS_OF=date(2026,10,24)
START=date(2021,11,1)
out={"probe":"JANUS_RV03_EXISTING_FACTS_V1","read_only":True,"as_of":AS_OF.isoformat(),"stocks":[]}
core=None
control=None
def d(value):
    try:return date.fromisoformat(str(value)[:10])
    except (ValueError,TypeError):return None
def safe(row):
    keep=("symbol","observed_date","pe_ratio","pb_ratio","source_id","provenance_id",
          "available_at","source_published_at","first_observed_at")
    return {k:str(row[k]) if not isinstance(row[k],(type(None),str,int,float,bool)) else row[k]
            for k in keep if k in row}
try:
    core=_iceberg_core(os.environ["CORE_BUCKET"],read_only=True)
    control=_control_plane()
    table=core.catalog.load_table(core.table_identifier("valuation"))
    snap=table.current_snapshot()
    if snap is None:raise RuntimeError("valuation_current_snapshot_missing")
    out["core_snapshot_id"]=str(snap.snapshot_id)
    for symbol in ("2330","2882"):
        item={"symbol":symbol,"market":None,"valuation_rows":[],"financial_rows":[],
              "price":None,"price_as_of":None,"core_rows_scanned":0,
              "financial_rows_scanned":0,"sources_authorized":False,
              "status":"UNKNOWN"}
        try:
            with control.connection.cursor() as cursor:
                cursor.execute("SELECT market FROM control.stock_master WHERE symbol=%s AND enabled=true LIMIT 1",
                               (symbol,))
                stock=cursor.fetchone()
                if not stock or str(stock[0]).upper() not in ("TWSE","TPEX"):
                    item["status"]="IDENTITY_MISSING"
                    out["stocks"].append(item)
                    continue
                item["market"]=str(stock[0]).lower()
                cursor.execute(
                    """SELECT payload_json,source_id,provenance_id
                       FROM control.market_serving_recent
                       WHERE dataset_id='financials' AND symbol=%s AND sort_at < %s
                       ORDER BY sort_at DESC LIMIT 301""",
                    (symbol,datetime(2026,10,25,tzinfo=timezone.utc)))
                finances=cursor.fetchall()
                item["financial_rows_scanned"]=len(finances)
                if len(finances)>300:
                    item["status"]="FINANCIAL_SCAN_LIMIT"
                    out["stocks"].append(item)
                    continue
                cursor.execute(
                    """SELECT payload_json,source_id,provenance_id
                       FROM control.stock_serving_recent
                       WHERE dataset_id='ohlcv' AND symbol=%s AND sort_at < %s
                       ORDER BY sort_at DESC LIMIT 1""",
                    (symbol,datetime(2026,10,25,tzinfo=timezone.utc)))
                quote=cursor.fetchone()
            if quote and isinstance(quote[0],dict) and quote[1] in ("twse","tpex") and quote[2]:
                item["price"]=quote[0].get("close")
                item["price_as_of"]=quote[0].get("trade_date")
            for payload,source,provenance in finances:
                if not isinstance(payload,dict):
                    continue
                if payload.get("metric") not in ("eps_single_quarter","bvps","book_value_per_share"):
                    continue
                if payload.get("symbol")!=symbol:
                    continue
                fields=("symbol","metric","fiscal_year","fiscal_quarter",
                        "fiscal_period_end","period_end","value","unit",
                        "period_basis","report_scope","share_basis",
                        "availability_at","published_at","first_observed_at",
                        "source_published_at")
                row={k:payload.get(k) for k in fields}
                row.update(source_id=source,provenance_id=provenance)
                item["financial_rows"].append(row)
            rows=table.scan(
                snapshot_id=snap.snapshot_id,
                row_filter=And(EqualTo("symbol",symbol),
                    GreaterThanOrEqual("observed_date",START),
                    LessThanOrEqual("observed_date",AS_OF)),
                selected_fields=("symbol","observed_date","pe_ratio","pb_ratio",
                                 "source_id","provenance_id"),
                limit=4001).to_arrow().to_pylist()
            item["core_rows_scanned"]=len(rows)
            if len(rows)>4000:
                item["status"]="CORE_SCAN_LIMIT"
                out["stocks"].append(item)
                continue
            bymonth=defaultdict(list)
            for row in rows:
                dt=d(row.get("observed_date"))
                if dt and START<=dt<=AS_OF:
                    bymonth[(dt.year,dt.month)].append(row)
            for key,group in sorted(bymonth.items()):
                # Last *observed* trading session for the month; preserve all
                # latest-date conflicting rows, never synthesize month-end dates.
                last=max(d(r.get("observed_date")) for r in group)
                item["valuation_rows"].extend(safe(r) for r in group
                                             if d(r.get("observed_date"))==last)
            ids={r.get("source_id") for r in item["valuation_rows"]+item["financial_rows"]
                 if r.get("source_id") and r.get("provenance_id")}
            item["source_ids"]=sorted(ids)
            item["sources_authorized"]=bool(ids) and all(
                control.source_is_approved(s) for s in ids)
            item["status"]="READ"
        except Exception as exc:
            item["status"]="BLOCKED_"+type(exc).__name__[:45]
            item["valuation_rows"]=[]
            item["financial_rows"]=[]
        out["stocks"].append(item)
except Exception as exc:
    out["probe_error"]="BLOCKED_"+type(exc).__name__[:45]
finally:
    if core is not None:
        try:core.close()
        except Exception:pass
    if control is not None:
        try:control.close()
        except Exception:pass
print("JANUS_RV03_EXISTING_FACTS_V1:"+json.dumps(out,default=str,
      ensure_ascii=False,sort_keys=True,separators=(",",":")),flush=True)
'''

def request_guard(request: dict) -> None:
    if request != {
        "intent": "rv03-two-stock-existing-dev-readonly",
        "symbols": ["2330", "2882"],
        "as_of": AS_OF.isoformat(),
        "no_data_mutation": True,
        "no_job_template_mutation": True,
        "no_new_resources": True,
        "one_execution": True,
    }:
        raise ValueError("rv03_readback_scope_invalid")


def readback(execution_name: str) -> dict:
    query = ('resource.type="cloud_run_job" AND '
             'labels."run.googleapis.com/execution_name"="' + execution_name + '"')
    for attempt in range(4):
        cp = subprocess.run(
            ["gcloud", "logging", "read", query, "--project=" + PROJECT,
             "--limit=130", "--format=json"],
            capture_output=True, text=True, timeout=55, check=False,
        )
        if cp.returncode != 0:
            raise RuntimeError("rv03_cloud_logging_read_failed")
        for entry in json.loads(cp.stdout):
            log = entry.get("textPayload") or ""
            if PREFIX not in log:
                continue
            payload = log.split(PREFIX, 1)[1].strip()
            try:
                response = json.loads(payload)
            except ValueError:
                continue
            if (response.get("probe")==PREFIX[:-1] and
                    response.get("as_of")==AS_OF.isoformat() and
                    [r.get("symbol") for r in response.get("stocks", [])]==list(SYMBOLS)):
                return response
        time.sleep(3 + attempt)
    raise RuntimeError("rv03_exact_live_receipt_unavailable")


def main() -> None:
    request_guard(json.loads(Path("ops/valuation-rv03-live-readback.json").read_text()))
    existing = job("janus-ingestion-core")
    before = fingerprint(existing)
    containers = existing["template"]["template"]["containers"]
    if len(containers)!=1 or (containers[0].get("command") or []) not in ([], ["python"]):
        raise ValueError("rv03_job_command_drift")
    override = {
        "args": ["-c", PROBE] if containers[0].get("command") else ["python", "-c", PROBE],
        "env": [{"name": "QUEUE_CONSUMER", "value": "false"}],
    }
    if containers[0].get("name"):
        override["name"]=containers[0]["name"]
    operation = cloud(ROOT+"/jobs/janus-ingestion-core:run", {
        "etag": existing["etag"],
        "overrides": {"taskCount": 1, "timeout": "350s",
                      "containerOverrides": [override]},
    }, "POST")
    op_name=operation.get("name","")
    if not op_name.startswith(ROOT+"/operations/"):
        raise RuntimeError("rv03_operation_identity_missing_do_not_repeat")
    deadline=time.monotonic()+430
    while not operation.get("done") and time.monotonic()<deadline:
        time.sleep(7)
        operation=cloud(op_name)
    if not operation.get("done") or operation.get("error"):
        raise RuntimeError("rv03_operation_not_successful_or_not_terminal")
    execution=operation.get("response") or {}
    if not terminal(execution) or execution.get("succeededCount")!=1 or execution.get("failedCount",0):
        raise RuntimeError("rv03_execution_not_successful")
    name=execution.get("name","").rsplit("/",1)[-1]
    if not re.fullmatch(r"janus-ingestion-core-[a-z0-9-]+",name):
        raise RuntimeError("rv03_execution_name_unexpected")
    receipt=readback(name)
    if before!=fingerprint(job("janus-ingestion-core")):
        raise RuntimeError("rv03_job_template_drift")
    from ingestion_core.valuation_range_inputs import from_existing_rows
    output={"operation":"rv03_two_stock_existing_live",
            "source_git_sha":os.environ.get("GITHUB_SHA"),
            "execution":name,"core_snapshot_id":receipt.get("core_snapshot_id"),
            "read_only":True,"data_mutations":0,"job_template_unchanged":True,
            "symbols":[]}
    for item in receipt["stocks"]:
        summary={"symbol":item["symbol"],"market":item.get("market"),
                 "input_status":item["status"],
                 "core_rows_scanned":item.get("core_rows_scanned"),
                 "serving_financial_rows_scanned":item.get("financial_rows_scanned"),
                 "source_ids":item.get("source_ids"),
                 "sources_authorized":item.get("sources_authorized")}
        if item["status"]=="READ":
            try:
                result=from_existing_rows(
                    symbol=item["symbol"],market=item["market"],
                    security_type="ordinary_stock",
                    is_financial=item["symbol"]=="2882",as_of=AS_OF,
                    valuation_rows=item["valuation_rows"],
                    financial_rows=item["financial_rows"],
                    rights_status="approved" if item["sources_authorized"] else "unknown",
                    price=item.get("price"),price_as_of=item.get("price_as_of"),
                )
                for field in ("status","valid_month_count","basis_type",
                              "financial_period","basis","lower","mid","upper",
                              "excluded_reasons","price_gap_to_reference_mid_pct",
                              "month_end_observation_dates"):
                    summary[field]=result.get(field)
                summary["latest_price_as_of"]=item.get("price_as_of")
                summary["latest_price"]=item.get("price")
            except Exception as exc:
                summary["status"]="BLOCKED_"+type(exc).__name__[:45]
        else:
            summary["status"]=item["status"]
        output["symbols"].append(summary)
    output["status"]="INPUTS_READ" if all(
        s["input_status"]=="READ" for s in output["symbols"]) else "PARTIAL"
    OUT.write_text(json.dumps(output,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    print(json.dumps(output,ensure_ascii=False,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
