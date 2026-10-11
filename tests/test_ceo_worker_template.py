import importlib.util
from pathlib import Path

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
