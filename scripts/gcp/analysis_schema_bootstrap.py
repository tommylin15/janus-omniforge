"""Apply allowlisted analysis migrations using the existing ingestion image and identity.

No image, Scheduler, project IAM, canonical ledger data or API traffic changes.
Owner phases may temporarily grant schema CREATE, revoked even on failure. The fixed SQL
is public repository code; credentials remain inside the existing Job runtime.
"""
import argparse
from base64 import b64encode
from hashlib import sha256
import json
from pathlib import Path
import time

BOOTSTRAP = '''import base64,hashlib,json,os
from ingestion_core.__main__ import _control_plane
from ingestion_core.serving_schema_migration import _without_role_lines, _publication_connection, _private_api_connection
raw=base64.b64decode(os.environ['JANUS_ANALYSIS_MIGRATION_SQL'],validate=True)
assert hashlib.sha256(raw).hexdigest()==os.environ['JANUS_ANALYSIS_MIGRATION_HASH']
prepare,rest=_without_role_lines(raw.decode()).split('-- PHASE: acceptance',1)
checks,record=rest.split('INSERT INTO control.schema_migrations',1)
control=_control_plane()
try:
 if os.environ['JANUS_ANALYSIS_MIGRATION_NAME']=='059_ledger_automatic_charges':
  raise RuntimeError('migration 059 requires the existing PostgreSQL owner operator path')
 if '-- PHASE: private-api' in prepare:
  control_sql,private_rest=prepare.split('-- PHASE: private-api',1)
  private_sql,finalize_sql=private_rest.split('-- PHASE: control-finalize',1)
  with control.connection.transaction(),control.connection.cursor() as cursor:
   cursor.execute(control_sql)
  private=None
  try:
   private=_private_api_connection()
   with private.transaction(),private.cursor() as cursor:
    cursor.execute(private_sql)
  finally:
   if private is not None: private.close()
   with control.connection.transaction(),control.connection.cursor() as cursor:
    cursor.execute('REVOKE CREATE ON SCHEMA private FROM janus_private_api')
  prepare=finalize_sql
 if '-- PHASE: publication' in prepare:
  control_sql,publication_sql=prepare.split('-- PHASE: publication',1)
  with control.connection.transaction(),control.connection.cursor() as cursor:
   cursor.execute(control_sql)
  publication=_publication_connection()
  try:
   with publication.transaction(),publication.cursor() as cursor:
    cursor.execute(publication_sql)
    cursor.execute(checks)
    assert all(cursor.fetchone())
  finally:
   publication.close()
  prepare='SELECT 1'
  checks='SELECT true'
 with control.connection.transaction(),control.connection.cursor() as cursor:
  cursor.execute('SELECT current_user')
  assert cursor.fetchone()[0]=='janus_control'
  cursor.execute(prepare)
  cursor.execute(checks)
  assert all(cursor.fetchone())
  cursor.execute('INSERT INTO control.schema_migrations'+record)
 print(json.dumps({'operation':'analysis_schema_bootstrap','migration':os.environ['JANUS_ANALYSIS_MIGRATION_NAME'],'status':'PASS'}))
finally:
 control.close()
'''


def payload(source, sql, migration='051_analysis_product'):
    if migration not in {'051_analysis_product', '052_ceo_daily_quota_50', '054_market_serving', '055_full_market_universe', '056_controller_ledger_backup', '057_home_market_snapshot', '058_official_held_etf_identity', '059_ledger_automatic_charges'}:
        raise ValueError('migration not approved for bootstrap')
    container = source['template']['template']['containers'][0]
    if container.get('command') not in (None, [], ['python']):
        raise ValueError('existing Python ingestion entrypoint required')
    args = (['python'] if not container.get('command') else []) + ['-c', BOOTSTRAP]
    override = {'args': args, 'env': [
        {'name': 'JANUS_ANALYSIS_MIGRATION_SQL', 'value': b64encode(sql).decode()},
        {'name': 'JANUS_ANALYSIS_MIGRATION_HASH', 'value': sha256(sql).hexdigest()},
        {'name': 'JANUS_ANALYSIS_MIGRATION_NAME', 'value': migration}]}
    if container.get('name'):
        override['name'] = container['name']
    return {'etag': source['etag'], 'overrides': {'taskCount': 1, 'timeout': '300s', 'containerOverrides': [override]}}


def main():
    from ghcr_jobs_rollout import cloud, fence, job, terminal, ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--migration', choices=('051_analysis_product', '052_ceo_daily_quota_50', '054_market_serving', '055_full_market_universe', '056_controller_ledger_backup', '057_home_market_snapshot', '058_official_held_etf_identity', '059_ledger_automatic_charges'),
                        default='051_analysis_product')
    args = parser.parse_args()
    if args.migration == '059_ledger_automatic_charges':
        parser.error('migration 059 requires the existing PostgreSQL owner operator path')
    source = job('janus-ingestion-core')
    fence()
    sql = (Path(__file__).parents[2] / 'infra/postgres/migrations' / f'{args.migration}.sql').read_bytes()
    operation = cloud(f'{ROOT}/jobs/janus-ingestion-core:run', payload(source, sql, args.migration), 'POST')
    name = operation.get('name', '')
    if not name.startswith(ROOT+'/operations/'):
        raise RuntimeError('migration dispatch unknown; no automatic retry')
    receipt = {'migration': args.migration, 'sql_hash': sha256(sql).hexdigest(),
               'operation': name, 'status': 'UNKNOWN', 'traffic_changed': False, 'image_changed': False}
    args.receipt.write_text(json.dumps(receipt), encoding='utf-8')
    deadline = time.monotonic()+360
    while time.monotonic() < deadline:
        current = cloud(name)
        if current.get('done'):
            if current.get('error'):
                raise RuntimeError('migration operation failed; inspect execution before retry')
            execution = current.get('response', {})
            execution_name = execution.get('name', '')
            if execution_name.startswith(ROOT+'/jobs/janus-ingestion-core/executions/'):
                execution = cloud(execution_name)
            if terminal(execution) and execution.get('succeededCount') == 1 and not execution.get('failedCount', 0):
                receipt.update(status='PASS', execution=execution_name)
                args.receipt.write_text(json.dumps(receipt), encoding='utf-8')
                print(json.dumps(receipt))
                return
            if terminal(execution):
                raise RuntimeError('migration execution failed; no automatic retry')
        time.sleep(3)
    raise RuntimeError('migration outcome unknown; no automatic retry')


if __name__ == '__main__':
    main()
