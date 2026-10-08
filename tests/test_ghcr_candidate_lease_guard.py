"""Readback-only safety gates before unlocking the Cloud Run GHCR API candidate."""
from __future__ import annotations
import copy
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
guard = runpy.run_path(str(ROOT / "scripts/gcp/ghcr_candidate_lease_guard.py"))
validate = guard["validate"]
SHA = "a" * 64
IMAGE = "ghcr.io/tommylin15/janus-api@sha256:" + SHA
TAG = "ghcr-aaaaaaaaaaaa"


def pair():
    old = {"metadata": {"name": "janus-api", "generation": 11},
           "status": {"observedGeneration": 11,
                      "conditions": [{"type": "Ready", "status": "True"}],
                      "traffic": [{"revisionName": "janus-api-legacy", "percent": 100}]},
           "spec": {"template": {"spec": {"containers": [{"image": "old"}]}}}}
    new = copy.deepcopy(old)
    new["metadata"]["generation"] = 12
    new["status"]["observedGeneration"] = 12
    new["status"]["traffic"].append({"revisionName": "janus-api-ghcr",
                                        "tag": TAG, "percent": 0})
    new["spec"]["template"]["spec"]["containers"][0]["image"] = IMAGE
    return old, new


def test_live_readback_safe_only_for_exact_candidate_and_active_baseline():
    old, new = pair()
    report = validate(old, new, IMAGE, TAG)
    assert report["status"] == "SAFE_TO_RELEASE"
    assert report["reasons"] == []


@pytest.mark.parametrize("mutate, reason", [
    (lambda n: n["status"]["traffic"][0].update(revisionName="janus-api-other"), "active_traffic_changed_or_split"),
    (lambda n: n["status"]["traffic"][0].update(percent=90), "active_traffic_changed_or_split"),
    (lambda n: n["status"]["traffic"][1].update(percent=10), "active_traffic_changed_or_split"),
    (lambda n: n["status"].update(observedGeneration=11), "service_not_ready_or_unreconciled"),
    (lambda n: n["status"].update(conditions=[{"type": "Ready", "status": "False"}]), "service_not_ready_or_unreconciled"),
    (lambda n: n["status"]["traffic"][1].update(percent=5), "candidate_tag_unsafe"),
    (lambda n: n["status"]["traffic"][1].update(revisionName=""), "candidate_tag_unsafe"),
    (lambda n: n["spec"]["template"]["spec"]["containers"][0].update(image="old"), "candidate_digest_mismatch"),
    (lambda n: n["status"]["traffic"].pop(), "candidate_tag_not_observed"),
    (lambda n: n["metadata"].update(name="other-service"), "live_service_mismatch"),
])
def test_unsafe_change_blocks_release(mutate, reason):
    old, new = pair()
    mutate(new)
    report = validate(old, new, IMAGE, TAG)
    assert report["status"] == "BLOCKED"
    assert reason in report["reasons"]


def test_previous_tag_mutation_blocks_release():
    old, new = pair()
    existing = {"revisionName": "tag-old", "percent": 0, "tag": "oauth"}
    old["status"]["traffic"].append(existing)
    new["status"]["traffic"].append({"revisionName": "tag-other", "percent": 0, "tag": "oauth"})
    assert "prior_tag_routes_changed" in validate(old, new, IMAGE, TAG)["reasons"]


def test_missing_snapshots_and_invalid_expected_image_block():
    old, new = pair()
    assert validate(None, new, IMAGE, TAG)["status"] == "BLOCKED"
    assert validate(old, new, "ghcr.io/wrong:latest", TAG)["status"] == "BLOCKED"
    assert validate(old, new, IMAGE, "incorrect-tag")["status"] == "BLOCKED"


def test_workflow_has_acquisition_before_deploy_and_always_on_recovery():
    text = (ROOT / ".github/workflows/ghcr-candidate-dev.yml").read_text()
    assert "contents: write" in text
    assert "ghcr_release_lease.py acquire" in text
    assert "ghcr_release_lease.py assert" in text
    assert "ghcr_candidate_lease_guard.py" in text
    assert "if: always()" in text
    assert "ghcr_release_lease.py release --safe-to-release" in text
    assert text.index("ghcr_release_lease.py acquire") < text.index("gcloud run deploy")
    assert text.index("ghcr_candidate_lease_guard.py") > text.index("gcloud run deploy")
    assert "GH_TOKEN: @@{{ github.token }}" in text.replace("$", "@@")
    assert "--no-traffic" in text
    assert "gcloud builds submit" not in text
    assert "update-traffic" not in text


def test_gcp_recovery_cannot_claim_full_owner_acceptance():
    text = (ROOT / ".github/workflows/ghcr-candidate-dev.yml").read_text()
    assert "Owner OAuth/MCP/PnL still pending" in text
