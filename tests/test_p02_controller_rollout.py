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
    assert r.SOURCE=="166f4d7086d9ffbaa578792e5746b89dc1d334f4"
    assert r.IMAGE_SOURCE_SHA=="6891656ac52e0ddc6e541229b73d88217c615ebb"

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

def test_controller_rollout_github_lease_permission():
    """Git ref lease acquire needs write; no broader GCP privileges are added."""
    workflow=(ROOT/".github/workflows/p02-controller-rollout-dev.yml").read_text()
    permissions=workflow.split("permissions:",1)[1].split("concurrency:",1)[0]
    assert "contents: write" in permissions  # GitHub tag lease: acquire/release
    assert "actions: read" in permissions
    assert "id-token: write" in permissions
    assert "packages: write" not in permissions


def test_five_day_queue_contract_in_built_release_source():
    """Release source has a strict 5-day cutoff and no old replay switch."""
    queues = (ROOT / "jobs/ingestion-core/ingestion_core/admin_batches.py").read_text()
    controller = (ROOT / "jobs/ingestion-core/ingestion_core/batch_controller.py").read_text()
    assert "requested_at >= now() - interval '5 days'" in queues
    assert "historical recovery disabled: five-day queue policy" in queues
    assert "queued_execution_is_fresh" in queues and "queued_execution_is_fresh" in controller
    assert "queue_request_excluded" in controller
    assert "requested_at >= now() - interval '7 days'" not in queues
    assert "requested_at >= now() - interval '30 days'" not in queues
    assert r.RELEASE_RUN == "40049195127"
