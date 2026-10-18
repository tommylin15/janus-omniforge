"""The CI entry must accept only bounded read-only and existing dev operations."""
import importlib.machinery
import json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import pytest

def load_module():
    return importlib.machinery.SourceFileLoader(
        "finops_one_shot", "scripts/gcp/finops-one-shot-maintenance.py").load_module()


@pytest.mark.parametrize('failure', [False, True])
def test_runtime_fence_restores_scheduler_and_releases_only_own_terminal_lease(failure):
    module = load_module()
    trace = []
    state = {'state': 'ENABLED', 'schedule': '30 * * * *'}
    def scheduler_state(action, expected):
        state['state'] = expected
        trace.append(action)
    rollout = SimpleNamespace(
        scheduler=lambda: dict(state), scheduler_fingerprint=lambda value: value['schedule'],
        JOB_COMPONENT=[('core', 'core')], job=lambda _: {'image': 'fixed'},
        image=lambda value: value['image'], fingerprint=lambda _: 'same-config',
        LEASE=['lease'], command=lambda args: trace.append(args[1]),
        writers=lambda: trace.append('assert-owner'), set_scheduler=scheduler_state,
        wait_for_terminal_executions=lambda: trace.append('terminal'),
        checked_image=lambda *args: trace.append('unchanged'))
    try:
        with module.runtime_fence(rollout):
            trace.append('maintenance')
            if failure:
                raise RuntimeError('known terminal worker failure')
    except RuntimeError:
        assert failure
    assert trace == ['acquire', 'assert-owner', 'pause', 'terminal', 'maintenance',
                     'terminal', 'unchanged', 'resume', 'release']
    assert state['state'] == 'ENABLED'


def test_runtime_fence_keeps_lease_and_scheduler_paused_on_unknown_execution():
    module = load_module()
    state, trace = {'state': 'ENABLED'}, []
    def terminal():
        if trace.count('terminal'):
            raise RuntimeError('execution still unknown')
        trace.append('terminal')
    rollout = SimpleNamespace(
        scheduler=lambda: dict(state), scheduler_fingerprint=lambda _: 'same',
        JOB_COMPONENT=[], LEASE=['lease'], command=lambda args: trace.append(args[1]),
        writers=lambda: None, set_scheduler=lambda action, expected: state.update(state=expected),
        wait_for_terminal_executions=terminal)
    with pytest.raises(RuntimeError, match='unknown'):
        with module.runtime_fence(rollout):
            pass
    assert state['state'] == 'PAUSED' and 'release' not in trace

def test_retention_dry_run_requires_exact_image_and_all_page_fence(monkeypatch, tmp_path, capsys):
    from contextlib import nullcontext
    m=load_module()
    monkeypatch.setattr(m, 'runtime_fence', lambda _: nullcontext())
    req={"intent":"one-shot-existing-dev-iceberg-maintenance","no_new_resources":True,
         "mode":"retention-dry-run","rollout_run":38676820532,
         "expected_source_sha":"4"*40,
         "expected_image":"ghcr.io/tommylin15/janus-ingestion-core@sha256:"+"a"*64}
    request=tmp_path/"request.json"
    request.write_text(json.dumps(req))
    monkeypatch.setattr(m,"REQUEST",request)
    def jsoncall(*args):
        if args[:3]==("gh","run","view"):
            return {"status":"completed","conclusion":"success","workflowName":"Janus GHCR controlled Jobs rollout"}
        if args[:3]==("gcloud","scheduler","jobs"):
            return {"state":"ENABLED","schedule":"30 * * * *","timeZone":"Asia/Taipei"}
        if args[:3]==("gcloud","run","jobs") and "describe" in args:
            return {"containers":[{"image":req["expected_image"]}]}
        if args[:4]==("gcloud","run","jobs","executions"):
            return [{"status":{"completionTime":"2026-10-15T00:00:00Z"}}]
        raise AssertionError(args)
    monkeypatch.setattr(m,"jsoncall",jsoncall)
    monkeypatch.setattr(m,"inventory",lambda:{"objects":8135,"bytes":178359928,"under_1mib":8130})
    monkeypatch.setattr(m,"call",lambda *a,**kw:"janus-ingestion-core-test123")
    monkeypatch.setattr(m,"log_evidence",lambda *_:{
        "component":"data-retention","mode":"dry-run",
        "tables":[{"planned_expiration":3}],"orphans":[{"planned_objects":7}],
        "core_manifests":{"status":"reference_fence_required","planned_objects":0}})
    import sys
    sys.path.insert(0,"scripts/gcp")
    import ghcr_jobs_rollout
    visited=[]
    monkeypatch.setattr(ghcr_jobs_rollout,"fence",lambda:visited.append("full_scan"))
    m.main()
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="PASS" and result["operation"]=="retention-dry-run"
    assert result["planned_orphans"]==7 and result["planned_snapshots_to_expire"]==3
    assert visited==["full_scan"]

def test_invalid_mode_fails_before_gcp_calls(monkeypatch,tmp_path):
    m=load_module()
    p=tmp_path/"request.json"
    p.write_text(json.dumps({"intent":"one-shot-existing-dev-iceberg-maintenance",
       "no_new_resources":True,"mode":"retention-delete-all","expected_source_sha":"4"*40}))
    monkeypatch.setattr(m,"REQUEST",p)
    with patch.object(m,"jsoncall") as c:
        try: m.main()
        except RuntimeError as err: assert "invalid one-shot" in str(err)
        else: raise AssertionError("mode should be blocked")
    c.assert_not_called()


def test_unlinked_small_files_requires_separate_explicit_user_approval(monkeypatch,tmp_path):
    import pytest
    m=load_module()
    p=tmp_path/'request.json'
    p.write_text(json.dumps({'intent':'one-shot-existing-dev-iceberg-maintenance','no_new_resources':True,
        'mode':'unlinked-small-files','expected_source_sha':'4'*40}))
    monkeypatch.setattr(m,'REQUEST',p)
    with patch.object(m,'jsoncall') as call:
        with pytest.raises(RuntimeError,match='explicit_unlinked_small_file_approval_required'):m.main()
    call.assert_not_called()


def test_audit_only_mode_requires_exact_audit_receipt(monkeypatch,tmp_path,capsys):
    from contextlib import nullcontext
    m=load_module()
    monkeypatch.setattr(m, 'runtime_fence', lambda _: nullcontext())
    req={"intent":"one-shot-existing-dev-iceberg-maintenance","no_new_resources":True,
         "mode":"audit-cleanup","rollout_run":38676820532,
         "expected_source_sha":"4"*40,
         "expected_image":"ghcr.io/tommylin15/janus-ingestion-core@sha256:"+"a"*64}
    f=tmp_path/"request.json"
    f.write_text(json.dumps(req))
    monkeypatch.setattr(m,"REQUEST",f)
    def jc(*args):
        if args[:3]==("gh","run","view"):
            return {"status":"completed","conclusion":"success","workflowName":"Janus GHCR controlled Jobs rollout"}
        if args[:3]==("gcloud","scheduler","jobs"):
            return {"state":"ENABLED","schedule":"30 * * * *","timeZone":"Asia/Taipei"}
        if args[:3]==("gcloud","run","jobs") and "describe" in args:
            return {"containers":[{"image":req["expected_image"]}]}
        if args[:4]==("gcloud","run","jobs","executions"):
            return [{"status":{"completionTime":"2026-10-15T00:00:00Z"}}]
        raise AssertionError(args)
    monkeypatch.setattr(m,"jsoncall",jc)
    monkeypatch.setattr(m,"inventory",lambda:{"objects":8000,"bytes":10000,"under_1mib":7800})
    monkeypatch.setattr(m,"call",lambda *a,**kw:"janus-ingestion-core-audit123")
    monkeypatch.setattr(m,"log_evidence",lambda *_:{"component":"iceberg-audit-only-cleanup",
                       "mode":"audit-cleanup","status":"PASS","deleted_objects":19,
                       "expired_snapshots":8,"canonical_tables_modified":0})
    import sys
    sys.path.insert(0,"scripts/gcp")
    import ghcr_jobs_rollout
    monkeypatch.setattr(ghcr_jobs_rollout,"fence",lambda:None)
    m.main()
    value=json.loads(capsys.readouterr().out)
    assert value["operation"]=="audit-cleanup" and value["audit_only_deleted_objects"]==19
    assert value["audit_only_expired_snapshots"]==8
    assert value["audit_only_canonical_tables_modified"]==0
