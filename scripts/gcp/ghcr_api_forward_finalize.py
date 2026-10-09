#!/usr/bin/env python3
"""Finalize the already serving GHCR dev API after failed legacy rollback rehearsal.

No GCP traffic changes, no old AR image rollback, no force-unlock; only the
original failed run's annotated Git-ref owner can release the lease after
independent live identity/health, Jobs and Scheduler checks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time

import ghcr_api_promote as api
import ghcr_jobs_rollout as jobs
from ghcr_mcp_route import BASE, LEASE, PROJECT, REGION, command, describe, probe

SHA = "fbcc5f58a2fa31f2f36dc4c82702fb62910c7361"
ORIGINAL_RUN = "37936648808"
ORIGINAL_HEAD = "4d6bb78d888e1a04fab1ad4d7492c30d5c61e05b"
RELEASE = "37876247130"
JOBS_RUN = "37915584159"
CANDIDATE = "janus-api-00451-cuw"
EXPECTED_IMAGE = ("ghcr.io/tommylin15/janus-api@sha256:"
                  "a2c263b3ed8729e6677a47fc1084b51a1833721872045b4d4b78035e778f43cf")
REQUEST = Path("ops/ghcr-api-forward-finalize-request.json")
PROOF = Path("/tmp/ghcr-jobs-proof/ghcr-jobs-forward-recovery.json")


def request():
    data = json.loads(REQUEST.read_text())
    if (data.get("intent") != "finalize-serving-ghcr-api-forward-only"
            or data.get("approved") is not True
            or data.get("scope") != "existing-dev-janus-api-only"
            or data.get("source_sha") != SHA
            or data.get("failed_promotion_run") != ORIGINAL_RUN
            or data.get("failed_promotion_head") != ORIGINAL_HEAD
            or data.get("no_old_ar_revision_rollback") is not True
            or data.get("private_job_config_parity") != "NOT_VERIFIED"):
        raise ValueError("forward_finalize_request_invalid")
    return data


def assert_original_lease():
    run = json.loads(command(["gh", "run", "view", ORIGINAL_RUN,
                              "--json", "headSha,status,conclusion,workflowName"]))
    if (run.get("headSha") != ORIGINAL_HEAD
            or run.get("status") != "completed"
            or run.get("conclusion") != "failure"
            or run.get("workflowName") != "Janus GHCR controlled forward-only API promotion"):
        raise ValueError("original_promotion_owner_unverified")
    owned = LEASE + ["--run-id", ORIGINAL_RUN, "--run-attempt", "1", "--sha", ORIGINAL_HEAD]
    command(owned + ["assert"])
    return owned



def wait_for_terminal_executions(timeout_seconds=720, poll_seconds=25):
    """Never cancel/retry a real Job; bound waiting for a scheduled execution."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            jobs.fence()
            return
        except ValueError as error:
            if str(error) != "execution_not_terminal":
                raise
            if time.monotonic() >= deadline:
                raise ValueError("execution_still_active_after_bounded_wait") from None
            time.sleep(poll_seconds)



def assert_ready_readback(service, revision):
    """Fail closed on explicit NotReady, but support gcloud service JSON without
    a Ready condition using reconciled generation, latestReady and live probes.
    """
    status = service.get("status")
    meta = service.get("metadata")
    rev_status = revision.get("status")
    if not isinstance(status, dict) or not isinstance(meta, dict) or not isinstance(rev_status, dict):
        raise ValueError("live_api_readiness_shape_unknown")
    generation = meta.get("generation")
    observed = status.get("observedGeneration")
    if (not str(generation).isdigit() or not str(observed).isdigit()
            or int(generation) != int(observed)):
        raise ValueError("live_api_generation_unreconciled")
    if status.get("latestReadyRevisionName") != CANDIDATE:
        raise ValueError("live_api_latest_ready_revision_mismatch")

    def ready_conditions(rows):
        if not isinstance(rows, list):
            raise ValueError("live_api_conditions_shape_unknown")
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("live_api_conditions_shape_unknown")
        return [row.get("status") for row in rows if row.get("type") == "Ready"]

    service_ready = ready_conditions(status.get("conditions", []))
    if service_ready and service_ready != ["True"]:
        raise ValueError("live_api_not_ready")
    revision_ready = ready_conditions(rev_status.get("conditions", []))
    if revision_ready and revision_ready != ["True"]:
        raise ValueError("live_api_revision_not_ready")
    # Absent Ready is not treated as PASS by itself. verify_current still checks
    # exact image digest, live health, SHA, 401 boundary and candidate OAuth/MCP.

def verify_current():
    api.acceptance(SHA)
    approved = api.check_forward_promotion_request(RELEASE, JOBS_RUN, SHA)
    receipt = json.loads(PROOF.read_text())
    api.check_jobs_receipt(receipt, SHA)
    if receipt.get("phase") != "FORWARD_ONLY_PASS_WITH_PRIVATE_CONFIG_UNVERIFIED":
        raise ValueError("jobs_forward_receipt_not_matching")
    # The live :30 scheduler can start a legitimate execution while the
    # release lease is held. Do not cancel or re-run it. Verify all other
    # runtime invariants again after the bounded wait.
    try:
        api.verify_forward_runtime(approved)
    except ValueError as error:
        if str(error) != "execution_not_terminal":
            raise
        wait_for_terminal_executions()
        api.verify_forward_runtime(approved)
    current = describe()
    if api.active(current) != CANDIDATE:
        raise ValueError("api_ghcr_not_at_100_percent")
    if api.tags(current).get("ghcr-" + SHA[:12]) != CANDIDATE:
        raise ValueError("candidate_tag_drift")
    revision = json.loads(command(["gcloud", "run", "revisions", "describe",
                                   CANDIDATE, f"--project={PROJECT}",
                                   f"--region={REGION}", "--format=json"]))
    assert_ready_readback(current, revision)
    if api.revision_image(revision) != EXPECTED_IMAGE:
        raise ValueError("live_api_digest_drift")
    api.health(SHA)
    probe("https://ghcr-" + SHA[:12] + "---" + BASE.removeprefix("https://"), SHA)
    return current


def run(receipt):
    evidence = {"source_sha": SHA, "failed_promotion_run": ORIGINAL_RUN,
                "phase": "PREFLIGHT", "api_traffic_write": False,
                "old_ar_revision_rollback_verified": False,
                "private_job_config_parity": "NOT_VERIFIED", "lease_released": False}
    def save():
        receipt.write_text(json.dumps(evidence, sort_keys=True))
    save()
    try:
        request()
        evidence["phase"] = "VERIFY_ORIGINAL_LEASE"
        save()
        owned = assert_original_lease()
        evidence["phase"] = "LIVE_RUNTIME_VERIFICATION"
        save()
        verify_current()
        evidence["phase"] = "LIVE_VERIFIED"
        evidence["active_revision"] = CANDIDATE
        evidence["traffic_percent"] = 100
        evidence["health"] = "PASS"
        evidence["owner_boundary"] = "PASS"
        evidence["jobs_scheduler"] = "PASS"
        save()
        command(owned + ["release", "--safe-to-release"])
        evidence["lease_released"] = True
        evidence["phase"] = "FORWARD_ONLY_PASS_OLD_REVISION_ROLLBACK_UNVERIFIED"
        save()
        return 0
    except Exception as error:
        evidence["error_type"] = type(error).__name__
        reason = str(error)
        evidence["reason"] = (reason if re.fullmatch(r"[a-z][a-z0-9_]{3,100}", reason)
                              else "control_failure")
        save()
        return 78


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    return run(parser.parse_args().receipt)


if __name__ == "__main__":
    sys.exit(main())
