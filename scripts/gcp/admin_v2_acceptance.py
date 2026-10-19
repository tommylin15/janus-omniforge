"""Bounded synthetic usage acceptance in the existing, exact-image dev Job."""
import argparse
import json
import re
import time
from pathlib import Path

import ghcr_jobs_rollout as rollout


CANARY = r'''
import json,time,uuid
from datetime import datetime,timezone,timedelta
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import PostgresWorkspaceRepository
from services.api.usage import UsageBatch,UsageService,TAIPEI
load_postgres_bundle('JANUS_API_POSTGRES_BUNDLE',{
 'ADMIN_V2_WRITER_DSN':'database_url',
 'ADMIN_V2_CLEANUP_DSN':'pipeline_database_url'})
import os
writer=PostgresWorkspaceRepository(os.environ['ADMIN_V2_WRITER_DSN'])
cleaner=PostgresWorkspaceRepository(os.environ['ADMIN_V2_CLEANUP_DSN'])
owner=writer.resolve_user('admin-v2-synthetic-'+uuid.uuid4().hex,'admin-v2-canary@example.invalid')
usage=UsageService(writer)
tables=('usage_recent_events','usage_ingest_receipts','usage_user_feature_daily','usage_daily_sessions','usage_preferences')
def sizes():
 with writer._connection() as db:
  return db.execute("SELECT sum(pg_total_relation_size(t)) AS bytes FROM unnest(ARRAY['private.usage_recent_events','private.usage_ingest_receipts','private.usage_user_feature_daily','private.usage_daily_sessions']) t").fetchone()['bytes']
def io():
 with writer._connection() as db:
  return db.execute('SELECT blks_read,blks_hit FROM pg_stat_database WHERE datname=current_database()').fetchone()
result={'component':'admin-v2-synthetic-acceptance','status':'UNKNOWN','financial_mutations':0}
contributed=0
try:
 assert usage.preference(owner)['enabled'] is False
 usage.preference(owner,True)
 initial=sizes();before_io=io();cpu=time.process_time();durations=[];session=uuid.uuid4()
 now=datetime.now(timezone.utc)
 for index in range(6):
  events=[{'event_id':str(uuid.uuid4()),'session_id':str(session),'feature_id':'journal',
   'event_type':'feature_action','action_key':'save','client_time':now.isoformat()} for _ in range(20)]
  value=UsageBatch.model_validate({'batch_id':str(uuid.uuid4()),'events':events})
  started=time.perf_counter();accepted=usage.ingest(owner,value)['accepted'];contributed+=accepted
  assert accepted==20
  durations.append((time.perf_counter()-started)*1000)
  assert usage.ingest(owner,value)['status']=='duplicate'
 data=usage.read(actor='admin-v2-synthetic-canary',user_id=owner)
 assert sum(row['actions'] for row in data['items'])==120
 assert sum(row['sessions'] for row in data['items'])==1
 assert usage.read(actor='admin-v2-synthetic-canary',user_id=uuid.uuid4())['status']=='no_data'
 for _ in range(30):
  started=time.perf_counter();usage.read(actor='admin-v2-synthetic-canary',user_id=owner)
  durations.append((time.perf_counter()-started)*1000)
 usage.preference(owner,False)
 assert usage.ingest(owner,value)['status']=='disabled'
 assert sorted(durations[6:])[28] <= 2000
 assert int(sizes()-initial) <= 2097152
 after_io=io()
 result.update(status='PASS',events=120,read_samples=30,
  p95_ms=round(sorted(durations[6:])[28],2),ingest_max_ms=round(max(durations[:6]),2),
  cpu_seconds=round(time.process_time()-cpu,4),storage_growth_bytes=int(sizes()-initial),
  shared_db_io_delta={key:after_io[key]-before_io[key] if after_io[key]>=before_io[key] else None for key in before_io},
  measurement_scope='synthetic service+real PostgreSQL; excludes browser/auth and concurrent DB load')
 usage.delete(owner)
 assert usage.read(actor='admin-v2-synthetic-canary',user_id=owner)['status']=='no_data'
finally:
 if contributed:
  with writer._connection() as db:
   row=db.execute("""UPDATE private.usage_monthly_summary SET actions=actions-%s
    WHERE month=%s AND feature_id='journal' AND actions >= %s RETURNING actions""",
    (contributed,now.astimezone(TAIPEI).date().replace(day=1),contributed)).fetchone()
   assert row is not None
 with cleaner._connection() as db:
  for table in tables:db.execute('DELETE FROM private.'+table+' WHERE user_id=%s',(owner,))
  db.execute("DELETE FROM private.usage_access_audit WHERE actor='admin-v2-synthetic-canary'")
  db.execute('DELETE FROM private.users WHERE user_id=%s AND google_sub LIKE %s',(owner,'admin-v2-synthetic-%'))
 with writer._connection() as db:
  assert db.execute('SELECT count(*) AS n FROM private.users WHERE user_id=%s',(owner,)).fetchone()['n']==0
 result['synthetic_cleanup_verified']=True
print(json.dumps(result,sort_keys=True))
'''


def checked_source(source, approved):
    if not approved or not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('explicit_exact_source_acceptance_required')
    return source


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--release-run',required=True)
    parser.add_argument('--approved',action='store_true')
    args=parser.parse_args()
    source=checked_source(args.source,args.approved)
    if not re.fullmatch(r'[0-9]+',args.release_run):
        raise ValueError('numeric_release_run_required')
    release=json.loads(rollout.command(['gh','run','view',args.release_run,'--json','headSha,status,conclusion,workflowName']))
    if release.get('headSha') != source or not rollout.successful_operation(release,args.release_run,'Janus GHCR full-test image publication','release'):
        raise ValueError('full_exact_source_release_required')
    manifest=json.loads(rollout.command(['skopeo','inspect','--no-creds',f'docker://ghcr.io/tommylin15/janus-private-pipeline:sha-{source}']))
    expected='ghcr.io/tommylin15/janus-private-pipeline@'+manifest['Digest']
    if not rollout.PIN.fullmatch(expected):
        raise ValueError('immutable_image_required')
    current=rollout.job('janus-private-pipeline')
    if rollout.image(current)!=expected:
        raise ValueError('existing_job_exact_image_required')
    fingerprint=rollout.fingerprint(current)
    rollout.wait_for_terminal_executions()
    rollout.command(rollout.LEASE+['acquire'])
    safe=True
    try:
        rollout.command(rollout.LEASE+['assert'])
        rollout.fence()
        current=rollout.checked_image('janus-private-pipeline',expected,fingerprint)
        container=current['template']['template']['containers'][0]
        if container.get('command') not in (None,[],['python']):
            raise ValueError('existing_python_entrypoint_required')
        override={'args':['-c',CANARY] if container.get('command')==['python'] else ['python','-c',CANARY]}
        if container.get('name'):override['name']=container['name']
        safe=False
        op=rollout.cloud(f'{rollout.ROOT}/jobs/janus-private-pipeline:run',{
            'etag':current['etag'],'overrides':{'taskCount':1,'timeout':'300s','containerOverrides':[override]}},'POST')
        operation=op.get('name','')
        if not operation.startswith(rollout.ROOT+'/operations/'):
            raise RuntimeError('unknown_execution_retain_lease')
        end=time.monotonic()+360
        while not op.get('done') and time.monotonic()<end:
            time.sleep(6);op=rollout.cloud(operation)
        if not op.get('done') or op.get('error'):
            raise RuntimeError('acceptance_not_successful_do_not_retry')
        execution=op.get('response',{})
        if not str(execution.get('name','')).startswith(rollout.ROOT+'/jobs/janus-private-pipeline/executions/'):
            raise RuntimeError('execution_identity_not_verified')
        execution=rollout.cloud(execution['name'])
        if not rollout.terminal(execution) or execution.get('succeededCount')!=1 or execution.get('failedCount',0):
            raise RuntimeError('acceptance_terminal_not_verified')
        rollout.checked_image('janus-private-pipeline',expected,fingerprint)
        safe=True
        receipt={'status':'PASS','source_sha':source,'execution':execution['name'],
                 'job_template_mutation':False,'traffic_mutation':False,'financial_mutations':0}
        Path('admin-v2-acceptance.json').write_text(json.dumps(receipt))
        print(json.dumps(receipt))
    finally:
        if safe:rollout.command(rollout.LEASE+['release','--safe-to-release'])


if __name__=='__main__':main()
