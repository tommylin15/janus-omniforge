#!/usr/bin/env python3
"""Bounded read-only diagnostics for actual 00719B owner, no financial figures.

Uses existing immutable janus-private-pipeline Cloud Run Job with one override
task. Does not write/recalculate or expose owner identity, shares or prices.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as cloud

REQ=Path("ops/holdings-p0-mart-check-request.json")
SOURCE="0b0855c0fdeba0294bb0bb09bf33906216d779fa"
JOB="janus-private-pipeline"
CODE=r"""
import json
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import repository_from_env
from services.api.store import PrivateIcebergStore
from services.api.private_pipeline import CorePriceReader, resolve_valuation_date

load_postgres_bundle('JANUS_API_POSTGRES_BUNDLE',{
    'PRIVATE_DATABASE_URL':('pipeline_database_url','database_url'),
    'PRIVATE_CATALOG_PASSWORD':('pipeline_catalog_password','catalog_password'),
    'CORE_CATALOG_PASSWORD':'core_catalog_password',
})
repo=repository_from_env()
with repo._connection() as c:
    owners=c.execute(
        'SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s',
        ('00719B',)
    ).fetchall()
if len(owners)!=1:
    raise RuntimeError('owner_scope_not_exactly_one')
owner=owners[0]['user_id']
version=int(repo.latest_ledger_version(owner))
market=CorePriceReader.from_env()
day=resolve_valuation_date(None,market.latest_valuation_date)
store=PrivateIcebergStore.from_env()
result={'read_only':True,'symbol':'00719B','one_owner':True,
        'valuation_date':day.isoformat(),'tables':{}}
for table in ('mart_user_positions','mart_user_unrealized_pnl','mart_user_portfolio_summary'):
    rows=store.mart(table,owner)
    if table!='mart_user_portfolio_summary':
        selected=[x for x in rows if x.get('symbol')=='00719B']
    else:
        selected=rows
    report={'selected_count':len(selected),'total_count':len(rows)}
    if table!='mart_user_portfolio_summary' and selected:
        row=selected[0]
        for field in (('market_price','market_value','shares','average_cost','price_status',
                       'price_date','ledger_version') if table=='mart_user_positions'
                      else ('unrealized_pnl','unrealized_return','price_status',
                            'price_date','ledger_version')):
            report[field+'_present']=row.get(field) is not None
        report['ledger_checkpoint_matches']=int(row.get('ledger_version') or 0)==version
        report['price_state']=str(row.get('price_status') or 'null')[:25]
        report['valuation_date_matches']=str(row.get('valuation_date'))[:10]==day.isoformat()
        report['price_date_is_future']=(str(row.get('price_date') or '')[:10]>day.isoformat())
    elif table=='mart_user_portfolio_summary' and selected:
        report['summary_status']=str(selected[0].get('aggregate_status') or 'null')[:30]
        report['summary_ledger_version_matches']=int(selected[0].get('ledger_version') or 0)==version
    result['tables'][table]=report
print(json.dumps(result,sort_keys=True))
"""

def main():
    req=json.loads(REQ.read_text())
    if (req.get('intent')!='read-only-00719B-mart-field-check'
            or req.get('scope')!='one-existing-owner'
            or req.get('no_gcp_config_changes') is not True
            or req.get('no_data_writes') is not True
            or req.get('source_sha')!=SOURCE):
        raise ValueError('read_only_authorization_drift')
    obj=cloud.job(JOB)
    img=cloud.image(obj)
    if not re.fullmatch(r'ghcr\.io/tommylin15/janus-private-pipeline@sha256:[a-f0-9]{64}',img):
        raise ValueError('unexpected_job_image')
    cloud.fence()
    container=obj['template']['template']['containers'][0]
    args=['-c',CODE]
    if not container.get('command'):
        args=['python']+args
    elif container['command']!=['python']:
        raise ValueError('unexpected_job_command')
    override={'args':args,'env':[]}
    if container.get('name'):
        override['name']=container['name']
    operation=cloud.cloud(f'{cloud.ROOT}/jobs/{JOB}:run',{'etag':obj['etag'],
        'overrides':{'taskCount':1,'timeout':'360s','containerOverrides':[override]}},'POST')
    name=operation.get('name','')
    if not isinstance(name,str) or not name.startswith(cloud.ROOT+'/operations/'):
        raise ValueError('read_only_execution_missing')
    deadline=time.monotonic()+475
    while not operation.get('done') and time.monotonic()<deadline:
        time.sleep(7)
        operation=cloud.cloud(name)
    if not operation.get('done') or operation.get('error'):
        raise RuntimeError('read_only_execution_failed_or_unknown')
    e=operation.get('response') or {}
    if not cloud.terminal(e) or e.get('succeededCount')!=1 or e.get('failedCount',0):
        raise RuntimeError('read_only_execution_not_successful')
    print(json.dumps({'read_only_mart_check':'PASS',
        'execution':str(e.get('name') or '').split('/')[-1]},sort_keys=True))

if __name__=='__main__':
    main()
