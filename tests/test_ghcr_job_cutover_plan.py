"""GHCR Janus Jobs read-only image plan contracts."""
import json
import runpy
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
guard_tests = runpy.run_path(str(ROOT / "tests/test_ghcr_job_cutover_guard.py"))
valid = guard_tests["evidence"]
plan_module = runpy.run_path(str(ROOT / "scripts/gcp/ghcr_job_cutover_plan.py"))
build_plan = plan_module["build_plan"]


def test_produces_reversible_image_only_plan_in_safe_order():
    report = build_plan(valid())
    assert report["status"] == "DRY_RUN_READY"
    assert report["resource_writes"] == 0
    assert report["automatic_apply"] is False
    assert [x["job"] for x in report["updates"]] == [
        "janus-private-pipeline", "janus-intelligence-mart",
        "janus-ingestion-core", "janus-batch-controller"
    ]
    assert [x["job"] for x in report["rollback_order"]] == list(
        reversed([x["job"] for x in report["updates"]]))
    assert report["protected_unchanged_jobs"] == ["janus-research-big-move-500"]
    assert report["updates"][-1]["component"] == "ingestion-core"
    assert report["updates"][-2]["target_pinned_image"] == report["updates"][-1]["target_pinned_image"]
    assert all("@sha256:" in row["previous_pinned_image"]
               and "@sha256:" in row["target_pinned_image"] for row in report["updates"])


@pytest.mark.parametrize("condition,blocker", [
    ("live_scheduler", "scheduler_still_enabled"),
    ("mutex_missing", "durable_deployment_mutex_unverified"),
    ("owner_missing", "authenticated_acceptance_unverified"),
    ("execution_unclear", "execution_janus-private-pipeline_unfenced"),
])
def test_blocking_live_condition_never_authorizes_release(condition, blocker):
    d = valid()
    if condition == "live_scheduler":
        d["scheduler"]["jobs"][0]["state"] = "ENABLED"
    elif condition == "mutex_missing":
        d["durable_deployment_mutex_verified"] = False
    elif condition == "owner_missing":
        d["owner_oauth_and_data_acceptance_verified"] = False
    elif condition == "execution_unclear":
        d["job_snapshots"]["janus-private-pipeline"]["potentially_active"] = 9
    report = build_plan(d)
    assert report["status"] == "BLOCKED"
    assert blocker in report["blockers"]
    assert report["resource_writes"] == 0
    assert report["automatic_apply"] is False


def test_missing_pinned_rollback_prevents_plan():
    d = valid()
    d["job_snapshots"]["janus-ingestion-core"]["image"] = "not-a-digest"
    report = build_plan(d)
    assert report["status"] == "BLOCKED"
    assert "image_mapping_janus-ingestion-core_unknown" in report["blockers"]


def test_missing_registry_digest_prevents_plan():
    d = valid()
    d["ghcr_images"]["private-pipeline"]["digest"] = ""
    report = build_plan(d)
    assert report["status"] == "BLOCKED"
    assert "image_mapping_janus-private-pipeline_unknown" in report["blockers"]


def test_no_sensitive_data_or_env_in_plan():
    d = valid()
    d["job_snapshots"]["janus-private-pipeline"]["database_url"] = "DO_NOT_EXPORT_SECRET"
    d["owner_email"] = "private@example.com"
    value = json.dumps(build_plan(d))
    assert "DO_NOT_EXPORT_SECRET" not in value
    assert "private@example.com" not in value
    assert "args" not in value


def test_empty_evidence_blocked_not_key_error():
    report = build_plan({})
    assert report["status"] == "BLOCKED"
    assert report["updates"] == []
    assert report["automatic_apply"] is False
