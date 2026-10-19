import importlib.util
import json
from pathlib import Path
import sys

import pytest


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(Path('scripts/gcp').resolve()))
    spec=importlib.util.spec_from_file_location('supplement_ops',Path('scripts/gcp/stock_supplement_ops.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unapproved_request_is_rejected_before_cloud_or_dispatch(tmp_path,monkeypatch):
    module=load(monkeypatch)
    monkeypatch.chdir(tmp_path)
    Path('ops').mkdir()
    Path('ops/stock-supplement-request.json').write_text(json.dumps({'approved':False}))
    monkeypatch.setattr(module,'cloud',lambda *_args,**_kwargs:pytest.fail('unapproved cloud call'))
    with pytest.raises(ValueError,match='invalid_stock_supplement_request'):
        module.run('run')


def test_migration_and_readback_probes_compile_without_owner_payloads(monkeypatch):
    module=load(monkeypatch)
    compile(module.MIGRATION_PROBE,'migration','exec')
    compile(module.READBACK_PROBE,'readback','exec')
    assert 'INSERT INTO private.' not in module.MIGRATION_PROBE
    assert 'user_id' not in module.READBACK_PROBE and 'shares' not in module.READBACK_PROBE


def test_baseline_uses_live_job_inventory_including_retirement_fence(monkeypatch):
    module=load(monkeypatch)
    monkeypatch.setattr(module,'existing_jobs',lambda:{'janus-ingestion-core':{'test':True}})
    monkeypatch.setattr(module,'cloud',lambda *_args,**_kwargs:{'executions':[]})
    monkeypatch.setattr(module,'image',lambda _job:'pinned')
    monkeypatch.setattr(module,'fingerprint',lambda _job:'hash')
    saved=[]
    monkeypatch.setattr(module,'save',saved.append)
    module.baseline()
    assert list(saved[0]['jobs'])==['janus-ingestion-core']
    assert saved[0]['active_executions']=={'janus-ingestion-core':[]}
