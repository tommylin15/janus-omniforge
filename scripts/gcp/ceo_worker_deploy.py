"""Create only the explicitly approved dev CEO Job; no execution or traffic change."""
import argparse
import json
from pathlib import Path
import time

from ceo_worker_template import JOB, PROJECT, template
from ghcr_jobs_rollout import ROOT, cloud, job

API_IDENTITY = f'janus-user-api@{PROJECT}.iam.gserviceaccount.com'
ROLES = ('roles/run.jobsExecutorWithOverrides', 'roles/run.viewer')


def bind_api(policy, identity):
    if identity != API_IDENTITY:
        raise ValueError('existing API identity required')
    member = 'serviceAccount:' + identity
    result = json.loads(json.dumps(policy))
    bindings = result.setdefault('bindings', [])
    for role in ROLES:
        binding = next((b for b in bindings if b['role'] == role and not b.get('condition')), None)
        if binding is None:
            binding = {'role': role, 'members': []}
            bindings.append(binding)
        if member not in binding['members']:
            binding['members'].append(member)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    parser.add_argument('--sha', required=True)
    args = parser.parse_args()
    plan = json.loads(Path('ops/ceo-worker-plan.json').read_text())
    assert plan['approved'] is True and plan['job'] == JOB
    desired = template(job('janus-intelligence-mart'), args.image, args.sha)
    api = cloud(f'{ROOT}/services/janus-api')
    assert api['template']['serviceAccount'] == API_IDENTITY
    path = f'{ROOT}/jobs/{JOB}'
    try:
        existing = cloud(path)
    except RuntimeError as error:
        if str(error) != 'cloud_control_http_404':
            raise
        existing = None
    if existing is None:
        operation = cloud(f'{ROOT}/jobs?jobId={JOB}', desired, 'POST')
        name = operation.get('name', '')
        assert name.startswith(ROOT + '/operations/')
        deadline = time.monotonic() + 480
        while time.monotonic() < deadline:
            state = cloud(name)
            if state.get('done'):
                if state.get('error'):
                    raise RuntimeError('CEO Job creation failed; inspect before retry')
                break
            time.sleep(3)
        else:
            raise RuntimeError('CEO Job creation unknown; no automatic retry')
        existing = cloud(path)
    task = existing['template']['template']
    expected_task = desired['template']['template']
    assert len(task['containers']) == 1
    container = task['containers'][0]
    assert not existing.get('reconciling')
    assert existing['terminalCondition']['state'] == 'CONDITION_SUCCEEDED'
    assert container['image'].removeprefix('cache.us-docker.pkg.dev/') == args.image
    assert existing.get('labels', {}).get('janus-git-sha') == args.sha
    assert task['serviceAccount'] == desired['template']['template']['serviceAccount']
    assert task['timeout'] == '480s' and task.get('maxRetries', 0) == 0
    assert container['resources']['limits'] == {'cpu': '1', 'memory': '1Gi'}
    assert existing['template'].get('taskCount', 1) == 1
    assert existing['template'].get('parallelism', 1) == 1
    assert task.get('vpcAccess') == expected_task.get('vpcAccess')
    for key in ('name', 'command', 'args', 'env'):
        assert container.get(key) == expected_task['containers'][0].get(key)
    policy = cloud(path + ':getIamPolicy')
    expected = bind_api(policy, API_IDENTITY)
    cloud(path + ':setIamPolicy', {'policy': expected}, 'POST')
    readback = cloud(path + ':getIamPolicy')
    member = 'serviceAccount:' + API_IDENTITY
    assert all(any(b['role'] == role and not b.get('condition') and member in b['members']
                   for b in readback.get('bindings', [])) for role in ROLES)
    print(json.dumps({'status': 'PASS', 'job': JOB, 'sha': args.sha,
                      'iam_scope': 'this-job-only', 'execution_started': False,
                      'traffic_changed': False, 'scheduler_created': False}))


if __name__ == '__main__':
    main()
