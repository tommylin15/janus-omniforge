"""Bounded dev migration/acceptance via GitHub Actions and the existing ingestion Job."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import time

from ghcr_jobs_rollout import ROOT, JOB_COMPONENT, REQUIRED_JOBS, cloud, command, image, job, terminal, fingerprint, successful_operation, LEASE

MIGRATION_PROBE = '''
import base64,json
from ingestion_core.__main__ import _control_plane
from ingestion_core.serving_schema_migration import _private_api_connection,_without_role_lines
text=base64.b64decode(SQL_B64).decode()
_,rest=text.split('-- PHASE: control-prepare',1)
prepare,rest=rest.split('-- PHASE: private-api',1)
private_part,rest=rest.split('-- PHASE: control-finalize',1)
finalize,acceptance=rest.split('-- PHASE: acceptance',1)
checks,record=acceptance.split('INSERT INTO control.schema_migrations',1)
control=_control_plane()
try:
    with control.connection.transaction(),control.connection.cursor() as cur:
        cur.execute(_without_role_lines(prepare))
    try:
        with _private_api_connection() as private:
            with private.transaction(),private.cursor() as cur:
                cur.execute(_without_role_lines(private_part))
    finally:
        with control.connection.transaction(),control.connection.cursor() as cur:
            cur.execute(_without_role_lines(finalize))
    with control.connection.transaction(),control.connection.cursor() as cur:
        cur.execute(_without_role_lines(checks))
        if not all(cur.fetchone() or (False,)): raise RuntimeError('migration_acceptance_failed')
        cur.execute('INSERT INTO control.schema_migrations'+_without_role_lines(record))
    print(json.dumps({'component':'stock-supplement-acceptance','migration':'066_stock_supplement_queue','status':'PASS','owner_mutation':False}))
finally:
    control.close()
'''

READBACK_PROBE = '''
import json,urllib.request
from ingestion_core.__main__ import _control_plane
control=_control_plane()
try:
    with control.connection.cursor() as cur:
        cur.execute("SELECT symbol,status,attempts,receipt FROM control.stock_supplement_requests ORDER BY symbol LIMIT 1001")
        rows=cur.fetchall()
    if len(rows)>1000: raise RuntimeError('readback_limit')
    output=[]
    for symbol,state,attempts,receipt in rows:
        metrics={}
        for metric in ('close','revenue','eps','pe','pb','yield'):
            with urllib.request.urlopen(f'https://janus-api-2oo7qbkd5q-uc.a.run.app/api/v1/public/stocks/{symbol}/visual-series?metric={metric}&limit=200',timeout=30) as response:
                payload=json.load(response)
            metrics[metric]={'usable_points':payload.get('usable_points'),'sources':payload.get('source_ids'),
                'profile_status':(payload.get('two_year_profile') or {}).get('status')}
        output.append({'symbol':symbol,'status':state,'attempts':attempts,'receipt':receipt,'api':metrics})
    print(json.dumps({'component':'stock-supplement-acceptance','status':'OBSERVED','owner_mutation':False,'items':output},default=str))
finally:
    control.close()
'''


def save(payload):
    Path('/tmp/stock-supplement.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,sort_keys=True),flush=True)


def baseline():
    jobs = {name:job(name) for name,_ in JOB_COMPONENT}
    active = {name:[r['name'].rsplit('/',1)[-1] for r in cloud(f'{ROOT}/jobs/{name}/executions?pageSize=100').get('executions',[]) if not terminal(r)] for name in REQUIRED_JOBS}
    save({'read_only':True,'jobs':{name:{'image':image(value),'configuration_hash':fingerprint(value)} for name,value in jobs.items()},'active_executions':active})


def run(operation):
    if operation=='baseline':
        return baseline()
    request = json.loads(Path('ops/stock-supplement-request.json').read_text())
    if (request.get('approved') is not True or request.get('intent')!='stock-supplement-dev'
        or not re.fullmatch(r'[0-9a-f]{40}',request.get('source_sha',''))
        or not re.fullmatch(r'ghcr.io/tommylin15/janus-ingestion-core@sha256:[0-9a-f]{64}',request.get('image',''))):
        raise ValueError('invalid_stock_supplement_request')
    release_run=request['release_run']
    release=json.loads(command(['gh','run','view',release_run,'--json','headSha,status,conclusion,workflowName']))
    if release.get('headSha')!=request['source_sha'] or not successful_operation(release,release_run,'Janus GHCR full-test image publication','release'):
        raise ValueError('full_release_not_verified')
    command(['git','merge-base','--is-ancestor',request['source_sha'],'HEAD'])
    data=job('janus-ingestion-core')
    if image(data)!=request['image']:
        raise ValueError('ingestion_image_drift')
    command(LEASE+['acquire'])
    safe=True
    try:
        for name in REQUIRED_JOBS:
            if any(not terminal(row) for row in cloud(f'{ROOT}/jobs/{name}/executions?pageSize=100').get('executions',[])):
                raise RuntimeError('active_execution_do_not_dispatch')
        if operation=='migrate':
            text=Path('infra/postgres/migrations/066_stock_supplement_queue.sql').read_bytes()
            probe='SQL_B64='+repr(base64.b64encode(text).decode())+'\n'+MIGRATION_PROBE
        elif operation=='readback':
            probe=READBACK_PROBE
        else:
            probe="import json;from ingestion_core.stock_supplement import run_pending;print(json.dumps(run_pending(daily=True),sort_keys=True))"
        container=data['template']['template']['containers'][0]
        if container.get('command') not in (None,[],['python']):
            raise ValueError('entrypoint_drift')
        override={'args':([] if container.get('command') else ['python'])+['-c',probe]}
        if container.get('name'):
            override['name']=container['name']
        safe=False
        op=cloud(f'{ROOT}/jobs/janus-ingestion-core:run',{'etag':data['etag'],'overrides':{
            'taskCount':1,'timeout':'1800s','containerOverrides':[override]}},'POST')
        name=op.get('name','')
        save({'operation':name,'status':'SUBMITTED_DO_NOT_RESUBMIT','mode':operation})
        if not re.fullmatch(re.escape(ROOT)+r'/operations/[0-9a-f-]{36}',name):
            raise RuntimeError('unknown_operation_do_not_resubmit')
        deadline=time.monotonic()+1860
        while not op.get('done') and time.monotonic()<deadline:
            time.sleep(10)
            op=cloud(name)
        execution=op.get('response',{})
        safe=bool(op.get('done') and terminal(execution))
        if op.get('done') and op.get('error'):
            safe=all(not any(not terminal(row) for row in cloud(f'{ROOT}/jobs/{job_name}/executions?pageSize=100').get('executions',[])) for job_name in REQUIRED_JOBS)
        if not safe or op.get('error') or execution.get('succeededCount')!=1:
            raise RuntimeError('execution_not_successful_inspect_existing_operation')
        execution_name=execution['name'].rsplit('/',1)[-1]
        query='resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="'+execution_name+'"'
        result=subprocess.run(['gcloud','logging','read',query,'--project=gen-lang-client-0593591102','--limit=100','--format=json'],capture_output=True,text=True,check=True,timeout=45)
        receipts=[]
        for event in json.loads(result.stdout):
            payload=event.get('jsonPayload')
            if not isinstance(payload,dict):
                try: payload=json.loads(event.get('textPayload',''))
                except (ValueError,TypeError): continue
            if payload.get('component') in {'stock-supplement','stock-supplement-acceptance'}:
                receipts.append(payload)
        save({'mode':operation,'operation':name,'execution':execution_name,'execution_succeeded':True,'receipts':receipts})
        if not receipts:
            raise RuntimeError('runtime_receipt_not_observed')
    finally:
        if safe:
            command(LEASE+['release','--safe-to-release'])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=('baseline','migrate','run','readback'))
    run(parser.parse_args().operation)
