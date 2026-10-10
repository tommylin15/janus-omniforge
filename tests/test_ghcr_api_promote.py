from copy import deepcopy
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import ghcr_api_promote as promote


def receipt():
    jobs = [name for name, _ in promote.JOB_COMPONENT]
    return {
        "source_sha": "a" * 40,
        "phase": "PASS",
        "rollback_mode": "reversible_ghcr",
        "rollback_baseline_verified": True,
        "rollback_available": True,
        "rollback_baseline_sha": "b" * 40,
        "old_image_rollback_exercised": False,
        "snapshots": {name: {"image": "example@sha256:" + "b" * 64,
                             "configuration_hash": "c" * 64} for name in promote.REQUIRED_JOBS},
        "canaries": [{"job": name, "result": "PASS", "execution": f"{name}-{i}"}
                     for name in jobs for i in range(2)],
    }


def test_jobs_receipt_requires_two_distinct_canaries_per_target_job():
    valid = receipt()
    promote.check_jobs_receipt(valid, "a" * 40)
    missing_job = deepcopy(valid)
    missing_job["canaries"][0]["job"] = missing_job["canaries"][1]["job"] = "janus-batch-controller"
    with pytest.raises(ValueError, match="jobs_canary_coverage_incomplete"):
        promote.check_jobs_receipt(missing_job, "a" * 40)
    duplicated = deepcopy(valid)
    duplicated["canaries"][1]["execution"] = duplicated["canaries"][0]["execution"]
    with pytest.raises(ValueError, match="jobs_canary_execution_duplicated"):
        promote.check_jobs_receipt(duplicated, "a" * 40)


@pytest.mark.parametrize("change", [
    lambda p: p.update(source_sha="d" * 40),
    lambda p: p.update(phase="REHEARSAL"),
    lambda p: p["snapshots"].pop("janus-private-pipeline"),
    lambda p: p["canaries"][0].update(result="UNKNOWN"),
])
def test_jobs_receipt_rejects_incomplete_or_stale_evidence(change):
    proof = receipt()
    change(proof)
    with pytest.raises(ValueError):
        promote.check_jobs_receipt(proof, "a" * 40)


@pytest.mark.parametrize("traffic", [
    [{"revisionName": "old", "percent": 70}, {"revisionName": "new", "percent": 30}],
    [{"revisionName": "old", "percent": 99}],
    [],
])
def test_promotion_requires_single_100_percent_baseline(traffic):
    with pytest.raises(ValueError, match="single_active_revision_required"):
        promote.active({"status": {"traffic": traffic}})


def test_switch_checks_traffic_and_preserves_all_tags():
    baseline = {"status": {"traffic": [{"revisionName": "old", "percent": 100},
                                       {"revisionName": "candidate", "tag": "ghcr-accepted", "percent": 0}]}}
    changed = deepcopy(baseline)
    changed["status"]["traffic"][0].update(revisionName="candidate")
    changed["metadata"] = {"generation": 17}
    changed["status"]["observedGeneration"] = 17
    changed["status"]["conditions"] = [{"type": "Ready", "status": "True"},
                                       {"type": "RoutesReady", "status": "True"}]
    with patch.object(promote, "command") as cmd, patch.object(promote, "describe", return_value=changed):
        promote.switch("candidate", baseline)
    assert any("--to-revisions=candidate=100" in v for v in cmd.call_args_list[-1].args[0])


def test_api_promotion_workflow_is_explicit_and_requires_jobs_proof():
    text = (ROOT / ".github/workflows/ghcr-api-promote-dev.yml").read_text()
    assert "workflow_dispatch:" in text and "push:" not in text
    assert "group: janus-dev-runtime-writers" in text
    assert "gh run download" in text and "ghcr-jobs-rollout-receipt" in text
    assert "--release-run" in text and "--jobs-run" in text
    assert "id-token: write" in text and "environment: dev" in text


def test_promotion_requires_public_retrievable_old_ghcr_baseline():
    from json import dumps
    old_sha = "a" * 40
    old_revision = "janus-api-good-old"
    current = "ghcr.io/tommylin15/janus-api@sha256:" + "b" * 64
    service = {"status": {"traffic": [{"revisionName":old_revision, "percent":100}]}}
    revision = {"spec": {"containers": [{"image": current}]},
                "status": {"conditions": [{"type":"Ready", "status":"True"}]}}
    manifest = {"Digest":"sha256:"+"b"*64,
                "Labels":{"org.opencontainers.image.revision":old_sha}}
    with patch.object(promote, "command", side_effect=[dumps(revision),dumps(manifest)]) as call:
        assert promote.verify_previous_ghcr_rollback(service,old_sha) == current
    assert call.call_count == 2
    assert "--no-creds" in call.call_args.args[0]

    wrong_revision = deepcopy(revision)
    wrong_revision["spec"]["containers"][0]["image"] = "us-docker.pkg.dev/old-image"
    with patch.object(promote,"command",return_value=dumps(wrong_revision)) as call:
        with pytest.raises(ValueError,match="previous_ghcr_rollback_image_required"):
            promote.verify_previous_ghcr_rollback(service,old_sha)
    call.assert_called_once()


def test_promotion_rejects_old_ghcr_digest_or_source_mismatch():
    from json import dumps
    sha="a"*40
    ref="ghcr.io/tommylin15/janus-api@sha256:"+"b"*64
    service={"status":{"traffic":[{"revisionName":"old","percent":100}]}}
    revision={"spec":{"containers":[{"image":ref}]},
              "status":{"conditions":[{"type":"Ready","status":"True"}]}}
    with patch.object(promote,"command",side_effect=[dumps(revision),dumps({
            "Digest":"sha256:"+"b"*64,
            "Labels":{"org.opencontainers.image.revision":"c"*40}})]):
        with pytest.raises(ValueError,match="previous_ghcr_registry_source_unverified"):
            promote.verify_previous_ghcr_rollback(service,sha)


def test_previous_revision_not_ready_blocks_before_registry_probe():
    from json import dumps
    ref="ghcr.io/tommylin15/janus-api@sha256:"+"b"*64
    service={"status":{"traffic":[{"revisionName":"old","percent":100}]}}
    revision={"spec":{"containers":[{"image":ref}]},
              "status":{"conditions":[{"type":"Ready","status":"False"}]}}
    with patch.object(promote,"command",return_value=dumps(revision)) as cmd:
        with pytest.raises(ValueError,match="previous_ghcr_revision_not_ready"):
            promote.verify_previous_ghcr_rollback(service,"a"*40)
    cmd.assert_called_once()


def test_previous_baseline_is_versioned_and_ancestor_checked():
    import json
    baseline={"status":"VERIFIED_PUBLIC_GHCR_ROLLBACK_BASELINE",
              "source_sha":"a"*40,
              "api_image":"ghcr.io/tommylin15/janus-api@sha256:"+"b"*64,
              "private_historical_config_parity":"NOT_VERIFIED",
              "old_ar_rollback_exercised":False}
    with patch.object(promote.Path,"read_text",return_value=json.dumps(baseline)), \
         patch.object(promote,"command") as cmd:
        assert promote.approved_previous_baseline("c"*40) == baseline
    cmd.assert_called_once_with(["git","merge-base","--is-ancestor","a"*40,"c"*40])
    for change in ({"status":"PASS"}, {"source_sha":"c"*40},
                   {"api_image":"us-docker.pkg.dev/old"}, {"old_ar_rollback_exercised":True}):
        bad={**baseline,**change}
        with patch.object(promote.Path,"read_text",return_value=json.dumps(bad)), \
             patch.object(promote,"command") as cmd:
            with pytest.raises(ValueError,match="approved_ghcr_baseline_missing"):
                promote.approved_previous_baseline("c"*40)
        cmd.assert_not_called()


@pytest.mark.parametrize("change", [
    lambda proof: proof.pop("rollback_baseline_verified"),
    lambda proof: proof.update(rollback_mode="user_authorized_forward_only"),
    lambda proof: proof.update(rollback_available=False),
    lambda proof: proof.update(old_image_rollback_exercised=True),
])
def test_regular_traffic_promotion_rejects_unverified_jobs_reversibility(change):
    proof=receipt()
    change(proof)
    with pytest.raises(ValueError,match="regular_jobs_reversible_baseline_unverified"):
        promote.check_jobs_receipt(proof,"a"*40)


def test_api_switch_waits_for_reconciled_ready_without_changing_other_tags():
    import copy
    baseline={"status":{"traffic":[{"revisionName":"old","percent":100,"tag":"active"},
                                  {"revisionName":"new","tag":"ghcr-candidate","percent":0}]},
              "spec":{"template":{"containers":[{"image":"unchanged"}]},
                      "traffic":[{"revisionName":"old","percent":100}]}}
    expected=copy.deepcopy(baseline)
    expected["status"]["traffic"][0]["revisionName"]="new"
    expected["spec"]["traffic"]=[{"revisionName":"new","percent":100}]
    expected["metadata"]={"generation":"9"}
    expected["status"]["observedGeneration"]="9"
    expected["status"]["conditions"]=[{"type":"Ready","status":"True"},
                                      {"type":"RoutesReady","status":"True"}]
    pending=copy.deepcopy(expected)
    pending["status"]["observedGeneration"]=8
    with (patch.object(promote,"command") as cmd,
          patch.object(promote,"describe",side_effect=[pending,expected]) as read,
          patch.object(promote.time,"sleep") as sleep):
        promote.switch("new",baseline)
    assert read.call_count==2
    sleep.assert_called_once_with(5)
    assert any("--to-revisions=new=100" in value for value in cmd.call_args_list[1].args[0])


def test_api_switch_rejects_route_not_ready_even_at_full_target_traffic():
    import copy
    baseline={"status":{"traffic":[{"revisionName":"old","percent":100}]}}
    broken={"metadata":{"generation":3},
            "status":{"observedGeneration":3,
                      "traffic":[{"revisionName":"new","percent":100}],
                      "conditions":[{"type":"Ready","status":"True"},
                                    {"type":"RoutesReady","status":"False"}]}}
    with (patch.object(promote,"command"),
          patch.object(promote,"describe",return_value=broken),
          patch.object(promote.time,"sleep",return_value=None)):
        with pytest.raises(ValueError,match="traffic_route_not_reconciled"):
            promote.switch("new",baseline)


def test_api_switch_rejects_nontraffic_service_configuration_change():
    baseline={"status":{"traffic":[{"revisionName":"old","percent":100}]},
              "spec":{"template":{"image":"old"}}}
    altered={"metadata":{"generation":3},
             "status":{"observedGeneration":3,
                       "traffic":[{"revisionName":"new","percent":100}],
                       "conditions":[{"type":"Ready","status":"True"}]},
             "spec":{"template":{"image":"changed"}}}
    with (patch.object(promote,"command"),
          patch.object(promote,"describe",return_value=altered)):
        with pytest.raises(ValueError,match="service_nontraffic_config_drift"):
            promote.switch("new",baseline)
