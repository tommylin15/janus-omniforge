"""Bounded read-only reference checks inside existing immutable dev Jobs.

No image/config updates, data writes, retention fence or cleanup. Receipts
contain counts and Core identities only; credentials and owner rows stay private.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import ghcr_jobs_rollout as r

REQUEST = Path('ops/finops-reference-runtime.json')
PREFIX = 'D06_REFERENCE_READBACK='
CORE_CODE = '''
import json
from ingestion_core.__main__ import _control_plane
with _control_plane() as control:
    connection=control.connection
    with connection.transaction():
        connection.execute('SET TRANSACTION READ ONLY')
        rows=connection.execute("SELECT request_options->>'core_snapshot_id' FROM control.executions WHERE status IN ('queued','running','retrying') LIMIT 10001").fetchall()
        if len(rows)>10000: raise RuntimeError('active_reference_limit')
        refs=sorted({row[0] for row in rows if row[0]})
print('D06_REFERENCE_READBACK='+json.dumps({'source':'active_control_executions','status':'COMPLETE','rows_checked':len(rows),'core_snapshot_ids':refs,'data_writes':0}),flush=True)
'''
MART_CODE = '''
import json, os
import psycopg
from packages.postgres_bundle import load_postgres_bundle
from intelligence_mart.runtime import _settings
load_postgres_bundle('JANUS_MART_POSTGRES_BUNDLE',{'PUBLICATION_DB_PASSWORD':('mart_publication_password','publication_password')})
settings=_settings('PUBLICATION_DB')
settings['dbname']=settings.pop('name')
out={'source':'postgres_publication_references','data_writes':0}
with psycopg.connect(**settings,sslmode=os.environ.get('PUBLICATION_DB_SSLMODE','require'),connect_timeout=5) as connection:
    connection.execute('SET TRANSACTION READ ONLY')
    connection.execute("SET LOCAL statement_timeout='10000ms'")
    rows=connection.execute('SELECT table_identifier,iceberg_snapshot_id,artifact_uri FROM publication.mart_report_index LIMIT 100001').fetchall()
    if len(rows)>100000: raise RuntimeError('publication_reference_limit')
    allowed=connection.execute("SELECT has_column_privilege(current_user,'publication.mart_report_index','core_snapshot_id','SELECT')").fetchone()[0]
    refs=[]
    if allowed:
        refs=[row[0] for row in connection.execute('SELECT DISTINCT core_snapshot_id FROM publication.mart_report_index LIMIT 100001').fetchall()]
        if len(refs)>100000: raise RuntimeError('publication_core_reference_limit')
    out.update(status='COMPLETE' if allowed else 'BLOCKED_CORE_ID_COLUMN_PRIVILEGE',rows_checked=len(rows),core_snapshot_ids=sorted(refs),protected_mart_snapshots=len({(row[0],row[1]) for row in rows}))
print('D06_REFERENCE_READBACK='+json.dumps(out,sort_keys=True),flush=True)
'''
CODES = {'janus-ingestion-core':CORE_CODE,'janus-intelligence-mart':MART_CODE}


def override(job, code):
    container=job['template']['template']['containers'][0]
    command=container.get('command') or []
    if command not in ([],['python']): raise ValueError('readonly_entrypoint_drift')
    result={'args':(['-c',code] if command else ['python','-c',code]),'env':[]}
    if container.get('name'): result['name']=container['name']
    return result


def checked_result(value):
    if not isinstance(value,dict) or value.get('data_writes')!=0:
        raise ValueError('invalid_reference_receipt')
    if value.get('source') not in {'active_control_executions','postgres_publication_references'}:
        raise ValueError('unknown_reference_source')
    refs=value.get('core_snapshot_ids')
    if not isinstance(refs,list) or any(not isinstance(x,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',x) for x in refs):
        raise ValueError('invalid_core_identity')
    return value


def probe(name, expected):
    job=r.checked_image(name,expected['image'],expected['configuration_hash'])
    start=datetime.now(timezone.utc).isoformat()
    operation=r.cloud(r.ROOT+'/jobs/'+name+':run',{'etag':job['etag'],
        'overrides':{'taskCount':1,'timeout':'180s','containerOverrides':[override(job,CODES[name])]}},'POST')
    op_name=operation.get('name','')
    if not op_name.startswith(r.ROOT+'/operations/'): raise RuntimeError('operation_identity_unknown')
    deadline=time.monotonic()+300
    while not operation.get('done') and time.monotonic()<deadline:
        time.sleep(5)
        operation=r.cloud(op_name)
    if not operation.get('done') or operation.get('error'): raise RuntimeError('readonly_operation_not_successful')
    execution=operation.get('response') or {}
    full_name=execution.get('name','')
    if not full_name.startswith(r.ROOT+'/jobs/'+name+'/executions/'): raise RuntimeError('execution_identity_unknown')
    execution=r.cloud(full_name)
    if not r.terminal(execution) or execution.get('succeededCount')!=1 or execution.get('failedCount',0):
        raise RuntimeError('readonly_execution_not_successful')
    execution_id=full_name.rsplit('/',1)[-1]
    selector=('resource.type="cloud_run_job" AND resource.labels.job_name="'+name+'" AND '
              'labels."run.googleapis.com/execution_name"="'+execution_id+'" AND timestamp>="'+start+'"')
    for _ in range(8):
        entries=json.loads(r.command(['gcloud','logging','read',selector,'--project='+r.PROJECT,'--limit=100','--format=json']))
        found=[json.loads(e['textPayload'].split(PREFIX,1)[1]) for e in entries if PREFIX in e.get('textPayload','')]
        if len(found)==1:
            result=checked_result(found[0])
            r.checked_image(name,expected['image'],expected['configuration_hash'])
            return {'execution':execution_id,'result':result,'job_config_unchanged':True}
        time.sleep(5)
    raise RuntimeError('reference_receipt_not_found')


def main():
    request=json.loads(REQUEST.read_text())
    if request.get('intent')!='read-only-d06-runtime-references' or request.get('no_data_mutation') is not True or set(request.get('jobs',{}))!=set(CODES):
        raise ValueError('runtime_reference_request_invalid')
    for name,expected in request['jobs'].items():
        if (not re.fullmatch(r'ghcr\.io/tommylin15/'+name+r'@sha256:[0-9a-f]{64}',expected.get('image',''))
                or not re.fullmatch(r'[0-9a-f]{64}',expected.get('configuration_hash',''))):
            raise ValueError('immutable_reference_baseline_required')
    r.fence()
    results=[]
    for name,expected in request['jobs'].items():
        try: results.append(probe(name,expected))
        except Exception as error:
            results.append({'job':name,'status':'BLOCKED','error_type':type(error).__name__})
            # Unknown execution status must never lead to another dispatch.
            break
    output={'component':'d06-runtime-reference-census','mode':'read-only','deletion_fence_published':False,'results':results}
    Path('d06-runtime-references.json').write_text(json.dumps(output,sort_keys=True))
    print(json.dumps(output,sort_keys=True))

if __name__=='__main__': main()
