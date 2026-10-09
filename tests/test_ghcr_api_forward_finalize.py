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
