#!/usr/bin/env python3
"""One-owner Private Mart live acceptance for a real held TPEx ETF.

Runs in the already-deployed private-pipeline container. No plaintext user ID
crosses the GitHub boundary; no ledger events are inserted or altered. This
execution writes only the identified owner's already-authorized Mart projection
under the existing private lock, after an official eligible price is verified.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as rollout

REQUEST = Path("ops/holdings-p0-owner-live-request.json")
EXPECTED_SOURCE = "0b0855c0fdeba0294bb0bb09bf33906216d779fa"
JOB = "janus-private-pipeline"

# Supplied as argv to the existing deployed Python Job, never rendered into logs
# by this runner. It reads the single owner from the real operational positions.
OWNER_CODE = r"""
import json
from datetime import date
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import repository_from_env
from services.api.private_pipeline import CorePriceReader, PrivatePipeline, owner_price_reader, resolve_valuation_date
from services.api.store import PrivateIcebergStore

load_postgres_bundle('JANUS_API_POSTGRES_BUNDLE', {
    'PRIVATE_DATABASE_URL': ('pipeline_database_url', 'database_url'),
    'MOBILE_LEDGER_DATABASE_URL': 'database_url',
    'PRIVATE_CATALOG_PASSWORD': ('pipeline_catalog_password', 'catalog_password'),
    'CORE_CATALOG_PASSWORD': 'core_catalog_password',
})
repo=repository_from_env()
with repo._connection() as connection:
    owners=connection.execute(
        "SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s",
        ('00719B',)
    ).fetchall()
if len(owners)!=1:
    raise RuntimeError('actual_holder_owner_scope_not_exactly_one')
owner=owners[0]['user_id']
market=CorePriceReader.from_env()
valued=resolve_valuation_date(None, market.latest_valuation_date)
price_reader=owner_price_reader(repo,market)
official=price_reader({'00719B'},valued)
entry=official.get('00719B')
if not isinstance(entry,tuple) or len(entry)!=2 or entry[0]<=0 or entry[1]>valued:
    raise RuntimeError('official_00719B_eligible_eod_missing')
with repo._connection() as connection:
    quote=connection.execute(
        "SELECT source,quote_at FROM control.operational_last_quotes WHERE symbol=%s",
        ('00719B',)
    ).fetchone()
if quote is None or quote['source']!='tpex_openapi_eod':
    raise RuntimeError('official_00719B_persisted_source_not_proven')
store=PrivateIcebergStore.from_env()
pipeline=PrivatePipeline(
    repo,store,price_reader,market.memberships,
    lambda: resolve_valuation_date(None,market.latest_valuation_date),
)
result=pipeline.run_user(owner,valued,write_guard=repo.private_mart_write_lock)
positions=store.mart('mart_user_positions',owner)
unrealized=store.mart('mart_user_unrealized_pnl',owner)
matched=[row for row in positions if row.get('symbol')=='00719B']
pnl_matched=[row for row in unrealized if row.get('symbol')=='00719B']
if len(matched)!=1 or len(pnl_matched)!=1:
    raise RuntimeError('owner_00719B_mart_position_or_pnl_missing')
row=matched[0]
pnl_row=pnl_matched[0]
current_version=int(repo.latest_ledger_version(owner))
if (row.get('market_price') is None or row.get('market_value') is None
        or pnl_row.get('unrealized_pnl') is None
        or pnl_row.get('unrealized_return') is None
        or row.get('price_status') not in {'available','stale'}
        or pnl_row.get('price_status') not in {'available','stale'}
        or int(row.get('ledger_version') or 0)!=current_version
        or int(pnl_row.get('ledger_version') or 0)!=current_version):
    raise RuntimeError('owner_00719B_mart_price_pnl_or_checkpoint_invalid')
print(json.dumps({
    'owner_scope':'exactly_one_real_owner',
    'symbol':'00719B',
    'official_price_date':entry[1].isoformat(),
    'valuation_date':valued.isoformat(),
    'mart_checkpoint_current':True,
    'mart_00719B_price_and_unrealized_present':True,
    'status':'PASS',
},sort_keys=True))
"""


def main() -> None:
    request=json.loads(REQUEST.read_text())
    if (request.get("intent")!="real-owner-tpex-mart-reconciliation"
            or request.get("approved") is not True
            or request.get("scope")!="single-owner-holding-00719B"
            or request.get("sha")!=EXPECTED_SOURCE
            or request.get("write_limit")!="private-mart-only"
            or request.get("ledger_mutation") is not False):
        raise ValueError("owner_live_reconciliation_authorization_drift")
    candidate=json.loads(Path("ops/ghcr-candidate-request.json").read_text())
    if candidate.get("sha")!=EXPECTED_SOURCE:
        raise ValueError("existing_deployed_source_mismatch")

    job=rollout.job(JOB)
    container=job["template"]["template"]["containers"][0]
    if len(job["template"]["template"]["containers"])!=1:
        raise ValueError("unexpected_private_job_container_count")
    img=rollout.image(job)
    if not (img.startswith("ghcr.io/tommylin15/janus-private-pipeline@sha256:")
            and len(img.rsplit("sha256:",1)[-1])==64):
        raise ValueError("immutable_private_job_image_required")
    # Existing dev rollout receipt passed; reject a currently active execution
    # rather than racing the scheduled Private Mart with an owner write.
    rollout.fence()
    args=["-c",OWNER_CODE]
    if not container.get("command"):
        args=["python"]+args
    elif container["command"]!=["python"]:
        raise ValueError("unexpected_private_job_entrypoint")
    override={"args":args, "env":[]}
    if container.get("name"):
        override["name"]=container["name"]
    operation=rollout.cloud(f"{rollout.ROOT}/jobs/{JOB}:run",{
        "etag":job["etag"],
        "overrides":{
            "taskCount":1,
            "timeout":"900s",
            "containerOverrides":[override],
        }
    },"POST")
    name=operation.get("name")
    if not isinstance(name,str) or not name.startswith(rollout.ROOT+"/operations/"):
        raise ValueError("private_job_execution_not_returned")
    deadline=time.monotonic()+1050
    while not operation.get("done") and time.monotonic()<deadline:
        time.sleep(8)
        operation=rollout.cloud(name)
    if not operation.get("done") or operation.get("error"):
        raise RuntimeError("owner_mart_execution_failed_or_unknown")
    e=operation.get("response") or {}
    if (not rollout.terminal(e) or e.get("succeededCount")!=1
            or e.get("failedCount",0)!=0):
        raise RuntimeError("owner_mart_execution_not_successful")
    print(json.dumps({
        "owner_mart_live_reconciliation":"PASS",
        "source_sha":EXPECTED_SOURCE,
        "execution":str(e.get("name","")).split("/")[-1],
        "job":JOB,
        "single_owner_only":True,
        "no_ledger_mutation":True,
    },sort_keys=True))


if __name__=="__main__":
    main()
