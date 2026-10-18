"""Run one six-stock Yahoo EPS supplement on the exact deployed dev image."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from ghcr_jobs_rollout import ROOT, cloud, image, job, terminal


def run(request_path):
    req = json.loads(Path(request_path).read_text())
    if (req.get('intent') != 'drl01-yahoo-eps-six-stock-2025q4'
        or req.get('approved') is not True
        or req.get('symbols') != ['1513', '2327', '2382', '3231', '3711', '5876']
        or req.get('period') != '2025Q4'
        or not re.fullmatch(r'ghcr.io/tommylin15/janus-ingestion-core@sha256:[0-9a-f]{64}', req.get('image', ''))):
        raise ValueError('invalid_yahoo_eps_request')
    j = job('janus-ingestion-core')
    if image(j) != req['image']:
        raise ValueError('deployed_image_drift')
    containers = j['template']['template']['containers']
    if len(containers) != 1 or containers[0].get('command') not in (None, [], ['python']):
        raise ValueError('entrypoint_drift')
    override = {'args': ([] if containers[0].get('command') else ['python']) + ['-m', 'ingestion_core.yahoo_eps'],
        'env': [{'name': 'QUEUE_CONSUMER', 'value': 'false'},
                {'name': 'DRL01_YAHOO_EPS_APPROVED', 'value': '2025Q4-six-symbols'}]}
    if containers[0].get('name'):
        override['name'] = containers[0]['name']
    op = cloud(f'{ROOT}/jobs/janus-ingestion-core:run', {'etag': j['etag'], 'overrides': {
        'taskCount': 1, 'timeout': '600s', 'containerOverrides': [override]}}, 'POST')
    operation = op.get('name', '')
    if not operation.startswith(ROOT + '/operations/'):
        raise RuntimeError('unknown_operation_do_not_resubmit')
    print(json.dumps({'operation': operation, 'status': 'SUBMITTED_DO_NOT_RESUBMIT'}), flush=True)
    deadline = time.monotonic() + 660
    while not op.get('done') and time.monotonic() < deadline:
        time.sleep(6)
        op = cloud(operation)
    exe = op.get('response', {})
    if not op.get('done') or op.get('error') or not terminal(exe) or exe.get('succeededCount') != 1:
        raise RuntimeError('yahoo_eps_not_verified_inspect_existing_operation')
    execution = exe['name'].rsplit('/', 1)[-1]
    query = 'resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="' + execution + '"'
    receipt = None
    for _ in range(5):
        cp = subprocess.run(['gcloud', 'logging', 'read', query, '--project=gen-lang-client-0593591102',
                             '--limit=100', '--format=json'], capture_output=True, text=True, timeout=45)
        if cp.returncode == 0:
            for event in json.loads(cp.stdout):
                value = event.get('jsonPayload')
                if not isinstance(value, dict):
                    try:
                        value = json.loads(event.get('textPayload', ''))
                    except (ValueError, TypeError):
                        continue
                if isinstance(value, dict) and value.get('component') == 'drl01_yahoo_eps':
                    receipt = value
        if receipt:
            break
        time.sleep(5)
    output = {'execution': execution, 'receipt': receipt}
    Path('/tmp/drl01-yahoo-eps.json').write_text(json.dumps(output, sort_keys=True, indent=2))
    print(json.dumps(output, sort_keys=True))
    if not receipt or receipt.get('status') != 'PASS':
        raise RuntimeError('yahoo_eps_receipt_not_pass')


if __name__ == '__main__':
    run(sys.argv[1])
