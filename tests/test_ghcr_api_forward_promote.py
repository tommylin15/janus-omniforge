"""Bounded GHCR API promotion from a successful forward-only Jobs recovery."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_api_promote as promoter


SHA = "a" * 40


def proof():
    names = [name for name, _ in promoter.JOB_COMPONENT]
    return {
        "source_sha": SHA,
        "mode": "user_authorized_forward_only_owner_recovery",
        "phase": "FORWARD_ONLY_PASS_WITH_PRIVATE_CONFIG_UNVERIFIED",
        "old_ar_image_rollback_exercised": False,
        "original_private_full_config_verified": False,
        "scheduler_resumed": True,
        "job_images": {name: "GHCR" for name in names},
        "canaries": [
            {"job": name, "result": "PASS", "execution": f"{name}-{n}"}
            for name in names for n in range(2)],
    }


def test_valid_8_canary_recovery_accepted_without_claiming_private_config_parity():
    promoter.check_jobs_receipt(proof(), SHA)


@pytest.mark.parametrize("edit", [
    lambda p: p.update(scheduler_resumed=False),
    lambda p: p.update(mode="unknown"),
    lambda p: p.update(phase="PASS"),
    lambda p: p.update(original_private_full_config_verified=True),
    lambda p: p.update(old_ar_image_rollback_exercised=True),
    lambda p: p["job_images"].pop("janus-private-pipeline"),
    lambda p: p["canaries"].pop(),
    lambda p: p["canaries"][1].update(execution=p["canaries"][0]["execution"]),
    lambda p: p["canaries"][0].update(result="FAILED"),
])
def test_incomplete_or_misrepresented_forward_evidence_never_passes(edit):
    obj = proof()
    edit(obj)
    with pytest.raises(ValueError):
        promoter.check_jobs_receipt(obj, SHA)


def request():
    return {
        "intent": "promote-existing-dev-ghcr-api-after-forward-jobs",
        "approved": True,
        "scope": "existing-dev-janus-api-only",
        "source_sha": SHA,
        "release_run": "37876247130",
        "jobs_run": "37915584159",
        "private_config_parity": "NOT_VERIFIED",
        "job_images": {
            n: "ghcr.io/tommylin15/janus-" + c + "@sha256:" + "a" * 64
            for n, c in promoter.JOB_COMPONENT},
        "research_image": (
            "us-central1-docker.pkg.dev/gen-lang-client-0593591102/"
            "janusai-poc/research-cloud-cohort-500@sha256:"
            "7320443730ff487315211710612216e044cd453388622fc852d3cdd081201f59"),
    }


def test_forward_request_requires_bounded_pins_and_explicit_unknown_parity():
    data = request()
    with patch.object(Path, "read_text", return_value=json.dumps(data)):
        assert promoter.check_forward_promotion_request(
            "37876247130", "37915584159", SHA) == data
    for bad in ({"approved": False}, {"scope": "all-services"},
                {"private_config_parity": "PASS"}, {"jobs_run": "another"}):
        altered = {**data, **bad}
        with patch.object(Path, "read_text", return_value=json.dumps(altered)):
            with pytest.raises(ValueError):
                promoter.check_forward_promotion_request(
                    "37876247130", "37915584159", SHA)


def test_post_rollout_runtime_fences_scheduler_and_images():
    data=request()
    images = data["job_images"]
    def job_for(name):
        if name=="janus-research-big-move-500":
            ref=data["research_image"]
        else:
            ref=images[name]
        return {"template": {"template": {"containers":[{"image":ref}]}}}
    with (patch.object(promoter.jobs, "legacy_writers") as writers,
          patch.object(promoter.jobs, "scheduler", return_value={"state": "ENABLED"}),
          patch.object(promoter.jobs, "fence") as fence,
          patch.object(promoter.jobs, "job", side_effect=job_for)):
        promoter.verify_forward_runtime(data)
    writers.assert_called_once()
    fence.assert_called_once()


def test_scheduler_paused_blocks_traffic_promotion():
    with (patch.object(promoter.jobs, "legacy_writers"),
          patch.object(promoter.jobs, "scheduler", return_value={"state": "PAUSED"}),
          patch.object(promoter.jobs, "fence") as fence):
        with pytest.raises(ValueError, match="scheduler_not_enabled"):
            promoter.verify_forward_runtime(request())
    fence.assert_not_called()


def test_workflow_is_explicit_single_request_only():
    yml=(ROOT/".github/workflows/ghcr-api-forward-promote-dev.yml").read_text()
    assert "ops/ghcr-api-forward-promote-request.json" in yml
    assert "workflow_dispatch:" not in yml
    assert "group: janus-dev-runtime-writers" in yml
    assert "cancel-in-progress: false" in yml
    assert "ghcr-jobs-forward-recovery" in yml
    assert "--forward-recovery" in yml
