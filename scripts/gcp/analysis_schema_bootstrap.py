"""Apply additive migration 051 using the existing ingestion image and identity.

No image, Scheduler, IAM, canonical data or API traffic changes. The fixed SQL
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
from ingestion_core.serving_schema_migration import _without_role_lines
raw=base64.b64decode(os.environ['JANUS_ANALYSIS_MIGRATION_SQL'],validate=True)
assert hashlib.sha256(raw).hexdigest()==os.environ['JANUS_ANALYSIS_MIGRATION_HASH']
prepare,rest=_without_role_lines(raw.decode()).split('-- PHASE: acceptance',1)
checks,record=rest.split('INSERT INTO control.schema_migrations',1)
control=_control_plane()
try:
 with control.connection.transaction(),control.connection.cursor() as cursor:
  cursor.execute('SELECT current_user')
  assert cursor.fetchone()[0]=='janus_control'
  cursor.execute(prepare)
  cursor.execute(checks)
  assert all(cursor.fetchone())
  cursor.execute('INSERT INTO control.schema_migrations'+record)
 print(json.dumps({'operation':'analysis_schema_bootstrap','migration':'051_analysis_product','status':'PASS'}))
finally:
 control.close()
'''


def payload(source, sql):
    container = source['template']['template']['containers'][0]
    if container.get('command') not in (None, [], ['python']):
        raise ValueError('existing Python ingestion entrypoint required')
    args = (['python'] if not container.get('command') else []) + ['-c', BOOTSTRAP]
    override = {'args': args, 'env': [
        {'name': 'JANUS_ANALYSIS_MIGRATION_SQL', 'value': b64encode(sql).decode()},
        {'name': 'JANUS_ANALYSIS_MIGRATION_HASH', 'value': sha256(sql).hexdigest()}]}
    if container.get('name'):
        override['name'] = container['name']
    return {'etag': source['etag'], 'overrides': {'taskCount': 1, 'timeout': '300s', 'containerOverrides': [override]}}


def main():
    from ghcr_jobs_rollout import cloud, fence, job, terminal, ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source = job('janus-ingestion-core')
    fence()
    sql = (Path(__file__).parents[2] / 'infra/postgres/migrations/051_analysis_product.sql').read_bytes()
    operation = cloud(f'{ROOT}/jobs/janus-ingestion-core:run', payload(source, sql), 'POST')
    name = operation.get('name', '')
    if not name.startswith(ROOT+'/operations/'):
        raise RuntimeError('migration dispatch unknown; no automatic retry')
    receipt = {'migration': '051_analysis_product', 'sql_hash': sha256(sql).hexdigest(),
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
