#!/usr/bin/env python3
"""One-owner PIT-safe 2026-10-15 TPEx official EOD and Private Mart repair.

Runner fetches BOTH official dates before lease/GCP writes. Cloud Run owner
reconstruction re-verifies immutable source, full same-day price coverage,
ledger checkpoint, and aggregate totals. No trade or ledger changes.
"""
from __future__ import annotations
from datetime import date
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as r
from p0_tpex_asof_owner_acceptance import OWNER_CODE,_read_exact_official_batch

SOURCE='7acff50000644979af3815f00fbd7f1c167e1098'
IMAGE='ghcr.io/tommylin15/janus-private-pipeline@sha256:2c6f4560abd6980aea69064795f7dbab38683f792ec628d3a8d53ed320bf5bae'
DAY=date(2026,10,15)
SCOPED={'00697B','00719B'}
REQUEST=Path('ops/p1-owner-eod-backfill-request.json')
RECEIPT=Path('/tmp/p1-owner-eod-backfill.json')
JOB='janus-private-pipeline'

def bounded_code() -> str:
    original='target=date(2026,10,14)'
    match='if symbols-set(prices):raise RuntimeError("owner_full_valuation_coverage_missing")'
    if OWNER_CODE.count(original)!=1 or OWNER_CODE.count(match)!=1:
        raise ValueError('p1_owner_code_contract_changed')
    code=OWNER_CODE.replace(original,'target=date(2026,10,15)')
    code=code.replace(match,match+'''
if any(entry[1]!=valuation for entry in prices.values()):
 raise RuntimeError("p1_owner_same_day_price_coverage_missing")''')
    code=code.replace('"component":"p0_tpex_asof_owner"','"component":"p1_owner_eod_backfill"')
    if 'target=date(2026,10,14)' in code or 'p1_owner_same_day_price_coverage_missing' not in code:
        raise ValueError('p1_owner_code_not_bound')
    return code

def main():
    q=json.loads(REQUEST.read_text())
    if not(q.get('intent')=='p1-exact-owner-official-eod-repair'
       and q.get('approved') is True and q.get('environment')=='dev'
       and q.get('source_sha')==SOURCE and q.get('target_date')==DAY.isoformat()
       and q.get('release_run')=='38755382061'
       and q.get('jobs_rollout_run')=='38821199561'
       and q.get('single_owner_only') is True
       and q.get('no_ledger_mutation') is True
       and q.get('private_mart_write_only') is True
       and q.get('no_job_template_mutation') is True
       and q.get('no_traffic_mutation') is True):
        raise ValueError('p1_owner_repair_scope_not_authorized')
    code=bounded_code()
    r.legacy_writers()
    job=r.job(JOB)
    if r.image(job)!=IMAGE:raise ValueError('p1_live_private_digest_drift')
    if r.scheduler().get('state')!='ENABLED':raise ValueError('p1_scheduler_not_enabled')
    r.fence()
    # No mutation until the exact official close for both held ETFs has been
    # independently downloaded and checked on the GitHub runner.
    verified=_read_exact_official_batch(DAY,SCOPED)
    items=[verified[s][0] for s in sorted(SCOPED)]
    hashes={s:verified[s][1] for s in sorted(SCOPED)}
    RECEIPT.write_text(json.dumps({'status':'OFFICIAL_2026_10_15_VERIFIED','no_ledger_mutation':True,
         'official_record_hashes':hashes},sort_keys=True))
    r.command(r.LEASE+['acquire'])
    r.fence()
    container=job['template']['template']['containers'][0]
    cmd=container.get('command') or []
    if cmd not in ([],['python']):raise ValueError('p1_job_entrypoint_unknown_retain_lease')
    override={'args':(['-c',code] if cmd else ['python','-c',code]),
              'env':[{'name':'JANUS_P0_TPEX_VERIFIED_EOD','value':json.dumps(items,ensure_ascii=False)}]}
    if container.get('name'):override['name']=container['name']
    op=r.cloud(f'{r.ROOT}/jobs/{JOB}:run',{
       'etag':job['etag'],'overrides':{'taskCount':1,'timeout':'900s',
                                       'containerOverrides':[override]}},'POST')
    name=op.get('name','')
    if not isinstance(name,str) or not name.startswith(r.ROOT+'/operations/'):
        raise RuntimeError('p1_dispatch_identity_unknown_retain_lease')
    RECEIPT.write_text(json.dumps({'status':'DISPATCHED_UNKNOWN','no_ledger_mutation':True,
         'operation':name.rsplit('/',1)[-1],'official_record_hashes':hashes},sort_keys=True))
    end=time.monotonic()+1100
    while not op.get('done') and time.monotonic()<end:
        time.sleep(8)
        op=r.cloud(name)
    if not op.get('done') or op.get('error'):
        raise RuntimeError('p1_owner_operation_not_proven_retain_lease')
    execution=op.get('response') or {}
    identity=str(execution.get('name') or '')
    if identity.startswith(r.ROOT+f'/jobs/{JOB}/executions/'):
        execution=r.cloud(identity)
    if not r.terminal(execution) or execution.get('succeededCount')!=1 or execution.get('failedCount',0):
        raise RuntimeError('p1_owner_execution_failed_or_unknown_retain_lease')
    # Cloud Run execution zero exit is reached only AFTER all in-container
    # per-symbol and aggregate assertions and unchanged ledger checkpoint.
    r.fence()
    r.command(r.LEASE+['release','--safe-to-release'])
    report={'status':'PASS_JOB_TERMINAL','source_sha':SOURCE,'target_date':DAY.isoformat(),
      'execution':identity.rsplit('/',1)[-1],'official_record_hashes':hashes,
      'full_same_day_price_gate':True,'ledger_unchanged':True,'no_ledger_mutation':True,
      'owner_scope':'single_real_holder','private_mart_only':True}
    RECEIPT.write_text(json.dumps(report,sort_keys=True))
    print(json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
