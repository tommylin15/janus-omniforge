"""Checkpoint-bound fee repair in the existing, release-verified private Job."""
import argparse
import json
import os
from pathlib import Path
import re
import time

import ghcr_jobs_rollout as jobs

JOB = 'janus-private-pipeline'
RUNTIME = r'''
import json,os
from packages.postgres_bundle import load_postgres_bundle
from services.api.repository import PostgresWorkspaceRepository
from scripts.gcp.ledger_fee_repair import repair_owner_fees
load_postgres_bundle('JANUS_API_POSTGRES_BUNDLE', {
 'PRIVATE_DATABASE_URL':('pipeline_database_url','database_url'),
 'MOBILE_LEDGER_DATABASE_URL':'database_url',
 'PRIVATE_CATALOG_PASSWORD':('pipeline_catalog_password','catalog_password'),
 'CORE_CATALOG_PASSWORD':'core_catalog_password',
})
repo=PostgresWorkspaceRepository(os.environ['MOBILE_LEDGER_DATABASE_URL'])
with repo._connection() as connection:
 if connection.execute('SELECT current_user AS role').fetchone()['role']!='janus_private_api':
  raise RuntimeError('private_api_role_required')
 owners=connection.execute("SELECT DISTINCT user_id FROM private.current_positions WHERE symbol=%s",('00719B',)).fetchall()
if len(owners)!=1:
 raise RuntimeError('actual_holder_owner_scope_not_exactly_one')
identity=repo.stock_identities({'00719B'}).get('00719B')
if not identity or identity.get('name')!='元大美債1-3' or identity.get('market')!='TPEX':
 raise RuntimeError('official_owner_binding_identity_drift')
owner=owners[0]['user_id']
checkpoint=json.loads(os.environ['JANUS_FEE_REPAIR_CHECKPOINT'])
result=repair_owner_fees(repo,owner,expected_ledger_version=checkpoint['ledger_version'],
 expected_profile_version=checkpoint['profile_version'],apply=checkpoint['mode']=='apply')
print(json.dumps({'operation':'ledger_fee_repair',**result},sort_keys=True),flush=True)
if checkpoint['mode'] in ('apply','reconcile'):
 if checkpoint['mode']=='reconcile' and (result.get('status')!='preview' or result.get('corrections')!=0):
  raise RuntimeError('reconciliation_requires_zero_pending_fee_corrections')
 from scripts.gcp.holdings_p0_owner_live_probe import OWNER_CODE
 exec(OWNER_CODE,{})
 check=repair_owner_fees(repo,owner,expected_ledger_version=result.get('ledger_version',checkpoint['ledger_version']),
  expected_profile_version=result['broker_profile_version'])
 if check.get('corrections')!=0:
  raise RuntimeError('post_mart_fee_readback_mismatch')
'''


def validate_request(value):
    if (value.get('intent') != 'checkpoint-bound-owner-fee-repair'
            or value.get('approved') is not True
            or value.get('scope') != 'single-real-owner-holding-00719B'
            or value.get('mode') not in {'preview', 'apply', 'reconcile'}
            or not re.fullmatch(r'[0-9a-f]{40}', str(value.get('source_sha', '')))
            or not re.fullmatch(r'ghcr\.io/tommylin15/janus-private-pipeline@sha256:[0-9a-f]{64}', str(value.get('image', '')))
            or not re.fullmatch(r'[0-9a-f]{64}', str(value.get('configuration_hash', '')))
            or any(not isinstance(value.get(key), str) or not value[key].isdigit()
                   for key in ('release_run', 'rollout_run', 'boundary_run'))
            or any(type(value.get(key)) is not int or value[key] < 0
                   for key in ('ledger_version', 'profile_version'))):
        raise ValueError('fee_repair_request_invalid')
    return value


def main():
    if os.getenv('GITHUB_REF') != 'refs/heads/main' or os.getenv('GITHUB_REPOSITORY') != 'tommylin15/janus-omniforge':
        raise ValueError('fee_repair_requires_repository_main')
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    req = validate_request(json.loads(args.request.read_text()))
    jobs.automated_oauth_acceptance(req['source_sha'], req['boundary_run'])
    for field, workflow in (('release_run', 'Janus GHCR full-test image publication'),
                            ('rollout_run', 'Janus GHCR controlled Jobs rollout')):
        run = json.loads(jobs.command(['gh', 'run', 'view', req[field], '--json',
                                      'headSha,status,conclusion,workflowName']))
        if run.get('status') != 'completed' or run.get('conclusion') != 'success' or run.get('workflowName') != workflow:
            raise ValueError('fee_repair_provenance_incomplete')
        if field == 'release_run':
            if run.get('headSha') != req['source_sha']:
                raise ValueError('fee_repair_release_source_mismatch')
        else:
            recorded = json.loads(jobs.command(['git', 'show', run['headSha']+':ops/ghcr-jobs-rollout-request.json']))
            if recorded.get('sha') != req['source_sha']:
                raise ValueError('fee_repair_rollout_source_mismatch')
    data = jobs.checked_image(JOB, req['image'], req['configuration_hash'])
    if len(data['template']['template']['containers']) != 1:
        raise ValueError('fee_repair_single_container_required')
    manifest = json.loads(jobs.command(['skopeo', 'inspect', '--no-creds', 'docker://'+req['image']]))
    if manifest.get('Labels', {}).get('org.opencontainers.image.revision') != req['source_sha']:
        raise ValueError('fee_repair_image_source_mismatch')
    jobs.fence()
    jobs.command(jobs.LEASE + ['acquire'])
    dispatched = False
    try:
        jobs.fence()
        data = jobs.checked_image(JOB, req['image'], jobs.fingerprint(data))
        container = data['template']['template']['containers'][0]
        command = container.get('command')
        if command not in (None, [], ['python']):
            raise ValueError('fee_repair_entrypoint_invalid')
        checkpoint = {key: req[key] for key in ('mode', 'ledger_version', 'profile_version')}
        override = {'args': (['python'] if not command else [])+['-c', RUNTIME],
                    'env': [{'name': 'JANUS_FEE_REPAIR_CHECKPOINT', 'value': json.dumps(checkpoint)}]}
        if container.get('name'):
            override['name'] = container['name']
        receipt = {'status': 'UNKNOWN', 'source_sha': req['source_sha'], **checkpoint}
        args.receipt.write_text(json.dumps(receipt))
        # Retain the lease for every unknown dispatch or failed execution.
        dispatched = True
        operation = jobs.cloud(f'{jobs.ROOT}/jobs/{JOB}:run', {'etag': data['etag'], 'overrides': {
            'taskCount': 1, 'timeout': '900s', 'containerOverrides': [override]}}, 'POST')
        name = operation.get('name', '')
        if not name.startswith(jobs.ROOT+'/operations/'):
            raise RuntimeError('fee_repair_dispatch_unknown')
        receipt['operation'] = name
        args.receipt.write_text(json.dumps(receipt))
        deadline = time.monotonic()+1050
        while not operation.get('done') and time.monotonic() < deadline:
            time.sleep(6)
            operation = jobs.cloud(name)
        if not operation.get('done') or operation.get('error'):
            raise RuntimeError('fee_repair_execution_failed_or_unknown_inspect_before_retry')
        execution = operation.get('response', {})
        if execution.get('name', '').startswith(jobs.ROOT+f'/jobs/{JOB}/executions/'):
            execution = jobs.cloud(execution['name'])
        if not jobs.terminal(execution) or execution.get('succeededCount') != 1 or execution.get('failedCount', 0):
            raise RuntimeError('fee_repair_execution_not_verified')
        receipt.update(status='PASS', execution=execution['name'].split('/')[-1])
        args.receipt.write_text(json.dumps(receipt))
        print(json.dumps(receipt, sort_keys=True))
        dispatched = False
    finally:
        if not dispatched:
            jobs.command(jobs.LEASE + ['release', '--safe-to-release'])


if __name__ == '__main__':
    main()
