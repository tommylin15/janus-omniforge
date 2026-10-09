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


def test_cloud_run_explicit_null_zero_traffic_fields_are_safe():
    old, new = pair()
    new["status"]["traffic"][1]["percent"] = None
    assert validate(old, new, IMAGE, TAG)["status"] == "SAFE_TO_RELEASE"


def test_cloud_run_old_zero_percent_tag_null_safe():
    old, new = pair()
    old["status"]["traffic"].append({"revisionName": "old-tag", "tag": "legacy", "percent": None})
    new["status"]["traffic"].append({"revisionName": "old-tag", "tag": "legacy", "percent": None})
    assert validate(old, new, IMAGE, TAG)["status"] == "SAFE_TO_RELEASE"


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
    assert text.index("python scripts/gcp/ghcr_candidate_lease_guard.py") > text.index("gcloud run deploy")
    assert "GH_TOKEN: @@{{ github.token }}" in text.replace("$", "@@")
    assert "--no-traffic" in text
    assert "gcloud builds submit" not in text
    assert "update-traffic" not in text


def test_gcp_recovery_cannot_claim_full_owner_acceptance():
    text = (ROOT / ".github/workflows/ghcr-candidate-dev.yml").read_text()
    assert "Owner OAuth/MCP/PnL still pending" in text


def test_legacy_manual_and_candidate_share_actions_serialization_group():
    ghcr = (ROOT / ".github/workflows/ghcr-candidate-dev.yml").read_text()
    legacy = (ROOT / ".github/workflows/deploy-dev.yml").read_text()
    group = "group: janus-dev-runtime-writers"
    assert group in ghcr and group in legacy
    assert "cancel-in-progress: false" in ghcr
    assert "cancel-in-progress: false" in legacy
    # This defense covers GitHub runs, not an independent Cloud Build trigger.


def test_all_shared_runtime_writers_serialize_and_legacy_rejects_held_lease():
    for name in ("ghcr-candidate-dev.yml", "deploy-dev.yml",
                 "run-dev-ingestion.yml", "ghcr-scheduler-operator-drill.yml"):
        text = (ROOT / ".github/workflows" / name).read_text()
        assert "group: janus-dev-runtime-writers" in text
        assert "cancel-in-progress: false" in text
    for name, first_write in (("deploy-dev.yml", "bash scripts/gcp/deploy-dev.sh"),
                              ("run-dev-ingestion.yml", "gcloud run jobs update")):
        text = (ROOT / ".github/workflows" / name).read_text()
        assert text.index("ghcr_release_lease.py inspect") < text.index(first_write)
        assert "jq -e '.status == \"ABSENT\"'" in text
        assert "GH_TOKEN: ${{ github.token }}" in text


def test_candidate_same_sha_retry_requires_immutable_revision_and_skips_deploy():
    workflow = (ROOT / ".github/workflows/ghcr-candidate-dev.yml").read_text()
    assert 'existing_revision=' in workflow
    assert 'gcloud run revisions describe "$existing_revision"' in workflow
    assert '"$GHCR_PUBLIC_IMAGE"' in workflow
    assert 'Reused existing 0% GHCR digest candidate' in workflow
    assert 'if [[ -n "$existing_revision" ]]' in workflow
    assert 'else\n            gcloud run deploy' in workflow
    assert 'gcloud run deploy "$SERVICE"' in workflow
    assert 'ghcr_candidate_lease_guard.py' in workflow
    assert workflow.index('ghcr_release_lease.py assert') < workflow.index('gcloud run deploy "$SERVICE"')


def test_revision_reuse_allows_only_exact_ghcr_or_observed_cloud_run_cache_mirror():
    workflow = (ROOT / ".github/workflows/ghcr-candidate-dev.yml").read_text()
    assert 'cache.us-docker.pkg.dev/' in workflow
    assert '(.spec.containers[0].image == $image)' in workflow
    assert '(.spec.containers[0].image == ("cache.us-docker.pkg.dev/" + $image))' in workflow
    assert '(.status.conditions | any(.type=="Ready" and .status=="True"))' in workflow
    assert 'gcloud artifacts docker' not in workflow
    assert 'us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc' not in workflow
