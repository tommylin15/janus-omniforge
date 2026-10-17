#!/usr/bin/env python3
"""Read-only 2025 Q4 EPS numerator/denominator source-fact feasibility audit."""
import json,subprocess,sys,time
from pathlib import Path
from ghcr_jobs_rollout import ROOT,cloud,job,terminal
PROBE=r"""
import json,os
from urllib.parse import urlencode
from ingestion_core.__main__ import _control_plane
from ingestion_core.data_supplement import _fetch
from ingestion_core.financial_publication import XbrlReport
syms=json.loads(os.environ['DRL01_Q4_SYMBOLS'])
out={'component':'drl01_q4_eps_source_feasibility','status':'PARTIAL','read_only':True,
     'symbols_checked':len(syms),'eligible_numerator_denominator':0,'per_symbol':[]}
with _control_plane() as control:
    if not control.source_is_approved('mops'):raise ValueError('mops_not_authorized')
    with control.connection.cursor() as cur:
        cur.execute("SELECT symbol FROM control.stock_master WHERE enabled AND market='TWSE' AND symbol=ANY(%s)",(syms,))
        if {str(v[0]) for v in cur.fetchall()}!=set(syms):raise ValueError('unapproved_current_stock')
    for symbol in syms:
        item={'symbol':symbol,'periods':{}}
        for quarter,year_end in ((3,'09-30'),(4,'12-31')):
            url='https://mopsov.twse.com.tw/server-java/t164sb01?'+urlencode(
                {'step':'1','CO_ID':symbol,'SYEAR':2025,'SSEASON':quarter,'REPORT_ID':'C'})
            period={'q':quarter,'has_weighted_shares':False,'has_parent_profit':False,
                    'has_basic_eps':False}
            try:
                raw,_=_fetch(url)
                report=XbrlReport()
                report.feed(raw.decode('latin-1'))
                md=report.metadata
                if (md.get('tifrs-notes:CompanyID')!=symbol or md.get('tifrs-notes:Year')!='2025'
                    or md.get('tifrs-notes:Quarter')!=str(quarter)
                    or md.get('tifrs-notes:ReportCategory')!='Consolidated report'):
                    raise ValueError('report_identity_mismatch')
                for fact in report.facts:
                    ctx=report.contexts.get(fact.get('contextref'),{})
                    if (ctx.get('dimensioned') or ctx.get('startdate')!='2025-01-01'
                        or ctx.get('enddate')!='2025-'+year_end):
                        continue
                    name=str(fact.get('name') or '')
                    units=report.units.get(fact.get('unitref'),[])
                    if ('WeightedAverage' in name and ('Share' in name or 'shares' in name)
                        and units==['xbrli:shares']):
                        period['has_weighted_shares']=True
                    if name=='ifrs-full:ProfitLossAttributableToOwnersOfParent' and units==['iso4217:TWD']:
                        period['has_parent_profit']=True
                    if name=='ifrs-full:BasicEarningsLossPerShare' and units==['iso4217:TWD','xbrli:shares']:
                        period['has_basic_eps']=True
                period['status']='FETCHED_VALIDATED'
            except Exception as error:
                period['status']='ERROR_'+type(error).__name__
                if getattr(error,'code',None) is not None:
                    period['http_status']=int(error.code)
            item['periods'][str(quarter)]=period
        item['has_reconstruction_inputs']=all(
            p['has_weighted_shares'] and p['has_parent_profit'] and p['has_basic_eps']
            for p in item['periods'].values())
        out['eligible_numerator_denominator']+=int(item['has_reconstruction_inputs'])
        out['per_symbol'].append(item)
source_failures=sum(
    p['status'].startswith('ERROR_') for item in out['per_symbol']
    for p in item['periods'].values())
out['source_failures']=source_failures
out['status']=('BLOCKED_OFFICIAL_SOURCE_ACCESS' if source_failures else
               'INPUTS_PRESENT' if out['eligible_numerator_denominator'] else
               'NO_SAFE_Q4_DENOMINATORS')
print(json.dumps(out,sort_keys=True,ensure_ascii=False),flush=True)
"""
def main():
    req=json.loads(Path(sys.argv[1]).read_text())
    syms=req.get('symbols')
    if (req.get('intent')!='drl01-readonly-2025-q4-eps-denominator-audit'
        or req.get('approved') is not True or req.get('read_only') is not True
        or not isinstance(syms,list) or not 1<=len(syms)<=8
        or any(not s.isdigit() or len(s)!=4 for s in syms)):
        raise ValueError('invalid_q4_probe_scope')
    j=job('janus-ingestion-core')
    c=j['template']['template']['containers']
    if len(c)!=1 or c[0].get('command') not in (None,[],['python']):raise ValueError('job_template_drift')
    override={'args':(['python'] if not c[0].get('command') else [])+['-c',PROBE],
              'env':[{'name':'QUEUE_CONSUMER','value':'false'},
                     {'name':'DRL01_Q4_SYMBOLS','value':json.dumps(syms)}]}
    if c[0].get('name'):override['name']=c[0]['name']
    op=cloud(f'{ROOT}/jobs/janus-ingestion-core:run',{'etag':j['etag'],'overrides':{
        'taskCount':1,'timeout':'850s','containerOverrides':[override]}},'POST')
    if not op.get('name','').startswith(ROOT+'/operations/'):raise RuntimeError('q4_probe_operation_unknown')
    name=op['name']
    until=time.monotonic()+930
    while not op.get('done') and time.monotonic()<until:
        time.sleep(6);op=cloud(name)
    if not op.get('done') or op.get('error'):raise RuntimeError('q4_probe_operation_failed')
    exe=op.get('response',{})
    if not terminal(exe) or exe.get('succeededCount')!=1 or exe.get('failedCount',0):
        raise RuntimeError('q4_probe_not_successful')
    execution=exe['name'].rsplit('/',1)[-1]
    filt='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+execution+'"'
    result=None
    for _ in range(5):
        p=subprocess.run(['gcloud','logging','read',filt,'--project=gen-lang-client-0593591102',
            '--limit=180','--format=json'],capture_output=True,text=True,timeout=40)
        if p.returncode==0:
            for row in json.loads(p.stdout):
                v=row.get('jsonPayload')
                if not isinstance(v,dict):
                    try:v=json.loads(row.get('textPayload',''))
                    except (TypeError,ValueError):continue
                if isinstance(v,dict) and v.get('component')=='drl01_q4_eps_source_feasibility':
                    result=v;break
        if result is not None:break
        time.sleep(5)
    if result is None:raise RuntimeError('missing_q4_source_receipt')
    out={'execution':execution,'receipt':result}
    Path('/tmp/drl01-q4-eps-source.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
