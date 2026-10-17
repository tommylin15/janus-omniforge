#!/usr/bin/env python3
"""Read-only source eligibility check for approved TPEx ETF symbols (no writes)."""
import json,subprocess,sys,time
from pathlib import Path
from ghcr_jobs_rollout import ROOT,cloud,job,terminal
PROBE=r"""
import json,os
from datetime import date
from ingestion_core.__main__ import _control_plane
from ingestion_core.data_supplement import _fetch
from urllib.parse import urlencode
symbols=set(json.loads(os.environ['DRL01_ETF_CODES']))
asof=date(2026,10,16)
report={'component':'drl01_etf_official_source_probe','status':'PARTIAL',
        'date':asof.isoformat(),'requested':len(symbols),'source_approved':False,
        'owner_mutation':False,'read_only':True}
with _control_plane() as control:
    report['source_approved']=bool(control.source_is_approved('tpex'))
    if report['source_approved']:
        url='https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?'+urlencode(
            {'date':asof.strftime('%Y/%m/%d'),'id':'','response':'json'})
        try:
            raw,_=_fetch(url)
            data=json.loads(raw)
            sections=[]
            if isinstance(data,list):sections=[data]
            elif isinstance(data,dict):
                if data.get('tables'):
                    for tab in data['tables']:
                        fields=tab.get('fields') or []
                        sections.append([dict(zip(fields,values)) for values in tab.get('data',[])])
                else:sections=[data.get('data',[])]
            found=set()
            matched_fields=set()
            for records in sections:
                for row in records:
                    if isinstance(row,dict) and str(row.get('代號') or row.get('證券代號') or row.get('symbol') or '').strip() in symbols:
                        found.add(str(row.get('代號') or row.get('證券代號') or row.get('symbol')).strip())
                        matched_fields.update(str(key) for key in row.keys())
            report['found']=len(found)
            report['matching_field_names']=sorted(matched_fields)
            report['source_tables']=len(sections)
            report['status']='PASS_SOURCE_PRESENT' if found==symbols else 'PARTIAL_SOURCE_MISSING'
        except Exception as error:
            report['status']='ERROR_'+type(error).__name__
print(json.dumps(report,sort_keys=True,ensure_ascii=False))
"""
def main():
    req=json.loads(Path(sys.argv[1]).read_text())
    if (req.get('approved') is not True or req.get('intent')!='drl01-etf-tpex-official-source-check'
        or req.get('read_only') is not True or req.get('no_owner_mutation') is not True
        or req.get('symbols')!=['00697B','00719B']):
        raise ValueError('invalid_etf_source_scope')
    j=job('janus-ingestion-core')
    c=j['template']['template']['containers']
    if len(c)!=1 or c[0].get('command') not in (None,[],['python']):raise ValueError('job_entrypoint_drift')
    overrides={'args':(['python'] if not c[0].get('command') else [])+['-c',PROBE],
      'env':[{'name':'QUEUE_CONSUMER','value':'false'},
             {'name':'DRL01_ETF_CODES','value':json.dumps(req['symbols'])}]}
    if c[0].get('name'):overrides['name']=c[0]['name']
    op=cloud(f'{ROOT}/jobs/janus-ingestion-core:run',{'etag':j['etag'],'overrides':{
        'taskCount':1,'timeout':'250s','containerOverrides':[overrides]}},'POST')
    name=op.get('name','')
    if not name.startswith(ROOT+'/operations/'):raise RuntimeError('bad_etf_probe_operation')
    deadline=time.monotonic()+320
    while not op.get('done') and time.monotonic()<deadline:
        time.sleep(5);op=cloud(name)
    if not op.get('done') or op.get('error'):raise RuntimeError('etf_probe_unverified')
    exe=op.get('response',{})
    if not terminal(exe) or exe.get('succeededCount')!=1 or exe.get('failedCount',0):
        raise RuntimeError('etf_probe_execution_failed')
    ename=exe['name'].rsplit('/',1)[-1]
    query='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+ename+'"'
    report=None
    for _ in range(5):
        proc=subprocess.run(['gcloud','logging','read',query,'--project=gen-lang-client-0593591102',
            '--limit=150','--format=json'],capture_output=True,text=True,timeout=40)
        if proc.returncode==0:
            for x in json.loads(proc.stdout):
                v=x.get('jsonPayload')
                if not isinstance(v,dict):
                    try:v=json.loads(x.get('textPayload',''))
                    except (TypeError,ValueError):continue
                if isinstance(v,dict) and v.get('component')=='drl01_etf_official_source_probe':
                    report=v;break
        if report is not None:break
        time.sleep(5)
    if report is None:raise RuntimeError('etf_probe_receipt_missing')
    out={'execution':ename,'receipt':report}
    Path('/tmp/drl01-etf-source.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
