import importlib.util
from pathlib import Path
import sys
import json

import pytest

path = Path(__file__).parents[1] / 'scripts/gcp/ceo_worker_template.py'
spec = importlib.util.spec_from_file_location('ceo_worker_template', path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def source():
    return {'name': f'projects/{worker.PROJECT}/locations/{worker.REGION}/jobs/janus-intelligence-mart',
            'template': {'template': {'serviceAccount': f'intelligence-mart@{worker.PROJECT}.iam.gserviceaccount.com',
                'vpcAccess': {'networkInterfaces': [{'network': 'existing'}]},
                'containers': [{'image': 'old', 'env': [{'name': 'BUNDLE', 'valueSource': {'secretKeyRef': {'secret': 'existing', 'version': 'latest'}}}]}]}}}


def test_dedicated_worker_preserves_private_network_and_secret_references():
    old = source()
    result = worker.template(old, 'ghcr.io/tommylin15/janus-intelligence-mart@sha256:'+'1'*64, 'a'*40)
    task = result['template']['template']
    assert task['maxRetries'] == 0 and task['timeout'] == '480s'
    assert task['vpcAccess'] == old['template']['template']['vpcAccess']
    assert task['containers'][0]['resources']['limits'] == {'cpu': '1', 'memory': '1Gi'}
    assert task['containers'][0]['env'][0] == old['template']['template']['containers'][0]['env'][0]
    assert old['template']['template']['containers'][0]['image'] == 'old'
    assert result['name'].endswith('/jobs/janus-ceo-analysis')
    env = {e['name']: e for e in task['containers'][0]['env']}
    assert env['MART_CEO_GEMINI_ONLY']['value'] == 'true'
    assert env['MART_GEMINI_MODEL']['value'] == 'gemini-3.5-flash-lite'
    assert 'MART_CODEX_AUTH_SECRET' not in env and 'GEMINI_API_KEY' not in env


def test_worker_rejects_mutable_image_and_wrong_source():
    with pytest.raises(ValueError):
        worker.template(source(), 'ghcr.io/tommylin15/janus-intelligence-mart:latest', 'a'*40)
    old = source()
    old['name'] = 'other-project'
    with pytest.raises(ValueError):
        worker.template(old, 'ghcr.io/tommylin15/janus-intelligence-mart@sha256:'+'1'*64, 'a'*40)


def test_additive_schema_bootstrap_carries_only_public_hash_fenced_sql():
    path = Path(__file__).parents[1] / 'scripts/gcp/analysis_schema_bootstrap.py'
    spec = importlib.util.spec_from_file_location('analysis_schema_bootstrap', path)
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    old = source()
    old['etag'] = 'e'
    payload = bootstrap.payload(old, b'public SQL')
    assert payload['overrides']['containerOverrides'][0]['args'][:2] == ['python', '-c']
    assert 'image' not in payload['overrides']['containerOverrides'][0]
    assert payload['etag'] == 'e'


def test_api_binding_preserves_existing_and_conditional_policy_without_broadening_identity():
    sys.path.insert(0, str(path.parent))
    from ceo_worker_deploy import API_IDENTITY, bind_api
    policy = {'etag': 'fence', 'bindings': [
        {'role': 'roles/run.viewer', 'members': ['serviceAccount:existing'],
         'condition': {'expression': 'false', 'title': 'restricted'}},
        {'role': 'roles/run.invoker', 'members': ['serviceAccount:other']}]}
    result = bind_api(policy, API_IDENTITY)
    assert result['etag'] == 'fence' and result['bindings'][:2] == policy['bindings']
    assert len(policy['bindings']) == 2
    assert bind_api(result, API_IDENTITY) == result
    assert all(b['members'] == ['serviceAccount:' + API_IDENTITY] for b in result['bindings'][2:])
    with pytest.raises(ValueError):
        bind_api(policy, 'other@other-project.iam.gserviceaccount.com')


def test_existing_worker_update_is_image_only_and_etag_fenced():
    sys.path.insert(0, str(path.parent))
    from ceo_worker_deploy import update_payload
    old = worker.template(source(), 'ghcr.io/tommylin15/janus-intelligence-mart@sha256:'+'1'*64, 'a'*40)
    old['etag'] = 'fence'
    desired = worker.template(source(), 'ghcr.io/tommylin15/janus-intelligence-mart@sha256:'+'2'*64, 'b'*40)
    assert update_payload(old, desired)['etag'] == 'fence'
    old['template']['template']['timeout'] = '1800s'
    with pytest.raises(AssertionError):
        update_payload(old, desired)


def test_worker_migrates_only_exact_retired_codex_env_to_gemini_lite():
    sys.path.insert(0, str(path.parent))
    from ceo_worker_deploy import update_payload
    desired = worker.template(source(), 'ghcr.io/tommylin15/janus-intelligence-mart@sha256:'+'2'*64, 'b'*40)
    old = json.loads(json.dumps(desired))
    old['etag'] = 'fence'
    env = old['template']['template']['containers'][0]['env']
    names = {'MART_CEO_GEMINI_ONLY', 'MART_GEMINI_MODEL', 'MART_GEMINI_FREE_TIER_CONFIRMED'}
    old['template']['template']['containers'][0]['env'] = [e for e in env if e['name'] not in names]
    old['template']['template']['containers'][0]['env'].insert(2, {'name': 'MART_CODEX_AUTH_SECRET', 'value': 'janus-mart-codex-auth'})
    assert update_payload(old, desired)['etag'] == 'fence'
    old['template']['template']['containers'][0]['env'][2]['value'] = 'different-secret'
    with pytest.raises(AssertionError):
        update_payload(old, desired)


def test_worker_fence_checks_later_execution_pages(monkeypatch):
    sys.path.insert(0, str(path.parent))
    import ceo_worker_deploy
    responses = iter([{'executions': [], 'nextPageToken': 'next'},
                      {'executions': [{'runningCount': 1}]}])
    monkeypatch.setattr(ceo_worker_deploy, 'cloud', lambda _: next(responses))
    with pytest.raises(AssertionError, match='not terminal'):
        ceo_worker_deploy.execution_fence()


def test_worker_update_does_not_poll_nonpersistent_validation_operation(monkeypatch, tmp_path):
    sys.path.insert(0, str(path.parent))
    import ceo_worker_deploy as deploy
    import subprocess
    old_image = 'ghcr.io/tommylin15/janus-intelligence-mart@sha256:'+'1'*64
    new_image = 'ghcr.io/tommylin15/janus-intelligence-mart@sha256:'+'2'*64
    old = worker.template(source(), old_image, 'a'*40)
    old.update(etag='fence', terminalCondition={'state': 'CONDITION_SUCCEEDED'})
    desired = worker.template(source(), new_image, 'b'*40)
    desired.update(etag='new', terminalCondition={'state': 'CONDITION_SUCCEEDED'})
    current = old
    calls = []
    def cloud(target, body=None, method=None):
        nonlocal current
        calls.append(target)
        if target.endswith('/services/janus-api'): return {'template': {'serviceAccount': deploy.API_IDENTITY}}
        if target.endswith('/executions?pageSize=100'): return {'executions': []}
        if '?validateOnly=true' in target: return {'name': deploy.ROOT+'/operations/validation', 'done': False}
        if target.endswith('/operations/validation'): raise RuntimeError('cloud_control_http_404')
        if target.endswith('/operations/update'): return {'done': True}
        if target.endswith(':getIamPolicy'): return deploy.bind_api({}, deploy.API_IDENTITY)
        if target.endswith(':setIamPolicy'): return body['policy']
        if method == 'PATCH':
            current = desired
            return {'name': deploy.ROOT+'/operations/update'}
        return current
    (tmp_path/'ops').mkdir()
    (tmp_path/'ops/ceo-worker-plan.json').write_text(json.dumps({'approved': True, 'job': worker.JOB}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(deploy, 'cloud', cloud)
    monkeypatch.setattr(deploy, 'job', lambda _: source())
    monkeypatch.setattr(subprocess, 'check_output', lambda *a, **k: json.dumps({'Digest': 'sha256:'+'1'*64, 'Labels': {'org.opencontainers.image.revision': 'a'*40}}))
    monkeypatch.setattr(sys, 'argv', ['deploy', '--image', new_image, '--sha', 'b'*40])
    deploy.main()
    assert deploy.ROOT+'/operations/validation' not in calls
    assert current['labels']['janus-git-sha'] == 'b'*40
