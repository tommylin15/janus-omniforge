import importlib.util
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path('scripts/gcp').resolve()))
spec=importlib.util.spec_from_file_location('finops_reference_runtime',Path('scripts/gcp/finops_reference_runtime.py'))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_override_replaces_worker_args_without_changing_image_env_or_template():
    job={'template':{'template':{'containers':[{'name':'worker','command':['python'],'image':'fixed','env':[{'name':'secret','valueSource':{}}]}]}}}
    assert m.override(job,'pass')=={'name':'worker','args':['-c','pass'],'env':[]}
    assert job['template']['template']['containers'][0]['image']=='fixed'
    job['template']['template']['containers'][0]['command']=['unexpected']
    with pytest.raises(ValueError,match='entrypoint'): m.override(job,'pass')


def test_receipt_rejects_non_core_references_or_write_claims():
    receipt={'source':'active_control_executions','data_writes':0,'core_snapshot_ids':['sha256:'+'a'*64]}
    assert m.checked_result(receipt)==receipt
    with pytest.raises(ValueError): m.checked_result({**receipt,'data_writes':1})
    with pytest.raises(ValueError): m.checked_result({**receipt,'core_snapshot_ids':['private-row']})
    with pytest.raises(ValueError): m.checked_result({**receipt,'source':'unknown'})


def test_runtime_queries_are_read_only_and_bound_all_rows():
    for code in m.CODES.values():
        compile(code,'<runtime>','exec')
        assert 'SET TRANSACTION READ ONLY' in code
        assert 'LIMIT 1000' in code
        assert not any(word in code.upper() for word in ('INSERT ','UPDATE ','DELETE ','CREATE ','GRANT '))
    assert 'has_column_privilege' in m.MART_CODE


def test_mutable_image_rejected_before_execution_fence(monkeypatch,tmp_path):
    import json
    request=tmp_path/'request.json'
    request.write_text(json.dumps({'intent':'read-only-d06-runtime-references','no_data_mutation':True,
        'jobs':{name:{'image':'ghcr.io/tommylin15/'+name+':latest','configuration_hash':'a'*64} for name in m.CODES}}))
    monkeypatch.setattr(m,'REQUEST',request)
    monkeypatch.setattr(m.r,'fence',lambda:pytest.fail('invalid baseline must not touch runtime'))
    with pytest.raises(ValueError,match='immutable_reference_baseline_required'): m.main()


def test_daily_batch_estimate_uses_event_volume_not_75_percent_assumption():
    result=m.batch_forecast([{'day_start_utc':'day','events':225} for _ in range(4)])
    assert result['four_window_nonempty_batches']==8
    assert result['daily_nonempty_batches']==5
    assert result['estimated_table_scans_avoided']==6
    assert result['estimated_batch_reduction_percent']==37.5
    assert result['matched_runtime_io_verified'] is False
    assert m.batch_forecast([])['estimated_batch_reduction_percent'] is None
    with pytest.raises(ValueError):m.batch_forecast([{'day_start_utc':'day','events':-1}])


def test_failed_rollout_blocks_probe_before_dispatch(monkeypatch,tmp_path):
    import json
    request=tmp_path/'request.json'
    request.write_text(json.dumps({'intent':'read-only-d06-runtime-references','no_data_mutation':True,
        'expected_rollout_run':'123','jobs':{name:{'image':'ghcr.io/tommylin15/'+name+'@sha256:'+'a'*64,'configuration_hash':'b'*64} for name in m.CODES}}))
    monkeypatch.setattr(m,'REQUEST',request)
    monkeypatch.setattr(m.r,'command',lambda args:json.dumps({'status':'completed','conclusion':'failure','workflowName':'Janus GHCR controlled Jobs rollout'}))
    monkeypatch.setattr(m.r,'fence',lambda:pytest.fail('failed rollout must not dispatch'))
    with pytest.raises(ValueError,match='reference_rollout_not_successful'):m.main()
