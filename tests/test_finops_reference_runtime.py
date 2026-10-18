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


def test_disabled_mirror_estimate_uses_previous_event_volume_not_total_gcs_io():
    result=m.batch_forecast([{'day_start_utc':'day','events':225} for _ in range(4)])
    assert result['four_window_nonempty_batches']==8
    assert result['disabled_mirror_batches']==0
    assert result['estimated_table_scans_avoided']==16
    assert result['estimated_batch_reduction_percent']==100
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

def test_snapshot_plan_excludes_current_files_recent_files_and_other_objects():
    from datetime import datetime, timezone
    spec=importlib.util.spec_from_file_location('snapshot_plan',Path('scripts/gcp/finops_snapshot_plan.py'))
    plan=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)
    now=datetime(2026,10,18,tzinfo=timezone.utc)
    def item(name,updated='2026-10-01T00:00:00Z'):
        return {'name':name,'updated':updated,'size':'100'}
    objects=[item('current.parquet'),item('old.avro'),item('recent.parquet','2026-10-17T00:00:00Z'),item('other.json'),item('edge.parquet','2026-10-11T00:00:00Z')]
    assert [x['name'] for x in plan.candidates(objects,{'gs://bucket/current.parquet'},'bucket',now)]==['old.avro']
    import ast
    tree=ast.parse(Path('scripts/gcp/finops_snapshot_plan.py').read_text())
    assert not any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {'delete','create','overwrite','commit','expire_snapshots'} for node in ast.walk(tree))
