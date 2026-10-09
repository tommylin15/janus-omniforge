import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_api_forward_finalize as finalize


def test_requires_specific_original_failed_owner():
    meta = {"headSha": finalize.ORIGINAL_HEAD, "status": "completed",
            "conclusion": "failure",
            "workflowName": "Janus GHCR controlled forward-only API promotion"}
    with patch.object(finalize, "command", side_effect=[
            json.dumps(meta), '{"status":"OWNED"}']) as cmd:
        got = finalize.assert_original_lease()
    assert "--run-id" in got and finalize.ORIGINAL_RUN in got
    assert "--sha" in got and finalize.ORIGINAL_HEAD in got
    assert cmd.call_count == 2


def test_running_or_wrong_owner_never_steals_lease():
    metadata = {"headSha": finalize.ORIGINAL_HEAD, "status":"in_progress",
                "conclusion":None,
                "workflowName":"Janus GHCR controlled forward-only API promotion"}
    with patch.object(finalize, "command", return_value=json.dumps(metadata)) as cmd:
        with pytest.raises(ValueError, match="original_promotion_owner_unverified"):
            finalize.assert_original_lease()
    cmd.assert_called_once()


def test_fail_closed_without_live_health_does_not_release_lease(tmp_path):
    receipt=tmp_path/"receipt.json"
    with (patch.object(finalize, "request"),
          patch.object(finalize, "assert_original_lease", return_value=["lease"]),
          patch.object(finalize, "verify_current", side_effect=ValueError("active_health_failed")),
          patch.object(finalize, "command") as cmd):
        assert finalize.run(receipt)==78
    assert json.loads(receipt.read_text())["lease_released"] is False
    cmd.assert_not_called()


def test_healthy_live_candidate_releases_only_original_lease(tmp_path):
    receipt=tmp_path/"receipt.json"
    with (patch.object(finalize, "request"),
          patch.object(finalize, "assert_original_lease", return_value=["original-owner"]),
          patch.object(finalize, "verify_current"),
          patch.object(finalize, "command") as cmd):
        assert finalize.run(receipt)==0
    cmd.assert_called_once_with(["original-owner", "release", "--safe-to-release"])
    e=json.loads(receipt.read_text())
    assert e["lease_released"] is True
    assert e["api_traffic_write"] is False
    assert e["old_ar_revision_rollback_verified"] is False
    assert e["phase"]=="FORWARD_ONLY_PASS_OLD_REVISION_ROLLBACK_UNVERIFIED"


def test_finalize_workflow_single_request_gated_not_retrying_traffic():
    yml=(ROOT/".github/workflows/ghcr-api-forward-finalize-dev.yml").read_text()
    assert "ops/ghcr-api-forward-finalize-request.json" in yml
    assert "workflow_dispatch:" not in yml
    assert "janus-dev-runtime-writers" in yml
    assert "ghcr_api_forward_finalize.py" in yml
    assert "ghcr-jobs-forward-recovery" in yml


def test_bounded_wait_succeeds_after_running_scheduled_execution_finishes():
    with (patch.object(finalize.jobs, "fence", side_effect=[
            ValueError("execution_not_terminal"), None]) as fence,
          patch.object(finalize.time, "sleep") as sleep):
        finalize.wait_for_terminal_executions(timeout_seconds=60, poll_seconds=1)
    assert fence.call_count == 2
    sleep.assert_called_once_with(1)


def test_bounded_wait_never_cancels_or_retries_running_job():
    with (patch.object(finalize.jobs, "fence",
                       side_effect=ValueError("execution_not_terminal")) as fence,
          patch.object(finalize.time, "sleep") as sleep,
          patch.object(finalize.time, "monotonic", side_effect=[0, 1]) as clock):
        with pytest.raises(ValueError, match="execution_still_active_after_bounded_wait"):
            finalize.wait_for_terminal_executions(timeout_seconds=0, poll_seconds=1)
    fence.assert_called_once()
    sleep.assert_not_called()


def test_bounded_wait_does_not_hide_other_errors():
    with patch.object(finalize.jobs, "fence", side_effect=RuntimeError("cloud_control_http_403")):
        with pytest.raises(RuntimeError, match="cloud_control_http_403"):
            finalize.wait_for_terminal_executions()

def test_live_readback_accepts_reconciled_latest_ready_without_service_condition():
    service = {"metadata": {"generation": "28"}, "status": {
        "observedGeneration": 28, "latestReadyRevisionName": finalize.CANDIDATE}}
    revision = {"status": {"conditions": [{"type": "Ready", "status": "True"}]}}
    finalize.assert_ready_readback(service, revision)


@pytest.mark.parametrize("edit,reason", [
    (lambda s, r: s["status"].update(observedGeneration=27),
     "live_api_generation_unreconciled"),
    (lambda s, r: s["status"].update(latestReadyRevisionName="janus-api-old"),
     "live_api_latest_ready_revision_mismatch"),
    (lambda s, r: s["status"].update(conditions=[{"type": "Ready", "status": "False"}]),
     "live_api_not_ready"),
    (lambda s, r: s["status"].update(conditions=[{"type": "Ready", "status": "Unknown"}]),
     "live_api_not_ready"),
    (lambda s, r: r["status"].update(conditions=[{"type": "Ready", "status": "False"}]),
     "live_api_revision_not_ready"),
    (lambda s, r: s["metadata"].pop("generation"),
     "live_api_generation_unreconciled"),
    (lambda s, r: s["status"].update(conditions="not-a-list"),
     "live_api_conditions_shape_unknown"),
])
def test_live_readback_fails_closed_on_stale_or_explicit_unready(edit, reason):
    service = {"metadata": {"generation": "28"}, "status": {
        "observedGeneration": 28, "latestReadyRevisionName": finalize.CANDIDATE}}
    revision = {"status": {"conditions": [{"type": "Ready", "status": "True"}]}}
    edit(service, revision)
    with pytest.raises(ValueError, match=reason):
        finalize.assert_ready_readback(service, revision)


def test_live_readback_accepts_explicit_service_ready():
    service = {"metadata": {"generation": 28}, "status": {
        "observedGeneration": "28", "latestReadyRevisionName": finalize.CANDIDATE,
        "conditions": [{"type": "Ready", "status": "True"}]}}
    revision = {"status": {"conditions": [{"type": "Ready", "status": "True"}]}}
    finalize.assert_ready_readback(service, revision)


def test_bounded_readiness_evidence_never_exposes_messages_or_service_config():
    service = {"metadata": {"generation": "12", "secret": "should-not-appear"},
               "status": {"observedGeneration": 12,
                          "latestReadyRevisionName": finalize.CANDIDATE,
                          "conditions": [{"type": "Ready", "status": "False",
                                          "reason": "RouteNotReady",
                                          "message": "secret-personal-payload"}]}}
    revision = {"status": {"conditions": [{"type": "Ready", "status": "True"}]}}
    got = finalize.bounded_readiness_evidence(service, revision)
    assert got["service_generation_reconciled"] is True
    assert got["latest_ready_is_candidate"] is True
    assert got["service_conditions"][0] == {
        "type": "Ready", "status": "False", "reason": "RouteNotReady"}
    assert "secret" not in json.dumps(got)
    assert "message" not in json.dumps(got)

