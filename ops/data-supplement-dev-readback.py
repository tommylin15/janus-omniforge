"""Pinned dev supplement readback: no model calls, mutations or raw values."""
import json
from datetime import date
from hashlib import sha256
from ingestion_core.stage import GcsObjectStore
from intelligence_mart.storage import load_core_datasets, sql_catalog_from_environment
from intelligence_mart.analysis import analyze, prompt_bundle, _research_rows, _features, _evidence_id, evidence_from_rows, validate_evidence
from packages.postgres_bundle import load_postgres_bundle
load_postgres_bundle("JANUS_MART_POSTGRES_BUNDLE", {"CATALOG_DB_PASSWORD":("mart_catalog_password","catalog_password"),"PUBLICATION_DB_PASSWORD":("mart_publication_password","publication_password")})
raw=GcsObjectStore("gen-lang-client-0593591102-dev-core").read("executions/537276d9-f4bb-4df9-8d9a-5ae449b5d981/core-snapshot.json")
manifest=json.loads(raw)
assert manifest["snapshot_id"]=="sha256:cb5a66d91253699dbc66930a3fbfb6d0f496255ae3b8ef0112398afb73335e09"
catalog=sql_catalog_from_environment()
symbols=("1102","2327","2330","4958","5876")
datasets=load_core_datasets(catalog,manifest,symbols)
result={"operation":"supplement_feature_readback","model_calls":0,"writes":0,"feature_version":"2","core_manifest_hash":"sha256:"+sha256(raw).hexdigest(),"snapshots":{k:str(v) for k,v in manifest.get("iceberg_tables",{}).items()},"symbols":{}}
for symbol in symbols:
 scoped={k:[r for r in rows if not r.get("symbol") or r["symbol"]==symbol] for k,rows in datasets.items()}
 selected=_research_rows(scoped,date(2026,10,3))
 valid,rejected,blockers=validate_evidence(evidence_from_rows(selected,manifest["snapshot_id"]),date(2026,10,3))
 ids={r["evidence_id"] for r in valid}
 qualified={k:[r for r in rows if _evidence_id(k,r,manifest["snapshot_id"]) in ids] for k,rows in selected.items()}
 f=_features(qualified,feature_version="2")
 financial=qualified.get("financials",[])
 result["symbols"][symbol]={"quarters":len({(r.get("fiscal_year"),r.get("fiscal_quarter")) for r in financial if r.get("statement_type")!="monthly_revenue"}),"months":len({(r.get("fiscal_year"),r.get("fiscal_month")) for r in financial if r.get("statement_type")=="monthly_revenue"}),"price_dates":len({str(r["trade_date"]) for r in qualified.get("ohlcv",[])}),"feature_presence":{role:{key:value is not None for key,value in values.items() if not isinstance(value,(list,dict))} for role,values in f.items()},"event_risk_score":__import__("intelligence_mart.analysis",fromlist=["_role"])._role("event_risk",f,[])["score"],"financial_metric_period_counts":{metric:len({(r["fiscal_year"],r["fiscal_quarter"]) for r in financial if r.get("metric")==metric}) for metric in {r.get("metric") for r in financial}},"rejected_count":len(rejected),"blockers":blockers}
import os
import psycopg
from intelligence_mart.runtime import _validate_fact_packs
with psycopg.connect(host=os.environ["PUBLICATION_DB_HOST"],dbname=os.environ["PUBLICATION_DB_NAME"],user=os.environ["PUBLICATION_DB_USER"],password=os.environ["PUBLICATION_DB_PASSWORD"],sslmode="require",connect_timeout=5,options="-c default_transaction_read_only=on -c statement_timeout=15000") as connection:
 options,requested=connection.execute("SELECT request_options,requested_symbols FROM control.executions WHERE execution_id=%s",("9283354c-aaca-5f46-a7b0-01dbb824e298",)).fetchone()
assert options["feature_version"]=="2" and options["core_snapshot_id"]==manifest["snapshot_id"]
assert options["core_snapshot_hash"]=="sha256:"+sha256(raw).hexdigest()
prompts,prompt_hash=prompt_bundle()
reports=analyze(execution_id="9283354c-aaca-5f46-a7b0-01dbb824e298",analysis_as_of=options["analysis_as_of"],core_snapshot_id=manifest["snapshot_id"],requested_symbols=tuple(requested),options=options,datasets=datasets,prompts=prompts,prompt_hash=prompt_hash)
result["fact_packs"]=_validate_fact_packs(reports)
result["fact_pack_hashes"]={report["scope"]["id"]:[pack["fact_pack_hash"] for pack in report["fact_packs"]] for report in reports}
print(json.dumps(result,default=str))
catalog.engine.dispose()

