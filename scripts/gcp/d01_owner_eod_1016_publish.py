#!/usr/bin/env python3
"""One-owner PIT-safe 2026-10-16 TPEx official EOD and Private Mart repair.

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

SOURCE='8eb42dcba28a68d4dee6d30e6a56e7d9e68bb699'
IMAGE_PREFIX='ghcr.io/tommylin15/janus-private-pipeline@sha256:'
DAY=date(2026,10,16)
SCOPED={'00697B','00719B'}
REQUEST=Path('ops/d01-owner-eod-1016-publish-request.json')
RECEIPT=Path('/tmp/d01-owner-eod-1016-publish.json')
JOB='janus-private-pipeline'

def bounded_code() -> str:
    original='target=date(2026,10,14)'
    match='if symbols-set(prices):raise RuntimeError("owner_full_valuation_coverage_missing")'
    if OWNER_CODE.count(original)!=1 or OWNER_CODE.count(match)!=1:
        raise ValueError('d01_owner_code_contract_changed')
    code=OWNER_CODE.replace(original,'target=date(2026,10,16)')
    code=code.replace(match,match+'''
if any(entry[1]!=valuation for entry in prices.values()):
 raise RuntimeError("d01_owner_same_day_price_coverage_missing")''')
    # Reuse an already persisted official price without overwriting its immutable
    # provenance. TPEx OpenAPI and dated dailyQuotes can have distinct raw hashes
    # and source URIs even when their official close/date are identical.
    prior_guard='''if (not row or row["price_date"]!=target.isoformat() or
  row["record_sha256"]!=source["record_sha256"] or
  row["source_uri"]!=source["source_uri"] or
  Decimal(row["price"])!=Decimal(source["price"])):
  raise RuntimeError("official_persisted_asof_provenance_invalid")'''
    preserved_guard='''if (not row or row["price_date"]!=target.isoformat() or
  Decimal(row["price"])!=Decimal(source["price"])):
  raise RuntimeError("official_persisted_asof_provenance_invalid")
 from services.api.tpex_quotes import TPEX_OFFICIAL_EOD_URL,TPEX_OFFICIAL_DATED_URL
 import re
 stored_uri=row.get("source_uri")
 stored_hash=row.get("record_sha256")
 if (not isinstance(stored_uri,str) or not isinstance(stored_hash,str) or
     re.fullmatch(r"[0-9a-f]{64}",stored_hash) is None or
     not (stored_uri==TPEX_OFFICIAL_EOD_URL or
          (stored_uri.startswith(TPEX_OFFICIAL_DATED_URL+"?") and "response=json" in stored_uri))):
  raise RuntimeError("official_stored_provenance_not_authorized")'''
    if code.count(prior_guard)!=1:
        raise ValueError('d01_owner_provenance_guard_drift')
    code=code.replace(prior_guard,preserved_guard)
    code=code.replace('"component":"p0_tpex_asof_owner"','"component":"d01_owner_eod_1016_publish"')
    if ('target=date(2026,10,14)' in code or 'd01_owner_same_day_price_coverage_missing' not in code
        or 'official_stored_provenance_not_authorized' not in code):
        raise ValueError('d01_owner_code_not_bound')
    return code

def main():
    q=json.loads(REQUEST.read_text())
    if not(q.get('intent')=='d01-2026-10-16-exact-owner-private-mart-publish'
       and q.get('approved') is True and q.get('environment')=='dev'
       and q.get('source_sha')==SOURCE and q.get('target_date')==DAY.isoformat()
       and q.get('release_run')=='38856837257'
       and q.get('jobs_rollout_run')=='38857643226'
       and q.get('single_owner_only') is True
       and q.get('no_ledger_mutation') is True
       and q.get('private_mart_write_only') is True
       and q.get('no_job_template_mutation') is True
       and q.get('no_traffic_mutation') is True):
        raise ValueError('d01_owner_repair_scope_not_authorized')
    code=bounded_code()
    r.legacy_writers()
    job=r.job(JOB)
    if not (r.image(job).startswith(IMAGE_PREFIX) and len(r.image(job))==len(IMAGE_PREFIX)+64 and all(c in '0123456789abcdef' for c in r.image(job)[len(IMAGE_PREFIX):])):raise ValueError('d01_live_private_digest_drift')
    if r.scheduler().get('state')!='ENABLED':raise ValueError('d01_scheduler_not_enabled')
    r.fence()
    # No mutation until the exact official close for both held ETFs has been
    # independently downloaded and checked on the GitHub runner.
    verified=_read_exact_official_batch(DAY,SCOPED)
    items=[verified[s][0] for s in sorted(SCOPED)]
    hashes={s:verified[s][1] for s in sorted(SCOPED)}
    RECEIPT.write_text(json.dumps({'status':'OFFICIAL_2026_10_16_VERIFIED','no_ledger_mutation':True,
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
        raise RuntimeError('d01_owner_operation_not_proven_retain_lease')
    execution=op.get('response') or {}
    identity=str(execution.get('name') or '')
    if identity.startswith(r.ROOT+f'/jobs/{JOB}/executions/'):
        execution=r.cloud(identity)
    if not r.terminal(execution) or execution.get('succeededCount')!=1 or execution.get('failedCount',0):
        raise RuntimeError('d01_owner_execution_failed_or_unknown_retain_lease')
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
