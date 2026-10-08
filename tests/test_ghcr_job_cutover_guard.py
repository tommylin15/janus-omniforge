"""Pure cutover guard regressions; no GCP resources, secrets or network."""
import json
import runpy
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
module = runpy.run_path(str(ROOT / "scripts/gcp/ghcr_job_cutover_guard.py"))
assess = module["assess"]
PROJECT = module["PROJECT"]
REGION = module["REGION"]
JOBS = module["REQUIRED_JOBS"]
COMPONENTS = module["EXPECTED_COMPONENTS"]


def evidence():
    sha = "0b93d99d42aaff662a3408d749d70aa9d04b1042"
    return {
        "project": PROJECT,
        "region": REGION,
        "source_sha": sha,
        "ghcr_images": {
            k: {"digest": "sha256:" + "a" * 64, "source_sha": sha,
                "anonymous_pull_verified": True}
            for k in COMPONENTS
        },
        "scheduler": {"full_region_enumeration": True, "jobs": [{
            "name": "janus-ingestion-daily",
            "state": "PAUSED",
            "schedule": "30 * * * *",
            "time_zone": "Asia/Taipei",
            "target": module["SCHEDULER_TARGET"],
            "identity": module["SCHEDULER_IDENTITY"],
            "retry_count": 1,
        }]},
        "job_snapshots": {
            k: {"image": "us-central1-docker.pkg.dev/example/repo/img@sha256:" + "b" * 64,
                "rollback_image_readable": True,
                "execution_list_complete": True,
                "potentially_active": 0}
            for k in JOBS
        },
        "durable_deployment_mutex_verified": True,
        "owner_oauth_and_data_acceptance_verified": True,
        "rollback_procedure_verified": True,
    }


def test_full_verified_hypothetical_snapshot_only_yields_separate_approval():
    assert assess(evidence())["status"] == "READY_FOR_SEPARATE_EXPLICIT_APPROVAL"


def test_live_enabled_hourly_scheduler_blocks_even_with_all_other_gates():
    d = evidence()
    d["scheduler"]["jobs"][0]["state"] = "ENABLED"
    report = assess(d)
    assert report["status"] == "BLOCKED"
    assert "scheduler_still_enabled" in report["blockers"]


@pytest.mark.parametrize("change,reason", [
    ("missing_scheduler_enumeration", "scheduler_enumeration_incomplete"),
    ("legacy_scheduler", "scheduler_controller_topology_mismatch"),
    ("wrong_target", "scheduler_controller_contract_mismatch"),
    ("running_job", "execution_janus-batch-controller_unfenced"),
    ("partial_execution_list", "execution_janus-private-pipeline_unfenced"),
    ("unreadable_rollback", "rollback_janus-ingestion-core_unverified"),
    ("unverified_public_image", "ghcr_intelligence-mart_unverified"),
    ("no_mutex", "durable_deployment_mutex_unverified"),
    ("no_owner_acceptance", "authenticated_acceptance_unverified"),
    ("no_rollback_drill", "rollback_procedure_unverified"),
])
def test_unknown_and_unsafe_conditions_fail_closed(change, reason):
    d = evidence()
    if change == "missing_scheduler_enumeration":
        d["scheduler"]["full_region_enumeration"] = False
    elif change == "legacy_scheduler":
        d["scheduler"]["jobs"].append({"name": "janus-private-pipeline-0740"})
    elif change == "wrong_target":
        d["scheduler"]["jobs"][0]["target"] = "https://example.com/other"
    elif change == "running_job":
        d["job_snapshots"]["janus-batch-controller"]["potentially_active"] = 1
    elif change == "partial_execution_list":
        d["job_snapshots"]["janus-private-pipeline"]["execution_list_complete"] = False
    elif change == "unreadable_rollback":
        d["job_snapshots"]["janus-ingestion-core"]["rollback_image_readable"] = False
    elif change == "unverified_public_image":
        d["ghcr_images"]["intelligence-mart"]["anonymous_pull_verified"] = False
    elif change == "no_mutex":
        d["durable_deployment_mutex_verified"] = False
    elif change == "no_owner_acceptance":
        d["owner_oauth_and_data_acceptance_verified"] = False
    elif change == "no_rollback_drill":
        d["rollback_procedure_verified"] = False
    report = assess(d)
    assert report["status"] == "BLOCKED"
    assert reason in report["blockers"]
    assert report["resource_writes"] == 0


def test_missing_fields_cannot_allow_release():
    report = assess({})
    assert report["status"] == "BLOCKED"
    assert len(report["blockers"]) > 5


def test_secret_or_private_data_does_not_appear_in_report():
    d = evidence()
    d["secret"] = "DONT_ECHO_THIS_TEST_SECRET"
    d["job_snapshots"]["janus-ingestion-core"]["owner_email"] = "secret@example.com"
    report = json.dumps(assess(d))
    assert "DONT_ECHO" not in report
    assert "secret@example.com" not in report


def test_bool_is_not_a_valid_active_execution_count():
    d = evidence()
    d["job_snapshots"]["janus-private-pipeline"]["potentially_active"] = False
    assert "execution_janus-private-pipeline_unfenced" in assess(d)["blockers"]
