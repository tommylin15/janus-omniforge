"""Offline P0-2 Controller-only immutable rollout guard tests."""
from __future__ import annotations
from pathlib import Path
import ast,sys,pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts/gcp"))
import p02_controller_rollout as r

def request():
    return dict(intent="p02-controller-only-lease-fix",approved=True,
                source_sha=r.SOURCE,release_run=int(r.RELEASE_RUN),
                job=r.JOB,no_analysis_replay=True,no_collection_replay=True,
                no_data_mutation=True,no_iam_expansion=True,
                no_api_traffic_change=True)

def test_exact_request_and_no_replay_contract():
    r.guard(request())
    for key in request():
        invalid=request()
        invalid[key]=None
        with pytest.raises(ValueError,match="rollout_request_invalid"):
            r.guard(invalid)
    assert r.JOB=="janus-batch-controller"
    assert r.SOURCE=="ba4fc98ca4a11e3c9092bd2b636ca105c9e8beb7"

def test_single_job_lease_fence_canary_and_rollback():
    s=(ROOT/"scripts/gcp/p02_controller_rollout.py").read_text()
    ast.parse(s)
    for x in (
        'gcp.command(gcp.LEASE+["acquire"])',
        'gcp.command(gcp.LEASE+["release","--safe-to-release"])',
        'gcp.writers()',
        'gcp.wait_for_terminal_executions()',
        'gcp.set_scheduler("pause","PAUSED")',
        'gcp.set_scheduler("resume","ENABLED")',
        'gcp.update(JOB,target,original_hash)',
        'gcp.update(JOB,old,original_hash)',
        'gcp.canary(JOB,target,original_hash,journal,save)',
        'gcp.checked_image(JOB,target,original_hash)',
        '"queue_recovery_dispatches":0',
        '"data_mutations":0',
        'source_sha',
    ):
        assert x in s, x
    for prohibited in ("control.executions SET", "QUEUE_EXECUTION_ID",
                       "JANUS_P02_ANALYSIS_RECOVERY", "gcp.update(\"janus-api\"",
                       ".delete(", "DROP TABLE","ALTER ROLE"):
        assert prohibited not in s
