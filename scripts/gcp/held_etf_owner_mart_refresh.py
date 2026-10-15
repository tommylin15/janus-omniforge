#!/usr/bin/env python3
"""One bounded real-owner TPEx ETF derived Mart refresh, no user ledger mutation."""
from __future__ import annotations
import json
from pathlib import Path
import time
import ghcr_jobs_rollout as rollout

REQUEST = Path("ops/held-etf-owner-live-request.json")
SOURCE = "536598f2528550fd60c73786597fdf2740860c9e"
IMAGE = "ghcr.io/tommylin15/janus-private-pipeline@sha256:9b33e5fe97457b9d039070078dd36c0ee1785a988b6f74da1fc53de321486b9a"
JOB = "janus-private-pipeline"

# This code runs inside the exact released Job image. It discovers the sole
# holder through private.current_positions without logging the owner key.
# It does not insert, change or reverse any ledger event.
OWNER_CODE = r"""
import json
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import repository_from_env
from services.api.private_pipeline import CorePriceReader, PrivatePipeline, owner_price_reader, resolve_valuation_date
from services.api.store import PrivateIcebergStore
load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
    "PRIVATE_DATABASE_URL": ("pipeline_database_url", "database_url"),
    "MOBILE_LEDGER_DATABASE_URL": "database_url",
    "PRIVATE_CATALOG_PASSWORD": ("pipeline_catalog_password", "catalog_password"),
    "CORE_CATALOG_PASSWORD": "core_catalog_password",
})
repo = repository_from_env()
with repo._connection() as connection:
    owners = connection.execute(
        "SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s", ("00697B",)
    ).fetchall()
if len(owners) != 1:
    raise RuntimeError("held_etf_owner_scope_not_exactly_one")
owner = owners[0]["user_id"]
identity = repo.stock_identities({"00697B"}).get("00697B")
if not identity or identity.get("name") != "元大美債7-10" or identity.get("market") not in {"TPEX","TPEX_UNVERIFIED"} or identity.get("enabled") is not True:
    raise RuntimeError("held_etf_official_identity_not_verified")
before = int(repo.latest_ledger_version(owner))
market = CorePriceReader.from_env()
valuation = resolve_valuation_date(None, market.latest_valuation_date)
reader = owner_price_reader(repo, market)
entry = reader({"00697B"}, valuation).get("00697B")
if not isinstance(entry,tuple) or len(entry) != 2 or not entry[0].is_finite() or entry[0] <= 0 or entry[1] > valuation:
    raise RuntimeError("held_etf_official_eod_missing")
with repo._connection() as connection:
    quote = connection.execute(
        "SELECT source, quote_at FROM control.operational_last_quotes WHERE symbol=%s", ("00697B",)
    ).fetchone()
if quote is None or quote["source"] != "tpex_openapi_eod":
    raise RuntimeError("held_etf_official_persisted_provenance_missing")
store = PrivateIcebergStore.from_env()
pipeline = PrivatePipeline(repo, store, reader, market.memberships,
    lambda: resolve_valuation_date(None, market.latest_valuation_date))
pipeline.run_user(owner, valuation, write_guard=repo.private_mart_write_lock)
after = int(repo.latest_ledger_version(owner))
if before != after:
    raise RuntimeError("owner_ledger_mutated_while_derived_mart_rebuilt")
positions = store.mart("mart_user_positions", owner)
pnl = store.mart("mart_user_unrealized_pnl", owner)
match = [r for r in positions if r.get("symbol")=="00697B"]
pnl_match = [r for r in pnl if r.get("symbol")=="00697B"]
if len(match)!=1 or len(pnl_match)!=1:
    raise RuntimeError("held_etf_private_mart_position_or_pnl_missing")
row, detail = match[0], pnl_match[0]
if (row.get("stock_name")!="元大美債7-10" or
    row.get("market_price") is None or row.get("market_value") is None or
    detail.get("unrealized_pnl") is None or detail.get("unrealized_return") is None or
    row.get("price_status") not in {"available","stale"} or
    str(row.get("price_date")) != entry[1].isoformat() or
    int(row.get("ledger_version") or 0)!=after or
    int(detail.get("ledger_version") or 0)!=after):
    raise RuntimeError("held_etf_private_mart_checkpoint_or_price_invalid")
print(json.dumps({"status":"PASS","symbol":"00697B",
    "official_price_date":entry[1].isoformat(),
    "valuation_date":valuation.isoformat(),
    "owner_count":1,"ledger_version_unchanged":True,
    "private_mart_price_pnl_present":True,
    "no_ledger_mutation":True},sort_keys=True))
"""

def main():
    request=json.loads(REQUEST.read_text())
    if (request.get("intent")!="single-owner-official-held-etf-mart" or
        request.get("approved") is not True or request.get("environment")!="dev" or
        request.get("symbol")!="00697B" or request.get("source_sha")!=SOURCE or
        request.get("no_ledger_mutation") is not True or
        request.get("private_mart_write_only") is not True or
        request.get("single_owner_only") is not True or
        request.get("no_job_template_mutation") is not True):
        raise ValueError("bounded_owner_mart_request_invalid")
    candidate=json.loads(Path("ops/ghcr-candidate-request.json").read_text())
    if candidate["sha"] != SOURCE:
        raise ValueError("candidate_source_drift")
    job=rollout.job(JOB)
    containers=job["template"]["template"]["containers"]
    if len(containers)!=1 or rollout.image(job)!=IMAGE:
        raise ValueError("actual_private_job_image_drift")
    if rollout.scheduler()["state"]!="ENABLED":
        raise ValueError("scheduler_not_enabled")
    rollout.fence()
    rollout.command(rollout.LEASE+["acquire"])
    container=containers[0]
    cmd=container.get("command")
    if cmd not in (None, [], ["python"]):
        raise ValueError("unsupported_private_job_entrypoint_retain_lease")
    args=["-c",OWNER_CODE] if cmd==["python"] else ["python","-c",OWNER_CODE]
    override={"args":args,"env":[]}
    if container.get("name"):
        override["name"]=container["name"]
    receipt=Path("/tmp/held-etf-owner-mart.json")
    outcome={"source_sha":SOURCE,"job":JOB,"symbol":"00697B",
        "status":"UNKNOWN","no_ledger_mutation":True,"job_template_mutation":False}
    receipt.write_text(json.dumps(outcome,sort_keys=True))
    op=rollout.cloud(f"{rollout.ROOT}/jobs/{JOB}:run",{
        "etag":job["etag"],"overrides":{"taskCount":1,"timeout":"900s",
        "containerOverrides":[override]}}, "POST")
    name=op.get("name","")
    if not isinstance(name,str) or not name.startswith(rollout.ROOT+"/operations/"):
        raise RuntimeError("owner_mart_job_operation_unknown_retain_lease")
    deadline=time.monotonic()+1060
    while not op.get("done") and time.monotonic()<deadline:
        time.sleep(8)
        op=rollout.cloud(name)
    if not op.get("done") or op.get("error"):
        raise RuntimeError("owner_mart_job_unknown_or_failed_retain_lease")
    execution=op.get("response") or {}
    if (not rollout.terminal(execution) or execution.get("succeededCount")!=1 or
        execution.get("failedCount",0)!=0):
        raise RuntimeError("owner_mart_job_not_successful_retain_lease")
    outcome.update(status="PASS",execution=str(execution.get("name","")).split("/")[-1],
                   owner_scope="single_real_holder",private_mart_refreshed=True)
    rollout.fence()
    rollout.command(rollout.LEASE+["release","--safe-to-release"])
    receipt.write_text(json.dumps(outcome,sort_keys=True))
    print(json.dumps(outcome,sort_keys=True))

if __name__=="__main__":
    main()
