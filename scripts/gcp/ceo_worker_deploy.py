"""Deploy only the approved bounded dev CEO Job; no execution or traffic change."""
import argparse
import json
from pathlib import Path
import time

from ceo_worker_template import JOB, PROJECT, template
from ghcr_jobs_rollout import ROOT, cloud, job, terminal

API_IDENTITY = f'janus-user-api@{PROJECT}.iam.gserviceaccount.com'
ROLES = ('roles/run.jobsExecutorWithOverrides', 'roles/run.viewer')


def execution_fence():
    from urllib.parse import quote
    path = f'{ROOT}/jobs/{JOB}/executions?pageSize=100'
    seen = set()
    while path:
        data = cloud(path)
        assert all(terminal(e) for e in data.get('executions', [])), 'CEO execution not terminal'
        token = data.get('nextPageToken')
        assert not token or token not in seen, 'execution pagination loop'
        seen.add(token)
        path = f'{ROOT}/jobs/{JOB}/executions?pageSize=100&pageToken={quote(token, safe="")}' if token else None


def update_payload(existing, desired):
    previous = json.loads(json.dumps(existing['template']))
    old = previous['template']['containers'][0]['image'].removeprefix('cache.us-docker.pkg.dev/')
    import re
    assert re.fullmatch(r'ghcr.io/tommylin15/janus-intelligence-mart@sha256:[0-9a-f]{64}', old)
    previous['template']['containers'][0]['image'] = desired['template']['template']['containers'][0]['image']
    env = previous['template']['containers'][0].get('env', [])
    target_env = desired['template']['template']['containers'][0]['env']
    legacy = [e for e in env if e['name'] == 'MART_CODEX_AUTH_SECRET']
    if legacy:
        assert legacy == [{'name': 'MART_CODEX_AUTH_SECRET', 'value': 'janus-mart-codex-auth'}]
        added = {'MART_CEO_GEMINI_ONLY', 'MART_GEMINI_MODEL', 'MART_GEMINI_FREE_TIER_CONFIRMED'}
        assert not any(e['name'] in added for e in env), 'CEO configuration drift'
        assert [e for e in env if e['name'] != 'MART_CODEX_AUTH_SECRET'] == [e for e in target_env if e['name'] not in added], 'CEO configuration drift'
        previous['template']['containers'][0]['env'] = target_env
    assert previous == desired['template'], 'CEO configuration drift'
    assert existing['labels'].get('janus-component') == 'manual-ceo'
    return {**desired, 'etag': existing['etag']}


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
    requests = []
    rollback = {}
    if existing is None:
        # CreateJob takes jobId in the URL and requires an empty resource name.
        requests = [(f'{ROOT}/jobs?jobId={JOB}',
                     {key: value for key, value in desired.items() if key != 'name'}, 'POST')]
    elif existing['labels'].get('janus-git-sha') != args.sha:
        execution_fence()
        payload = update_payload(existing, desired)
        import subprocess
        old_image = existing['template']['template']['containers'][0]['image'].removeprefix('cache.us-docker.pkg.dev/')
        public = json.loads(subprocess.check_output(['skopeo', 'inspect', '--no-creds', 'docker://' + old_image], text=True))
        assert public['Digest'] == old_image.split('@')[1]
        assert public['Labels']['org.opencontainers.image.revision'] == existing['labels']['janus-git-sha']
        snapshot = {'name': existing['name'], 'labels': existing['labels'], 'template': existing['template']}
        assert all('value' not in e for e in existing['template']['template']['containers'][0].get('env', [])
                   if any(term in e['name'].upper() for term in ('API_KEY', 'TOKEN', 'AUTH_JSON', 'BUNDLE'))), 'literal credentials cannot enter rollback artifact'
        Path('ceo-worker-rollback.json').write_text(json.dumps(snapshot))
        rollback = {'rollback_image': old_image, 'rollback_sha': existing['labels']['janus-git-sha'],
                    'rollback_template': 'ceo-worker-rollback.json',
                    'previous_provider_usable': False if any(e['name'] == 'MART_CODEX_AUTH_SECRET' for e in existing['template']['template']['containers'][0].get('env', [])) else 'unknown'}
        cloud(path + '?validateOnly=true', payload, 'PATCH')
        requests = [(path, payload, 'PATCH')]
    for target, body, method in requests:
        operation = cloud(target, body, method)
        name = operation.get('name', '')
        assert name.startswith(ROOT + '/operations/')
        deadline = time.monotonic() + 480
        while time.monotonic() < deadline:
            state = cloud(name)
            if state.get('done'):
                if state.get('error'):
                    raise RuntimeError('CEO Job deployment failed; inspect before retry')
                break
            time.sleep(3)
        else:
            raise RuntimeError('CEO Job deployment unknown; no automatic retry')
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
    print(json.dumps({'status': 'PASS', 'job': JOB, 'sha': args.sha, **rollback,
                      'iam_scope': 'this-job-only', 'execution_started': False,
                      'traffic_changed': False, 'scheduler_created': False}))


if __name__ == '__main__':
    main()
