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


@pytest.mark.parametrize('collateral_change', [False, True])
def test_weekly_toggle_accepts_only_the_flag_and_keeps_exact_image(monkeypatch, capsys, collateral_change):
    from copy import deepcopy
    import sys
    sys.path.insert(0, 'scripts/gcp')
    import ghcr_jobs_rollout as rollout
    module = load_module()
    image = 'ghcr.io/tommylin15/janus-ingestion-core@sha256:'+'a'*64
    state = {'template': {'template': {'containers': [{'image':image,
             'env':[{'name':'KEEP','value':'original'}]}]}}}
    snapshots = {'janus-batch-controller': (image, rollout.fingerprint(state))}
    original = deepcopy(snapshots)
    monkeypatch.setattr(rollout, 'job', lambda _: deepcopy(state))
    def update(*args, **kwargs):
        env = state['template']['template']['containers'][0]['env']
        env.append({'name':'FINOPS_WEEKLY_MAINTENANCE','value':'true'})
        if collateral_change:
            env[0]['value'] = 'changed'
        return ''
    monkeypatch.setattr(module, 'call', update)
    request = {'mode':'enable-weekly','expected_image':image}
    if collateral_change:
        with pytest.raises(RuntimeError, match='other_configuration'):
            module.execute_maintenance(request, None, rollout, snapshots)
        assert snapshots == original
    else:
        module.execute_maintenance(request, None, rollout, snapshots)
        assert snapshots['janus-batch-controller'] == (image, rollout.fingerprint(state))
        assert json.loads(capsys.readouterr().out)['weekly_maintenance'] is True


def test_mart_cleanup_requires_exact_image_and_current_only_receipt(monkeypatch, capsys):
    module = load_module()
    image = 'ghcr.io/tommylin15/janus-intelligence-mart@sha256:'+'a'*64
    calls = []
    rollout = SimpleNamespace(checked_image=lambda *args: {'image':image}, image=lambda value:value['image'])
    monkeypatch.setattr(module, 'call', lambda *args, **kwargs: calls.append(args) or 'janus-intelligence-mart-cleanup')
    monkeypatch.setattr(module, 'log_evidence', lambda *args, **kwargs: {'mode':'apply','policy_version':'current-only-snapshots-v1'})
    request = {'mode':'mart-retention','expected_mart_image':image,'expected_source_sha':'a'*40}
    snapshots = {'janus-intelligence-mart': (image, 'config')}
    module.execute_maintenance(request, None, rollout, snapshots)
    assert json.loads(capsys.readouterr().out)['operation'] == 'mart-retention'
    assert calls[0][:5] == ('gcloud','run','jobs','execute','janus-intelligence-mart')
    monkeypatch.setattr(module, 'log_evidence', lambda *args, **kwargs: {'mode':'apply','policy_version':'old-policy'})
    with pytest.raises(RuntimeError, match='policy_readback'):
        module.execute_maintenance(request, None, rollout, snapshots)

def test_retention_dry_run_uses_lease_owned_terminal_fence_not_legacy_cli_status(monkeypatch, tmp_path, capsys):
    from contextlib import contextmanager
    m=load_module()
    visited=[]
    @contextmanager
    def guarded(rollout):
        visited.append("lease-owned-pause-and-wait-all-pages")
        yield {}
    monkeypatch.setattr(m, 'runtime_fence', guarded)
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
    # The old latest-100 gcloud "status.completionTime" precheck is removed:
    # v2 terminal executions need not include that legacy CLI key.
    monkeypatch.setattr(ghcr_jobs_rollout, "fence", lambda: (_ for _ in ()).throw(
        AssertionError("never bypass the lease-owned pause+wait for terminality")))
    m.main()
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="PASS" and result["operation"]=="retention-dry-run"
    assert result["planned_orphans"]==7 and result["planned_snapshots_to_expire"]==3
    assert visited==["lease-owned-pause-and-wait-all-pages"]

def test_stage_only_one_shot_produces_exact_live_receipt_without_core_inventory(monkeypatch, capsys):
    module = load_module()
    image = "ghcr.io/tommylin15/janus-ingestion-core@sha256:" + "a" * 64
    snapshots = {"janus-ingestion-core": (image, "hash")}
    rollout = SimpleNamespace(checked_image=lambda *args: {"image": image},
                              image=lambda data: data["image"])
    monkeypatch.setattr(module, "inventory", lambda: (_ for _ in ()).throw(
        AssertionError("Core inventory must not run for Stage-only cleanup")))
    calls = []
    monkeypatch.setattr(module, "call", lambda *args, **kwargs: calls.append(args)
                        or "janus-ingestion-core-test123")
    receipt = {
        "component": "stage-only-retention", "status": "PASS", "mode": "apply",
        "scope": "stage-only", "policy": {"stage_days": 2, "quarantine_days": 2},
        "core_deleted": 0, "mart_deleted": 0, "private_deleted": 0,
        "generation_readback": "PASS", "stage": {"planned_objects": 10,
        "planned_bytes": 150, "deleted_objects": 10, "deleted_bytes": 150},
        "before": {"objects": 12, "bytes": 175}, "after": {"objects": 2, "bytes": 25}
    }
    monkeypatch.setattr(module, "log_evidence", lambda *args: receipt)
    request = {
        "mode": "stage-only-apply", "approved_stage_retention_hours": 48,
        "approved_stage_bucket": "gen-lang-client-0593591102-dev-stage",
        "approved_stage_apply": True, "expected_image": image,
        "expected_source_sha": "e" * 40
    }
    module.execute_maintenance(request, None, rollout, snapshots)
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "PASS" and output["evidence"]["stage"]["deleted_objects"] == 10
    assert "ICEBERG_MAINTENANCE_MODE=stage-only-apply" in str(calls)
    receipt["generation_readback"] = "NOT_VERIFIED"
    with pytest.raises(RuntimeError, match="generation_readback_failed"):
        module.execute_maintenance(request, None, rollout, snapshots)
    request.pop("approved_stage_apply")
    with pytest.raises(RuntimeError, match="scope_and_apply_approval_required"):
        module.execute_maintenance(request, None, rollout, snapshots)



def test_runtime_fence_waits_on_actual_cloud_run_terminal_gate_and_restores_after_completion():
    """A running execution is never ignored: Scheduler is paused before bounded wait."""
    m = load_module()
    state, trace = {'state':'ENABLED', 'schedule':'30 * * * *'}, []
    attempts = [False, True]
    def wait():
        assert state['state'] == 'PAUSED'
        trace.append("all-page-wait")
        if not attempts.pop(0):
            # Simulate the wait helper safely polling until active canary finishes.
            trace.append("saw-active-v2-execution")
    def set_scheduler(action, expected):
        trace.append(action)
        state['state'] = expected
    rollout = SimpleNamespace(
        scheduler=lambda: dict(state), scheduler_fingerprint=lambda x: x['schedule'],
        JOB_COMPONENT=[('janus-ingestion-core', 'ingestion-core')],
        job=lambda name: {'image':'sha256:digest'},
        image=lambda job:job['image'],fingerprint=lambda job:'same-hash',
        LEASE=['lease'], command=lambda args: trace.append(args[1]),
        writers=lambda:trace.append("check-owner"),
        set_scheduler=set_scheduler,wait_for_terminal_executions=wait,
        checked_image=lambda *a:trace.append("exact-image-config-check"))
    with m.runtime_fence(rollout):
        trace.append("safe-maintenance")
    assert trace == ['acquire','check-owner','pause','all-page-wait',
                     'saw-active-v2-execution','safe-maintenance','all-page-wait',
                     'exact-image-config-check','resume','release']
    assert state['state'] == 'ENABLED'

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
    monkeypatch.setattr(ghcr_jobs_rollout,"fence",lambda: (_ for _ in ()).throw(
        AssertionError("pre-lease terminal check forbidden")))
    m.main()
    value=json.loads(capsys.readouterr().out)
    assert value["operation"]=="audit-cleanup" and value["audit_only_deleted_objects"]==19
    assert value["audit_only_expired_snapshots"]==8
    assert value["audit_only_canonical_tables_modified"]==0


def test_stage_aged_purge_requires_explicit_age_bucket_and_apply_approval(monkeypatch):
    m = load_module()
    image = 'ghcr.io/tommylin15/janus-ingestion-core@sha256:' + 'b'*64
    snapshots = {'janus-ingestion-core': (image, 'fingerprint')}
    rollout = SimpleNamespace(
        checked_image=lambda *args: {'image': image},
        image=lambda job: job['image'])
    called = []
    monkeypatch.setattr(m, 'call', lambda *args, **kwargs: called.append(args) or '')
    request = {'mode': 'stage-aged-purge-apply', 'expected_image': image}
    with pytest.raises(RuntimeError, match='explicit_scope_approval_required'):
        m.execute_maintenance(request, {'containers': [{'image': image}]}, rollout, snapshots)
    request.update(approved_stage_bucket='gen-lang-client-0593591102-dev-stage',
                   approved_stage_purge_older_days=7,
                   user_approved_aged_stage_purge=True)
    with pytest.raises(RuntimeError, match='explicit_scope_approval_required'):
        m.execute_maintenance(request, {'containers': [{'image': image}]}, rollout, snapshots)
    assert not called


@pytest.mark.parametrize('operation,worker_mode', [
    ('stage-aged-purge-dry-run', 'dry-run'), ('stage-aged-purge-apply', 'apply')])
def test_stage_aged_purge_fenced_worker_receipt(monkeypatch, capsys, operation, worker_mode):
    m = load_module()
    image = 'ghcr.io/tommylin15/janus-ingestion-core@sha256:' + 'b'*64
    snapshots = {'janus-ingestion-core': (image, 'fingerprint')}
    rollout = SimpleNamespace(
        checked_image=lambda *args: {'image': image},
        image=lambda job: job['image'])
    calls = []
    monkeypatch.setattr(m, 'call', lambda *args, **kwargs:
                        calls.append(args) or 'janus-ingestion-core-exec7')
    evidence = {'component': 'stage-aged-stale-execution-purge',
                'status': 'PASS', 'mode': worker_mode,
                'planned_objects': 4, 'planned_bytes': 120,
                'deleted_objects': 4 if worker_mode == 'apply' else 0,
                'deleted_bytes': 120 if worker_mode == 'apply' else 0,
                'before': {'objects': 7, 'bytes': 160},
                'after': {'objects': 3 if worker_mode == 'apply' else 7,
                          'bytes': 40 if worker_mode == 'apply' else 160},
                'generation_readback': 'PASS' if worker_mode == 'apply' else 'NOT_APPLICABLE',
                'core_deleted': 0, 'mart_deleted': 0, 'private_deleted': 0}
    monkeypatch.setattr(m, 'log_evidence', lambda *args: evidence)
    request = {'mode': operation, 'expected_image': image,
               'expected_source_sha': 'b'*40,
               'approved_stage_bucket': 'gen-lang-client-0593591102-dev-stage',
               'approved_stage_purge_older_days': 7,
               'user_approved_aged_stage_purge': True,
               'approved_stage_purge_apply': True}
    m.execute_maintenance(request, {'containers': [{'image': image}]}, rollout, snapshots)
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'PASS' and result['operation'] == operation
    assert len(calls) == 1 and 'JANUS_STAGE_AGED_PURGE_MODE=' + worker_mode in str(calls)
    evidence['generation_readback'] = 'FAILED'
    if worker_mode == 'apply':
        with pytest.raises(RuntimeError, match='generation_readback_failed'):
            m.execute_maintenance(request, {'containers': [{'image': image}]}, rollout, snapshots)



def test_stage_dedupe_canary_fenced_receipt(monkeypatch, capsys):
    module = load_module()
    image = "ghcr.io/tommylin15/janus-ingestion-core@sha256:" + "e" * 64
    snapshots = {"janus-ingestion-core": (image, "fingerprint")}
    rollout = SimpleNamespace(
        checked_image=lambda *args: {"image": image},
        image=lambda job: job["image"])
    request = {"mode": "stage-dedupe-canary", "expected_image": image,
               "approved_stage_bucket": "gen-lang-client-0593591102-dev-stage",
               "user_approved_stage_dedupe_canary": True,
               "stage_canary_no_core_mutation": True}
    calls = []
    monkeypatch.setattr(module, "call", lambda *args, **kwargs:
                        calls.append(args) or "janus-ingestion-core-dedupe8")
    evidence = {
        "component": "stage-shared-raw-live-canary", "status": "PASS",
        "proof": {"raw_created_once": True, "second_execution_reused": True,
                  "distinct_provenance_manifests": True,
                  "raw_payload_verified": True, "created_objects": 4},
        "generation_cleanup": "PASS", "deleted_canary_objects": 4,
        "leftover_canary_objects": 0, "core_deleted": 0,
        "mart_deleted": 0, "private_deleted": 0,
    }
    monkeypatch.setattr(module, "log_evidence", lambda *args: evidence)
    module.execute_maintenance(request, {"containers": [{"image": image}]}, rollout, snapshots)
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
    assert len(calls) == 1 and "JANUS_STAGE_DEDUPE_CANARY_APPROVED=true" in str(calls)
    evidence["leftover_canary_objects"] = 1
    with pytest.raises(RuntimeError, match="runtime_receipt_failed"):
        module.execute_maintenance(request, {"containers": [{"image": image}]}, rollout, snapshots)
    request.pop("user_approved_stage_dedupe_canary")
    with pytest.raises(RuntimeError, match="explicit_scope_required"):
        module.execute_maintenance(request, {"containers": [{"image": image}]}, rollout, snapshots)
