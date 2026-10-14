"""One bounded official-data execution and verified coverage; no Job config writes."""
import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

import ghcr_jobs_rollout as rollout

JOB = 'janus-ingestion-core'
VERIFY = '''
def verify_inventory(inventory, day):
    assert inventory['scope'] == 'all_listed_otc_equities'
    assert inventory['universe_status'] == 'available' and inventory['universe_version']
    assert inventory['coverage_status'] == 'complete' and inventory['coverage_accepted']
    receipts = inventory['items']
    assert {'TWSE', 'TPEX'} <= {r['market'] for r in receipts if r.get('expected_count')}
    for r in receipts:
        if r.get('expected_count'):
            assert r['expected_count']>0 and r['received_count']>=0 and r['missing_count']>=0
            assert r['date']==day and r['coverage_accepted']
            assert r['received_count']+r['missing_count']==r['expected_count']
            limits = {'TWSE': 1, 'TPEX': 3, 'ALL': 0}
            assert r['market'] in limits
            assert r.get('max_missing_ratio') == limits[r['market']] / 10
            assert r['missing_count'] * 10 <= r['expected_count'] * limits[r['market']]
            if r['dataset']=='outside_500_registered_portfolio_ohlcv':
                assert r.get('snapshot_ids') and r.get('stage_provenance_ids')
            else:
                assert r.get('snapshot_id') and r.get('stage_provenance_id')
    return [{k:r.get(k) for k in ('date','source','dataset','market','expected_count',
             'received_count','missing_count','max_missing_ratio','coverage_accepted',
             'snapshot_id','snapshot_ids','cache_hit')}
            for r in receipts if r.get('expected_count')]
'''

CODE = VERIFY + '''
import json,hashlib,os
from ingestion_core.__main__ import run_scheduled_collection
from ingestion_core.stage import GcsObjectStore
try:
    result=run_scheduled_collection()
    assert result['status']=='succeeded' and result['coverage_status']=='complete'
    bucket,key=result['coverage_inventory_uri'].removeprefix('gs://').split('/',1)
    raw=GcsObjectStore(bucket).read(key)
    assert 'sha256:'+hashlib.sha256(raw).hexdigest()==result['coverage_inventory_hash']
    inventory=json.loads(raw)
    receipts=verify_inventory(inventory,result['as_of'])
    if os.environ['JANUS_FULL_MARKET_ACCEPTANCE_PHASE']=='cached':
        assert result['staged']==0 and all(r['cache_hit'] for r in receipts)
    print(json.dumps({'operation':'full_market_dev_acceptance','status':'PASS',
          'phase':os.environ['JANUS_FULL_MARKET_ACCEPTANCE_PHASE'],
          'execution_id':result['execution_id'],'date':result['as_of'],
          'universe_version':inventory['universe_version'],
          'members':len(inventory['effective_symbols']),
          'staged':result['staged'],'serving_published':result['serving_published'],
          'inventory_hash':result['coverage_inventory_hash'],'coverage':receipts},sort_keys=True))
except Exception as error:
    print(json.dumps({'operation':'full_market_dev_acceptance','status':'FAIL',
          'error_code':type(error).__name__},sort_keys=True))
    raise SystemExit(1) from None
'''


def payload(source, phase, day):
    if phase not in {'bootstrap', 'cached'} or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        raise ValueError('invalid bounded acceptance request')
    date.fromisoformat(day)
    containers = source['template']['template']['containers']
    if len(containers) != 1 or containers[0].get('command') not in (None, [], ['python']):
        raise ValueError('unknown ingestion entrypoint')
    container = containers[0]
    override = {'args': ([] if container.get('command') else ['python']) + ['-c', CODE],
                'env': [{'name': k, 'value': v} for k,v in {
                    'FORCE_REFRESH': 'true' if phase == 'bootstrap' else 'false',
                    'INGESTION_DATE': '', 'BACKFILL_START_DATE': '', 'BACKFILL_END_DATE': '',
                    'INGESTION_DATASETS': '', 'MART_JOB': '', 'QUEUE_CONSUMER': 'false',
                    'JANUS_FULL_MARKET_ACCEPTANCE_PHASE': phase,
                }.items()]}
    if container.get('name'):
        override['name'] = container['name']
    return {'etag': source['etag'], 'overrides': {
        'taskCount': 1, 'timeout': '1200s', 'containerOverrides': [override]}}


def verified_terminal_business_success(result, known):
    """Only a fully verified terminal business PASS permits owned lease release."""
    return (known is True and result.get('status') == 'PASS'
            and isinstance(result.get('business'), dict)
            and result['business'].get('status') == 'PASS')


def run(release_run, boundary_run, phase, receipt):
    source_sha = json.loads(Path('ops/ghcr-candidate-request.json').read_text())['sha']
    release = json.loads(rollout.command(['gh','run','view',release_run,
        '--json','headSha,status,conclusion,workflowName']))
    if (release['headSha'] != source_sha or release['status'] != 'completed'
            or release['conclusion'] != 'success'
            or release['workflowName'] != 'Janus GHCR full-test image publication'):
        raise ValueError('full exact-source release required')
    rollout.automated_oauth_acceptance(source_sha, boundary_run)
    manifest = json.loads(rollout.command(['skopeo','inspect','--no-creds',
        'docker://ghcr.io/tommylin15/janus-ingestion-core:sha-'+source_sha]))
    if manifest['Labels']['org.opencontainers.image.revision'] != source_sha:
        raise ValueError('immutable source mismatch')
    target = 'ghcr.io/tommylin15/janus-ingestion-core@'+manifest['Digest']
    source = rollout.job(JOB)
    config_hash = rollout.fingerprint(source)
    rollout.checked_image(JOB, target, config_hash)
    rollout.legacy_writers()
    rollout.fence()
    rollout.command(rollout.LEASE + ['acquire'])
    known = False
    result = {'source_sha': source_sha, 'phase': phase, 'status': 'UNKNOWN',
              'job_configuration_changed': False, 'traffic_changed': False}
    def save(): receipt.write_text(json.dumps(result,indent=2)+'\n')
    try:
        rollout.fence()
        current = rollout.checked_image(JOB, target, config_hash)
        day = datetime.now(ZoneInfo('Asia/Taipei')).date().isoformat()
        operation = rollout.cloud(f'{rollout.ROOT}/jobs/{JOB}:run', payload(current, phase, day), 'POST')
        name = operation.get('name','')
        if not name.startswith(rollout.ROOT+'/operations/'):
            raise RuntimeError('unknown dispatch; no automatic retry')
        result['operation'] = name
        save()
        deadline = time.monotonic()+2700
        while not operation.get('done') and time.monotonic() < deadline:
            time.sleep(8)
            operation = rollout.cloud(name)
        if not operation.get('done'):
            raise RuntimeError('unknown execution; retain lease')
        known = True
        if operation.get('error'):
            result['status'] = 'FAIL'
            raise RuntimeError('business execution failed; inspect before retry')
        execution = operation.get('response',{})
        if (not rollout.terminal(execution) or execution.get('succeededCount') != 1
                or execution.get('failedCount',0)):
            known = False
            raise RuntimeError('unverified terminal execution; retain lease')
        execution_name = execution['name'].split('/')[-1]
        result['execution'] = execution_name
        business = []
        for attempt in range(12):
            entries = json.loads(rollout.command(['gcloud','logging','read',
                f'resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="{execution_name}"',
                '--project='+rollout.PROJECT,'--freshness=1h','--limit=50','--order=desc','--format=json']))
            for entry in entries:
                value = entry.get('jsonPayload')
                if value is None:
                    try: value = json.loads(entry.get('textPayload',''))
                    except (ValueError,TypeError): continue
                if isinstance(value,dict) and value.get('operation') == 'full_market_dev_acceptance':
                    business.append(value)
            if business: break
            if attempt < 11: time.sleep(5)
        if not business or business[0].get('status') != 'PASS':
            raise RuntimeError('verified business receipt missing')
        result.update(status='PASS',business=business[0])
        rollout.checked_image(JOB, target, config_hash)
        save()
        print(json.dumps(result,sort_keys=True))
    finally:
        save()
        if verified_terminal_business_success(result, known):
            rollout.checked_image(JOB, target, config_hash)
            rollout.fence()
            rollout.command(rollout.LEASE + ['release', '--safe-to-release'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--release-run', required=True)
    parser.add_argument('--boundary-run', required=True)
    parser.add_argument('--phase', choices=('bootstrap','cached'), required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    run(args.release_run,args.boundary_run,args.phase,args.receipt)
