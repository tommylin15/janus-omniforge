from unittest.mock import patch

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_jobs_readonly_preflight as preflight


def test_no_mutations_and_all_live_gates_present():
    with patch.object(preflight.rollout, "legacy_writers") as writer, \
         patch.object(preflight.rollout, "scheduler", return_value={"state": "ENABLED"}), \
         patch.object(preflight.rollout, "job") as job, \
         patch.object(preflight.rollout, "fence") as fence, \
         patch.object(preflight.rollout, "job_update_permissions") as iam, \
         patch.object(preflight.rollout, "set_scheduler") as set_sched, \
         patch.object(preflight.rollout, "update") as update:
        evidence = preflight.scan()
    assert evidence["status"] == "READONLY_PREFLIGHT_PASS"
    assert evidence["gcp_writes"] == 0
    assert all(v["status"] == "PASS" for v in evidence["gates"].values())
    assert job.call_count == len(preflight.rollout.REQUIRED_JOBS)
    writer.assert_called_once()
    fence.assert_called_once()
    iam.assert_called_once()
    set_sched.assert_not_called()
    update.assert_not_called()


def test_unknown_cloud_run_or_iam_is_blocked_not_misreported_pass():
    with patch.object(preflight.rollout, "legacy_writers", side_effect=RuntimeError("token-secret")), \
         patch.object(preflight.rollout, "scheduler", return_value={"state": "ENABLED"}), \
         patch.object(preflight.rollout, "job"), \
         patch.object(preflight.rollout, "fence"), \
         patch.object(preflight.rollout, "job_update_permissions", side_effect=ValueError("missing")):
        evidence = preflight.scan()
    assert evidence["status"] == "BLOCKED"
    assert evidence["gates"]["legacy_cloud_build_not_competing"]["status"] == "BLOCKED"
    assert evidence["gates"]["jobs_update_and_canary_iam"]["status"] == "BLOCKED"
    assert "token-secret" not in str(evidence)
    assert "missing" not in str(evidence)


def test_unexpected_scheduler_state_blocks_readonly_preflight():
    with patch.object(preflight.rollout, "legacy_writers"), \
         patch.object(preflight.rollout, "scheduler", return_value={"state": "PAUSED"}), \
         patch.object(preflight.rollout, "job"), \
         patch.object(preflight.rollout, "fence"), \
         patch.object(preflight.rollout, "job_update_permissions"):
        evidence = preflight.scan()
    assert evidence["status"] == "BLOCKED"
    assert evidence["gates"]["scheduler_expected_enabled_baseline"]["status"] == "BLOCKED"


def test_workflow_is_explicit_preflight_and_has_no_mutating_release_step():
    source = (ROOT / ".github/workflows/ghcr-jobs-readonly-preflight.yml").read_text()
    assert "workflow_dispatch:" in source
    assert "'ops/ghcr-jobs-preflight-request.json'" in source
    assert "ghcr_jobs_readonly_preflight.py" in source
    assert "ghcr_jobs_rollout.py --release-run" not in source
    assert "id-token: write" in source
