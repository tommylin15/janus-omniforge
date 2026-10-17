#!/usr/bin/env python3
"""DRL-01 one-shot bounded official 2026 EPS Core -> existing PostgreSQL serving.

No alternate provider, no owner or Core mutation. Only six audited equity
symbols and two published official single-quarter periods; preserve lineage.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from ghcr_jobs_rollout import ROOT, cloud, job, terminal

PROBE = r"""
import json,os
from collections import defaultdict
from datetime import date
from decimal import Decimal,InvalidOperation
from pyiceberg.expressions import And,EqualTo,In
from ingestion_core.__main__ import _iceberg_core
from ingestion_core.serving_projection import StockServingProjection
from packages.web_api.core import _comparable_single_quarter_eps

req=json.loads(os.environ['DRL01_EPS_SERVING_SCOPE'])
symbols=set(req['symbols'])
report={'component':'drl01_2026_eps_serving_sync','status':'PARTIAL',
        'scope':'official_validated_2026_q1_q2_only',
        'owner_mutation':False,'core_mutation':False,'published_rows':0,
        'symbols_qualified':0}
core=None
try:
    core=_iceberg_core(os.environ['CORE_BUCKET'],read_only=True)
    table=core.catalog.load_table(core.table_identifier('financials'))
    snap=table.current_snapshot()
    report['core_snapshot_id']=str(snap.snapshot_id)
    rows=table.scan(snapshot_id=snap.snapshot_id,
        row_filter=And(In('symbol',sorted(symbols)),EqualTo('fiscal_year',2026)),
        limit=12000).to_arrow().to_pylist()
    candidates=defaultdict(list)
    for row in rows:
        if (row.get('symbol') not in symbols or row.get('source_id')!='mops'
            or not row.get('provenance_id') or not row.get('execution_id')
            or not row.get('availability_at') or str(row['availability_at'])[:10]>'2026-10-17'
            or row.get('unit')!='TWD_per_share'):continue
        try:
            y,q=int(row['fiscal_year']),int(row['fiscal_quarter'])
            end=str(row.get('fiscal_period_end') or '')[:10]
            value=Decimal(str(row.get('value')))
            if not value.is_finite() or y!=2026 or q not in (1,2) or (
                end!='2026-'+('03-31' if q==1 else '06-30')):continue
        except (TypeError,ValueError,InvalidOperation):continue
        # _comparable_single_quarter_eps() only accepts official explicit
        # single quarter or Q1 YTD. Never treat Q2 YTD as Q2.
        candidates[row['symbol']].append(row)
    published=[]
    for symbol in sorted(symbols):
        qualified=_comparable_single_quarter_eps(candidates[symbol])
        periods={int(row['fiscal_quarter']) for row in qualified}
        if periods!={1,2}:
            raise RuntimeError('current_year_qualified_eps_missing')
        selected=[]
        for q in (1,2):
            valid=[row for row in candidates[symbol] if int(row['fiscal_quarter'])==q and
               ((row.get('metric')=='eps_single_quarter' and row.get('period_basis')=='single_quarter')
                 or q==1 and row.get('period_basis') in (None,'year_to_date')
                 and ('每股盈餘' in str(row.get('metric') or '') or row.get('metric')=='eps_year_to_date'))]
            if not valid:raise RuntimeError('missing_raw_eligible_eps')
            valid.sort(key=lambda row:str(row.get('availability_at') or ''))
            selected.append(valid[-1])
        published.extend(selected)
        report['symbols_qualified']+=1
    grouped=defaultdict(list)
    for row in published:
        grouped[(str(row['execution_id']),str(row['provenance_id']),str(row['source_id']))].append(row)
    projection=StockServingProjection.from_env()
    for (execution,provenance,source), items in grouped.items():
        report['published_rows']+=projection.publish(
            'financials',items,execution_id=execution,
            provenance_id=provenance,source_id=source,
            core_snapshot_id=snap.snapshot_id)
    report['status']='PASS' if report['symbols_qualified']==6 and report['published_rows']==12 else 'PARTIAL'
except Exception as error:
    report['status']='BLOCKED_'+type(error).__name__
finally:
    if core is not None:
        try:core.close()
        except Exception:pass
    print(json.dumps(report,sort_keys=True,ensure_ascii=False),flush=True)
"""

def main():
    req=json.loads(Path(sys.argv[1]).read_text())
    if (req.get('intent')!='drl01-publish-core-2026-eps-to-existing-serving'
        or req.get('approved') is not True
        or req.get('symbols')!=['1513','2327','2382','3231','3711','5876']
        or req.get('year')!=2026 or req.get('quarters')!=[1,2]
        or req.get('no_owner_mutation') is not True
        or req.get('no_core_mutation') is not True
        or req.get('no_job_template_mutation') is not True):
        raise ValueError('invalid_eps_serving_scope')
    j=job('janus-ingestion-core')
    c=j['template']['template']['containers']
    if len(c)!=1 or c[0].get('command') not in (None,[],['python']):
        raise ValueError('job_entrypoint_drift')
    override={'args':(['python'] if not c[0].get('command') else [])+['-c',PROBE],
              'env':[{'name':'QUEUE_CONSUMER','value':'false'},
                     {'name':'DRL01_EPS_SERVING_SCOPE','value':json.dumps(req,separators=(',',':'))}]}
    if c[0].get('name'):override['name']=c[0]['name']
    op=cloud(f'{ROOT}/jobs/janus-ingestion-core:run',
             {'etag':j['etag'],'overrides':{'taskCount':1,'timeout':'600s',
                                           'containerOverrides':[override]}},'POST')
    name=op.get('name','')
    if not name.startswith(ROOT+'/operations/'):raise RuntimeError('invalid_eps_serving_operation')
    until=time.monotonic()+690
    while not op.get('done') and time.monotonic()<until:
        time.sleep(6);op=cloud(name)
    if not op.get('done') or op.get('error'):raise RuntimeError('eps_serving_operation_unknown')
    exe=op.get('response',{})
    if not terminal(exe) or exe.get('succeededCount')!=1 or exe.get('failedCount',0):
        raise RuntimeError('eps_serving_job_failed')
    execution=exe.get('name','').rsplit('/',1)[-1]
    if not execution.startswith('janus-ingestion-core-'):raise ValueError('invalid_execution')
    filt='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+execution+'"'
    receipt=None
    for _ in range(5):
        cp=subprocess.run(['gcloud','logging','read',filt,'--project=gen-lang-client-0593591102',
                           '--limit=180','--format=json'],text=True,capture_output=True,timeout=45)
        if cp.returncode==0:
            for event in json.loads(cp.stdout):
                obj=event.get('jsonPayload')
                if not isinstance(obj,dict):
                    try:obj=json.loads(event.get('textPayload',''))
                    except (TypeError,ValueError):continue
                if isinstance(obj,dict) and obj.get('component')=='drl01_2026_eps_serving_sync':
                    receipt=obj;break
        if receipt:break
        time.sleep(5)
    if receipt is None:raise RuntimeError('eps_serving_receipt_missing')
    out={'execution':execution,'receipt':receipt}
    Path('/tmp/drl01-eps-serving-readback.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
    print(json.dumps(out,sort_keys=True))
    if receipt['status']!='PASS':raise RuntimeError('eps_serving_publication_not_complete')

if __name__=='__main__':main()
