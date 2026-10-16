#!/usr/bin/env python3
"""P1 one-owner 2026-10-15 EOD readiness read-only; no ledger or Mart mutation."""
from __future__ import annotations
import json, time, sys, subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as r

JOB='janus-private-pipeline'
SOURCE='7acff50000644979af3815f00fbd7f1c167e1098'
IMAGE='ghcr.io/tommylin15/janus-private-pipeline@sha256:2c6f4560abd6980aea69064795f7dbab38683f792ec628d3a8d53ed320bf5bae'
REQUEST=Path('ops/p1-owner-eod-readonly-request.json')
OUT=Path('/tmp/p1-owner-eod-readonly.json')
CODE=r'''
import json
from datetime import date
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import repository_from_env
from services.api.private_pipeline import CorePriceReader,owner_price_reader,resolve_valuation_date
from services.api.store import PrivateIcebergStore
target=date(2026,10,15)
load_postgres_bundle('JANUS_API_POSTGRES_BUNDLE',{
 'PRIVATE_DATABASE_URL':('pipeline_database_url','database_url'),
 'MOBILE_LEDGER_DATABASE_URL':'database_url',
 'PRIVATE_CATALOG_PASSWORD':('pipeline_catalog_password','catalog_password'),
 'CORE_CATALOG_PASSWORD':'core_catalog_password'})
repo=repository_from_env()
with repo._connection() as connection:
 connection.execute('SET TRANSACTION READ ONLY')
 owners=connection.execute('SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s AND shares>0',('00697B',)).fetchall()
if len(owners)!=1:raise RuntimeError('owner_scope_not_exactly_one')
owner=owners[0]['user_id']
ledger_before=int(repo.latest_ledger_version(owner))
with repo._connection() as connection:
 connection.execute('SET TRANSACTION READ ONLY')
 holdings=connection.execute('SELECT DISTINCT symbol FROM private.current_positions WHERE user_id=%s AND shares>0',(owner,)).fetchall()
symbols={row['symbol'] for row in holdings}
if not {'00697B','00719B'}.issubset(symbols) or not 1<=len(symbols)<=50:
 raise RuntimeError('owner_symbol_scope_invalid')
market=CorePriceReader.from_env()
latest=resolve_valuation_date(None,market.latest_valuation_date)
archive=repo.official_eod_quotes({'00697B','00719B'},target)
reader=owner_price_reader(repo,market)
prices=reader(symbols,target)
valid={symbol:entry for symbol,entry in prices.items()
       if isinstance(entry,tuple) and len(entry)==2 and entry[0] is not None
       and entry[0].is_finite() and entry[0]>0 and entry[1]<=target}
same_day=sum(1 for entry in valid.values() if entry[1]==target)
store=PrivateIcebergStore.from_env()
positions=[row for row in store.mart('mart_user_positions',owner)
 if str(row.get('valuation_date'))==target.isoformat() and int(row.get('ledger_version') or 0)==ledger_before]
pnl=[row for row in store.mart('mart_user_unrealized_pnl',owner)
 if str(row.get('valuation_date'))==target.isoformat() and int(row.get('ledger_version') or 0)==ledger_before]
aggregate=[row for row in store.mart('mart_user_portfolio_summary',owner)
 if str(row.get('valuation_date'))==target.isoformat() and int(row.get('ledger_version') or 0)==ledger_before
 and row.get('currency')=='TWD']
ledger_after=int(repo.latest_ledger_version(owner))
if ledger_after!=ledger_before:raise RuntimeError('ledger_changed_during_readonly')
result={'status':'PASS_READ_ONLY','target_date':target.isoformat(),
 'core_latest_date':latest.isoformat(),'holder_count':1,'held_count':len(symbols),
 'valid_asof_price_count':len(valid),'same_day_price_count':same_day,
 'official_etf_archive_count':len(archive),
 'mart_position_count':len(positions),'mart_unrealized_count':len(pnl),
 'mart_summary_count':len(aggregate),
 'mart_aggregate_status':aggregate[0].get('aggregate_status') if len(aggregate)==1 else None,
 'mart_summary_pnl_present':aggregate[0].get('unrealized_pnl') is not None if len(aggregate)==1 else False,
 'ledger_unchanged':True,'no_data_mutation':True}
print('P1_EOD_READINESS='+json.dumps(result,sort_keys=True),flush=True)
'''

def main():
 q=json.loads(REQUEST.read_text())
 if not(q.get('intent')=='p1-real-owner-eod-readonly' and q.get('approved') is True
   and q.get('target_date')=='2026-10-15' and q.get('source_sha')==SOURCE
   and q.get('rollout_run')=='38821199561' and q.get('no_ledger_mutation') is True
   and q.get('no_mart_mutation') is True and q.get('no_job_template_mutation') is True):
  raise ValueError('p1_owner_readonly_guard_invalid')
 job=r.job(JOB)
 if r.image(job)!=IMAGE:raise ValueError('live_private_immutable_image_drift')
 if r.scheduler().get('state')!='ENABLED':raise ValueError('scheduler_not_enabled')
 r.fence()
 container=job['template']['template']['containers'][0]
 command=container.get('command') or []
 if command not in ([],['python']):raise ValueError('job_entrypoint_drift')
 override={'args':(['-c',CODE] if command else ['python','-c',CODE]),'env':[]}
 if container.get('name'):override['name']=container['name']
 op=r.cloud(f'{r.ROOT}/jobs/{JOB}:run',{
  'etag':job['etag'],'overrides':{'taskCount':1,'timeout':'420s','containerOverrides':[override]}},'POST')
 name=op.get('name','')
 if not isinstance(name,str) or not name.startswith(r.ROOT+'/operations/'):
  raise RuntimeError('readonly_operation_identity_unknown')
 OUT.write_text(json.dumps({'status':'DISPATCHED','no_data_mutation':True}))
 deadline=time.monotonic()+620
 while not op.get('done') and time.monotonic()<deadline:
  time.sleep(6)
  op=r.cloud(name)
 if not op.get('done') or op.get('error'):
  raise RuntimeError('readonly_operation_not_successful')
 execution=op.get('response') or {}
 execution_name=str(execution.get('name',''))
 if execution_name.startswith(r.ROOT+f'/jobs/{JOB}/executions/'):
  execution=r.cloud(execution_name)
 if not r.terminal(execution) or execution.get('succeededCount')!=1 or execution.get('failedCount',0):
  raise RuntimeError('readonly_execution_not_terminal_success')
 id=execution_name.rsplit('/',1)[-1]
 if not id.startswith('janus-private-pipeline-'):raise ValueError('unexpected_readonly_execution')
 filters=('resource.type="cloud_run_job" AND resource.labels.job_name="janus-private-pipeline" '
          'AND timestamp>="2026-10-15T23:30:00Z"')
 found=[]
 for _ in range(8):
  data=json.loads(r.command(['gcloud','logging','read',filters,
       '--project=gen-lang-client-0593591102','--limit=250','--format=json']))
  found=[]
  for item in data:
   lbl=item.get('labels') or {}
   res=(item.get('resource') or {}).get('labels') or {}
   if lbl.get('run.googleapis.com/execution_name')!=id and res.get('execution_name')!=id:continue
   raw=item.get('textPayload') or ''
   if 'P1_EOD_READINESS=' not in raw:continue
   try:found.append(json.loads(raw.split('P1_EOD_READINESS=',1)[1].strip()))
   except ValueError:pass
  if found:break
  time.sleep(6)
 if len(found)!=1 or found[0].get('no_data_mutation') is not True:
  raise RuntimeError('readonly_sanitized_log_unavailable')
 result={'status':'PASS_READ_ONLY','execution':id,'result':found[0]}
 OUT.write_text(json.dumps(result,sort_keys=True))
 print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
