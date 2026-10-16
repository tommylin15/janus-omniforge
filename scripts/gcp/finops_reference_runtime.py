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
import json, os, resource, time, traceback
from pathlib import Path
from urllib.error import HTTPError
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from ingestion_core.__main__ import _control_plane, _iceberg_core
from ingestion_core import batch_controller
import inspect
mirror_disabled=not hasattr(batch_controller,'export_events') and '_iceberg_core' not in inspect.getsource(batch_controller.run)
with _control_plane() as control:
    connection=control.connection
    with connection.transaction():
        connection.execute('SET TRANSACTION READ ONLY')
        rows=connection.execute("SELECT request_options->>'core_snapshot_id' FROM control.executions WHERE status IN ('queued','running','retrying') LIMIT 10001").fetchall()
        if len(rows)>10000: raise RuntimeError('active_reference_limit')
        refs=sorted({row[0] for row in rows if row[0]})
        daily=connection.execute("SELECT (created_at AT TIME ZONE 'Asia/Taipei')::date,count(*) FROM control.batch_event_outbox WHERE created_at>=now()-interval '14 days' GROUP BY 1 ORDER BY 1").fetchall()
        pending=connection.execute("SELECT count(*),min(created_at) FROM control.batch_event_outbox WHERE exported_at IS NULL").fetchone()
        slots=connection.execute("SELECT date_bin(interval '24 hours',created_at,timestamptz '2000-01-01 15:30:00+00'),date_bin(interval '6 hours',created_at,timestamptz '2000-01-01 15:30:00+00'),count(*) FROM control.batch_event_outbox WHERE created_at>=date_bin(interval '24 hours',now(),timestamptz '2000-01-01 15:30:00+00')-interval '14 days' AND created_at<date_bin(interval '24 hours',now(),timestamptz '2000-01-01 15:30:00+00') GROUP BY 1,2 ORDER BY 1,2").fetchall()
out={'source':'active_control_executions','status':'COMPLETE','rows_checked':len(rows),'core_snapshot_ids':refs,'data_writes':0,
     'outbox_daily_events':[{'taipei_date':str(day),'events':count} for day,count in daily],
     'outbox_six_hour_events':[{'day_start_utc':str(day),'slot_start_utc':str(slot),'events':count} for day,slot,count in slots],
     'pending_events':pending[0],'oldest_pending_at':str(pending[1]) if pending[1] else None,'iceberg_audit_disabled':mirror_disabled}
from ingestion_core.stage import GcsObjectStore
from ingestion_core.iceberg_maintenance import maintain_financials, compact_batch_events, _keep_snapshots, _references
from ingestion_core.retention import clean_orphans
core=_iceberg_core(os.environ['CORE_BUCKET'],read_only=True)
started=time.monotonic()
try:
    store=GcsObjectStore(os.environ['CORE_BUCKET'])
    from urllib.request import Request, urlopen
    permissions_url='https://storage.googleapis.com/storage/v1/b/'+store.bucket+'/iam/testPermissions?permissions=storage.objects.get&permissions=storage.objects.create&permissions=storage.objects.delete'
    try:
        with urlopen(Request(permissions_url,headers={'Authorization':'Bearer '+store._token()}),timeout=15) as response:
            out['gcs_core_permissions']=sorted(json.load(response).get('permissions',[]))
    except HTTPError as error:
        out['gcs_permission_probe_http_status']=error.code
    identifier='ops.batch_events_v1'
    out['audit_compaction_dry_run']=compact_batch_events(core=core,apply=False)
    plan=maintain_financials(core=core,store=store,apply=False,identifier=identifier)
    orphans=clean_orphans(core,store,identifier,apply=False,now=datetime.now(timezone.utc))
    table=core.catalog.load_table(identifier)
    pointer=table.metadata_location
    referenced,_=_references(store,identifier)
    keep=_keep_snapshots(table,referenced,datetime.now(timezone.utc))
    live=set()
    for snapshot in table.snapshots():
        if snapshot.snapshot_id not in keep: continue
        live.add(snapshot.manifest_list)
        for manifest in snapshot.manifests(table.io):
            if manifest.manifest_path in live: continue
            live.add(manifest.manifest_path)
            live.update(entry.data_file.file_path for entry in manifest.fetch_manifest_entry(table.io,discard_deleted=True))
    objects=store.objects('warehouse/batch_events_v1/')
    cutoff=datetime.now(timezone.utc)-timedelta(days=7)
    candidates=[x for x in objects if x['name'].endswith(('.avro','.parquet'))
        and 'gs://'+store.bucket+'/'+x['name'] not in live
        and datetime.fromisoformat(x['updated'].replace('Z','+00:00'))<cutoff]
    if core.catalog.load_table(identifier).metadata_location!=pointer: raise RuntimeError('audit_catalog_changed_during_plan')
    out['audit_cleanup_dry_run']={'maintenance':plan,'current_orphans':orphans,
        'post_expiry_orphan_objects':len(candidates),'post_expiry_orphan_bytes':sum(int(x['size']) for x in candidates),
        'post_expiry_orphans_under_1mib':sum(int(x['size'])<1024*1024 for x in candidates),
        'post_expiry_orphans_under_32mib':sum(int(x['size'])<32*1024*1024 for x in candidates),
        'candidate_generations':[{'name':x['name'],'generation':x['generation'],'bytes':int(x['size'])} for x in candidates],
        'audit_visible_objects':len(objects),'audit_visible_bytes':sum(int(x['size']) for x in objects),
        'elapsed_seconds':round(time.monotonic()-started,3),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'applied':False}
except Exception as error:
    frame=traceback.extract_tb(error.__traceback__)[-1]
    out['audit_cleanup_dry_run']={'status':'BLOCKED','error_type':type(error).__name__,
        'http_status':error.code if isinstance(error,HTTPError) else None,
        'error_location':Path(frame.filename).name+':'+str(frame.lineno),'applied':False}
finally: core.close()
print('D06_REFERENCE_READBACK='+json.dumps(out,sort_keys=True),flush=True)
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


def batch_forecast(slots):
    """Historical four-window mirror batches avoided after mirror shutdown."""
    daily={}
    old_batches=0
    for row in slots:
        count=row['events']
        if type(count) is not int or count<0: raise ValueError('invalid_event_count')
        daily[row['day_start_utc']]=daily.get(row['day_start_utc'],0)+count
        old_batches+=(count+199)//200
    return {'observed_days':len(daily),'events':sum(daily.values()),
            'four_window_nonempty_batches':old_batches,'disabled_mirror_batches':0,
            'estimated_table_scans_avoided':2*old_batches,
            'estimated_batch_reduction_percent':100.0 if old_batches else None,
            'max_observed_daily_events':max(daily.values(),default=0),
            'matched_runtime_io_verified':False,'assumption':'prior four-window mirror; 200-event nonempty batches; successful flushes; no retries; two logical table scans per batch eliminated by shutdown; not GCS request counts'}


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


def probe(name, expected, state, save):
    job=r.checked_image(name,expected['image'],expected['configuration_hash'])
    start=datetime.now(timezone.utc).isoformat()
    operation=r.cloud(r.ROOT+'/jobs/'+name+':run',{'etag':job['etag'],
        'overrides':{'taskCount':1,'timeout':'360s','containerOverrides':[override(job,CODES[name])]}},'POST')
    op_name=operation.get('name','')
    if not op_name.startswith(r.ROOT+'/operations/'): raise RuntimeError('operation_identity_unknown')
    state.update(status='DISPATCHED',operation=op_name)
    save()
    deadline=time.monotonic()+480
    while not operation.get('done') and time.monotonic()<deadline:
        time.sleep(5)
        operation=r.cloud(op_name)
    if not operation.get('done') or operation.get('error'): raise RuntimeError('readonly_operation_not_successful')
    execution=operation.get('response') or {}
    full_name=execution.get('name','')
    if not full_name.startswith(r.ROOT+'/jobs/'+name+'/executions/'): raise RuntimeError('execution_identity_unknown')
    state['execution']=full_name.rsplit('/',1)[-1]
    save()
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
            if 'outbox_six_hour_events' in result:
                result['batch_forecast']=batch_forecast(result['outbox_six_hour_events'])
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
    if request.get('expected_rollout_run'):
        run=json.loads(r.command(['gh','run','view',str(request['expected_rollout_run']),
            '--json','status,conclusion,workflowName']))
        if run!={'status':'completed','conclusion':'success','workflowName':'Janus GHCR controlled Jobs rollout'}:
            raise ValueError('reference_rollout_not_successful')
    r.fence()
    output={'component':'d06-runtime-reference-census','mode':'read-only','deletion_fence_published':False,'results':[]}
    def save(): Path('d06-runtime-references.json').write_text(json.dumps(output,sort_keys=True))
    for name,expected in request['jobs'].items():
        state={'job':name,'status':'PREFLIGHT'}
        output['results'].append(state)
        try: state.update(probe(name,expected,state,save),status='OBSERVED')
        except Exception as error:
            reason=str(error)
            state.update(status='BLOCKED',error_type=type(error).__name__,
                         reason=reason if re.fullmatch(r'[a-z][a-z0-9_]{3,100}',reason) else 'readback_failure')
            # Unknown execution status must never lead to another dispatch.
            break
    save()
    print(json.dumps(output,sort_keys=True))

if __name__=='__main__': main()
