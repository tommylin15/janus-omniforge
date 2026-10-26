"""SEQ-08: bounded PostgreSQL product readback via one existing Dev Mart Job.

Requires an explicit exact execution ID from a successful real Mart receipt.
One Cloud Run override runs only SELECT under a read-only transaction; prints
aggregate model role statuses and explicitly requested public stock flags.
Never emits credentials, private symbol lists, holdings, prices or payload JSON.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import ghcr_jobs_rollout as jobs

PREFIX="SEQ08_PG_PROOF:"
PROJECT="gen-lang-client-0593591102"
JOB="janus-intelligence-mart"
SOURCE_PATTERN=re.compile(r"^[a-f0-9]{40}$")
EXEC_PATTERN=re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
ROLE_NAMES=("quant","risk","fundamental","valuation")

PROBE=r'''
import json, os, psycopg
from collections import Counter
from packages.postgres_bundle import load_postgres_bundle
from intelligence_mart.runtime import _settings
uid=os.environ["SEQ08_PROOF_MART_EXECUTION"]
load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {
    "CATALOG_DB_PASSWORD":("mart_catalog_password","catalog_password"),
    "PUBLICATION_DB_PASSWORD":("mart_publication_password","publication_password")})
settings=_settings("PUBLICATION_DB")
with psycopg.connect(host=settings["host"],dbname=settings["name"],user=settings["user"],
                     password=settings["password"],sslmode=os.getenv("PUBLICATION_DB_SSLMODE","require"),
                     connect_timeout=8) as db:
    with db.transaction():
        db.execute("SET TRANSACTION READ ONLY")
        db.execute("SET LOCAL statement_timeout='25000ms'")
        with db.cursor() as cur:
            cur.execute("""SELECT symbol,payload_json->'four_model_serving'
                           FROM private.specialist_product
                           WHERE execution_id=%s""",(uid,))
            rows=cur.fetchall()
            statuses={r:Counter() for r in ("quant","risk","fundamental","valuation")}
            missing_serving=0
            for symbol,item in rows:
                if isinstance(item,str): item=json.loads(item)
                if not isinstance(item,dict):
                    missing_serving+=1
                    continue
                for role in statuses:
                    status=item.get(role,{}).get("status","MISSING_STATUS")
                    statuses[role][status]+=1
            cur.execute("""SELECT symbol,MAX(analysis_as_of) FROM private.specialist_product
                           WHERE symbol IN ('2330','2882') GROUP BY symbol""")
            public_samples={str(s):str(d) for s,d in cur.fetchall()}
proof={"status":"PG_SELECT_READBACK_PASS","mart_execution_id":uid,
       "rows":len(rows),"missing_serving":missing_serving,
       "status_counts":{k:dict(v) for k,v in statuses.items()},
       "public_samples_present":{code:code in public_samples for code in ("2330","2882")},
       "owner_login_ui":"NOT_VERIFIED","private_symbols_exposed":False}

# Public-only independent 2330/2882 model feature/probability spot check.
# Use the exact existing CURRENT Core manifest and an in-memory inference
# cache: reading weights is allowed, persisting anything to GCS is not.
try:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from urllib.parse import urlparse
    from ingestion_core.stage import GcsObjectStore
    from intelligence_mart.specialist_runtime import latest_training_input
    from intelligence_mart.analytics_reader import IcebergSnapshotReader
    from intelligence_mart.analyst_inputs import bounded_inputs,build
    from intelligence_mart.specialists import DEPENDENCIES
    from intelligence_mart.storage import sql_catalog_from_environment
    from intelligence_mart.seq08_native_serving import Session

    today=datetime.now(ZoneInfo("Asia/Taipei")).date()
    dev_core=GcsObjectStore("gen-lang-client-0593591102-dev-core")
    event=latest_training_input(dev_core,today)
    uri=urlparse(event["coreSnapshotUri"])
    if uri.scheme!="gs" or uri.netloc!=dev_core.bucket:
        raise ValueError("unexpected_core_manifest_uri")
    core=json.loads(dev_core.read(uri.path.lstrip("/")))
    asof=event["analysisAsOf"]; snapshot=event["coreSnapshotId"]
    required={name for names in DEPENDENCIES.values() for name in names}
    tables={name:fence for name,fence in core.get("iceberg_tables",{}).items()
            if name in {"core."+kind+"_v1" for kind in required}}
    inputs=dict(core,iceberg_tables=tables)
    if "datasets" in core:
        inputs["datasets"]={name:rows for name,rows in core["datasets"].items()
                            if name in required}
    reader=IcebergSnapshotReader(sql_catalog_from_environment(),date_bounds=bounded_inputs(core,asof))
    try:
        stock_data=reader.read(inputs,("2330","2882"),core_snapshot_id=snapshot,row_limit=240000)
    finally:
        reader.close()
    with psycopg.connect(host=settings["host"],dbname=settings["name"],user=settings["user"],
                         password=settings["password"],sslmode=os.getenv("PUBLICATION_DB_SSLMODE","require"),
                         connect_timeout=8) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout='25000ms'")
            with conn.cursor() as cur:
                cur.execute("""SELECT symbol,payload_json->'seq08_quant_rank'
                            FROM private.market_screening_product
                            WHERE analysis_as_of=%s AND core_snapshot_id=%s
                              AND symbol=ANY(%s)""",(asof,snapshot,["2330","2882"]))
                ranks={}
                for sym,val in cur.fetchall():
                    if isinstance(val,str):val=json.loads(val)
                    if isinstance(val,dict):ranks[str(sym)]=val
    with psycopg.connect(host=settings["host"],dbname=settings["name"],user=settings["user"],
                         password=settings["password"],sslmode=os.getenv("PUBLICATION_DB_SSLMODE","require"),
                         connect_timeout=8) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout='25000ms'")
            with conn.cursor() as cur:
                cur.execute("""SELECT COUNT(*),
                                 COUNT(*) FILTER (WHERE jsonb_typeof(payload_json->'seq08_quant_rank')='object'),
                             COUNT(*) FILTER (WHERE jsonb_typeof(payload_json->'seq08_quant_rank')='null'),
                                 COUNT(*) FILTER (WHERE payload_json->>'latest_trade_date'=
                                     (SELECT MAX(payload_json->>'latest_trade_date')
                                      FROM private.market_screening_product
                                      WHERE analysis_as_of=%s AND core_snapshot_id=%s)),
                                 MAX(payload_json->>'latest_trade_date')
                               FROM private.market_screening_product
                               WHERE analysis_as_of=%s AND core_snapshot_id=%s""",
                            (asof,snapshot,asof,snapshot))
                total,ranked,json_null_count,on_latest,latest_day=cur.fetchone()
                cur.execute("""SELECT symbol,payload_json->>'latest_trade_date',
                                      jsonb_typeof(payload_json->'seq08_quant_rank')='object'
                               FROM private.market_screening_product
                               WHERE analysis_as_of=%s AND core_snapshot_id=%s
                                     AND symbol=ANY(%s)""",
                            (asof,snapshot,["2330","2882"]))
                requested_public_screening={
                    str(symbol):{"present":True,"latest_trade_date":latest,
                                 "rank_present":rank_ready}
                    for symbol,latest,rank_ready in cur.fetchall()}
    proof["public_screening_membership"]={
        stock:requested_public_screening.get(stock,{"present":False,"rank_present":False})
        for stock in ("2330","2882")}
    proof["full_market_screening_counts"]={
        "analysis_as_of":asof,"core_snapshot_id":snapshot,
        "screening_rows":int(total),"ranked_rows":int(ranked),
        "json_null_rank_count":int(json_null_count),
        "latest_session_row_count":int(on_latest),
        "latest_trade_date":latest_day,
        "private_symbols_exposed":False}
    # Recompute only the two explicitly requested public stocks' *input*
    # gates with deployed source; never infer full-market percentiles from 2 stocks.
    from intelligence_mart.market_screening import market_features
    from intelligence_mart.specialists import validated_inputs,price_series
    public_market_gates={}
    for public_symbol in ("2330","2882"):
        raw_price_rows=[row for row in stock_data.datasets.get("ohlcv",())
                        if str(row.get("symbol"))==public_symbol]
        try:
            feature_row=market_features(stock_data.datasets,(public_symbol,),
                                        asof,snapshot,rank=False)[0]
            valid,_,rejected=validated_inputs(stock_data.datasets,public_symbol,asof,snapshot)
            accepted_prices=price_series(valid.get("ohlcv",()))
            benchmark_dates=sorted({str(row.get("trade_date",""))[:10]
                                    for row in valid.get("benchmark",())
                                    if row.get("trade_date")})
            public_market_gates[public_symbol]={
                "gate":feature_row.get("seq08_quant_rank_gate"),
                "latest_trade_date":feature_row.get("latest_trade_date"),
                "core_ohlcv_rows":len(raw_price_rows),
                "accepted_stock_sessions":len(accepted_prices),
                "accepted_all_benchmark_sessions":len(benchmark_dates),
                "latest_accepted_benchmark_session":benchmark_dates[-1] if benchmark_dates else None,
                "rejected_evidence_count":len(rejected),
                "read_only":True}
        except (KeyError,ValueError,TypeError) as gate_error:
            public_market_gates[public_symbol]={
                "status":"BLOCKED","reason_type":type(gate_error).__name__}
    proof["public_market_rank_input_gates"]=public_market_gates
    analyst=build(stock_data.datasets,("2330","2882"),asof,snapshot,market_rank=ranks)
    class LocalOnlyCache:
        def __init__(self,bucket):
            self.backing=GcsObjectStore(bucket);self.pending={}
        def read(self,name):
            return self.pending[name] if name in self.pending else self.backing.read(name)
        def create(self,name,raw,mime):
            self.pending[name]=raw
            return True
    bucket="gen-lang-client-0593591102-dev-mart"
    predictions=Session(LocalOnlyCache(bucket),bucket).run(analyst)
    public={}
    for row in predictions["rows"]:
        public[row["symbol"]]={role:{"status":info["status"],
                                     "prediction":info.get("prediction"),
                                     "input_as_of":info.get("input_as_of"),
                                     "missing_features":info.get("missing_features",[]),
                                     "reasons":info.get("reasons",[])}
                               for role,info in row["roles"].items()}
    proof["public_model_spotcheck"]={
        "analysis_as_of":asof,"core_snapshot_id":snapshot,
        "target_symbols":["2330","2882"],"rows":public,
        "independent_of_owner_portfolio":True,
        "full_market_rank_count":len(ranks),"gcs_persistent_writes":0}

except Exception as public_error:
    proof["public_model_spotcheck"]={
        "status":"NOT_VERIFIED",
        "reason_type":type(public_error).__name__,
        "target_symbols":["2330","2882"],
        "independent_of_owner_portfolio":True,
        "gcs_persistent_writes":0}
print("SEQ08_PG_PROOF:"+json.dumps(proof,sort_keys=True),flush=True)
'''


def request():
    data=json.loads(Path("ops/seq08-pg-readback-request.json").read_text())
    if (data.get("intent")!="seq08-one-existing-dev-pg-readonly"
        or data.get("approved") is not True
        or data.get("scope")!="existing-dev-mart-one-select-execution"
        or data.get("no_pg_mutation") is not True
        or data.get("no_owner_mutation") is not True
        or data.get("no_new_resources") is not True
        or data.get("one_job_execution") is not True
        or not SOURCE_PATTERN.fullmatch(str(data.get("source_sha","")))
        or not EXEC_PATTERN.fullmatch(str(data.get("mart_execution_id","")))
        or os.getenv("GITHUB_RUN_ATTEMPT","1")!="1"):
        raise ValueError("seq08_pg_probe_request_invalid")
    return data


def parse_log(entries, operation_id):
    hits=[]
    for item in entries:
        blob=item.get("textPayload","")
        if PREFIX not in blob:
            continue
        try:
            result=json.loads(blob.split(PREFIX,1)[1].strip())
        except ValueError:
            continue
        if (result.get("mart_execution_id")==operation_id
                and result.get("status")=="PG_SELECT_READBACK_PASS"
                and result.get("private_symbols_exposed") is False):
            hits.append(result)
    if len(hits)!=1:
        raise ValueError("seq08_exact_pg_log_receipt_missing_or_ambiguous")
    return hits[0]


def main():
    file=Path("/tmp/seq08-pg-product-proof.json")
    phase="PREFLIGHT"
    maybe_dispatched=False
    try:
        req=request()
        job=jobs.job(JOB)
        ref=jobs.image(job)
        if "@sha256:" not in ref:
            raise ValueError("seq08_pg_probe_unpinned_job")
        # The Cloud Run container exposes the exact current immutable version.
        marker=jobs.command(["skopeo","inspect","--no-creds","docker://"+ref])
        data=json.loads(marker)
        if data.get("Labels",{}).get("org.opencontainers.image.revision")!=req["source_sha"]:
            raise ValueError("seq08_pg_probe_source_version_drift")
        jobs.wait_for_terminal_executions(timeout=400)
        job=jobs.job(JOB)
        if jobs.image(job)!=ref:
            raise ValueError("seq08_pg_probe_image_changed")
        container=job["template"]["template"]["containers"][0]
        if container.get("command") not in (None,["python"]):
            raise ValueError("seq08_pg_probe_entrypoint_unknown")
        override={"args":(["python"] if not container.get("command") else []) + ["-c",PROBE],
                  "env":[{"name":"SEQ08_PROOF_MART_EXECUTION","value":req["mart_execution_id"]}]}
        if container.get("name"): override["name"]=container["name"]
        phase="DISPATCH_UNKNOWN_DO_NOT_RETRY"
        file.write_text(json.dumps({"phase":phase,"maybe_dispatched":True}))
        maybe_dispatched=True
        op=jobs.cloud(f"{jobs.ROOT}/jobs/{JOB}:run",{"etag":job["etag"],
            "overrides":{"taskCount":1,"timeout":"240s","containerOverrides":[override]}},"POST")
        name=op.get("name","")
        if not name.startswith(jobs.ROOT+"/operations/"):
            raise ValueError("seq08_pg_probe_op_identity_unknown")
        deadline=time.monotonic()+320
        while not op.get("done") and time.monotonic()<deadline:
            time.sleep(6)
            op=jobs.cloud(name)
        if not op.get("done") or op.get("error"):
            raise ValueError("seq08_pg_probe_not_successful_or_unknown")
        result=op.get("response",{})
        if (not jobs.terminal(result) or result.get("succeededCount")!=1
                or result.get("failedCount",0)):
            raise ValueError("seq08_pg_probe_execution_not_pass")
        execution=result.get("name","").rsplit("/",1)[-1]
        if not re.fullmatch(r"janus-intelligence-mart-[a-z0-9-]+",execution):
            raise ValueError("seq08_pg_probe_execution_identity_invalid")
        phase="LOG_READBACK"
        query=('resource.type="cloud_run_job" AND '
               'labels."run.googleapis.com/execution_name"="'+execution+'"')
        for _ in range(4):
            cp=subprocess.run(["gcloud","logging","read",query,"--project="+PROJECT,
                              "--limit=150","--format=json"],capture_output=True,timeout=75)
            if cp.returncode:
                raise ValueError("seq08_pg_probe_log_read_denied")
            try:
                proof=parse_log(json.loads(cp.stdout),req["mart_execution_id"])
                proof["cloud_run_execution"]=execution
                proof["gcp_job_executions"]=1
                file.write_text(json.dumps(proof,sort_keys=True))
                print(json.dumps(proof,sort_keys=True))
                return
            except ValueError as error:
                if str(error)!="seq08_exact_pg_log_receipt_missing_or_ambiguous":
                    raise
            time.sleep(5)
        raise ValueError("seq08_pg_probe_log_receipt_not_found")
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) else type(error).__name__
        if not re.fullmatch("[a-z][a-z0-9_]{3,100}",code):code=type(error).__name__
        fail={"status":"BLOCKED","phase":phase,"reason":code,
              "may_have_dispatched":maybe_dispatched,"pg_mutations":0}
        file.write_text(json.dumps(fail,sort_keys=True))
        print(json.dumps(fail,sort_keys=True))
        sys.exit(78)


if __name__=="__main__":
    main()
