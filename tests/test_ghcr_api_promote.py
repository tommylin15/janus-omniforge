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
    changed["status"]["conditions"] = [{"type": "Ready", "status": "True"}]
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
