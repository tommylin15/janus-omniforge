#!/usr/bin/env python3
"""One-off fail-closed reconciliation of a terminal, abandoned Janus deploy lease.

A normal lease may only be released by its own run. This separately audited
terminal-owner recovery does not impersonate that owner; it verifies its exact
immutable identity plus read-only GitHub/GCP fences before deleting only its
stale Git ref. No Cloud Run, scheduler, database, or IAM mutation is allowed.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

REPO = "tommylin15/janus-omniforge"
TAG = "janus-ghcr-deploy-global-v1"
OWNER_RUN = 38559419684
OWNER_SHA = "b1f3a616652bc08edf435ee0f786b884a06ea82e"
TAG_SHA = "d70502586aeaa95bdd0cc6d6fb13cc2cf7d54525"
LEASE_REF = f"repos/{REPO}/git/ref/tags/{TAG}"
LEASE_TAG = f"repos/{REPO}/git/tags/{TAG_SHA}"
MARKER = "JANUS_DEPLOY_LEASE_V1:"


def verify_owner(run: dict[str, Any]) -> None:
    if (run.get("id") != OWNER_RUN or run.get("head_sha") != OWNER_SHA
            or run.get("run_attempt") != 1
            or run.get("name") != "Janus bounded full-market business acceptance"
            or run.get("status") != "completed" or run.get("conclusion") != "failure"):
        raise ValueError("owner_run_not_exactly_terminal_failed")


def verify_lease(ref: dict[str, Any], tag: dict[str, Any]) -> None:
    if (ref.get("ref") != f"refs/tags/{TAG}"
            or ref.get("object") != {"sha": TAG_SHA, "type": "tag",
                                     "url": f"https://api.github.com/repos/{REPO}/git/tags/{TAG_SHA}"}
            or tag.get("sha") != TAG_SHA or tag.get("tag") != TAG
            or tag.get("object", {}).get("type") != "commit"
            or tag.get("object", {}).get("sha") != OWNER_SHA):
        raise ValueError("lease_identity_mismatch")
    message = tag.get("message", "")
    if not isinstance(message, str) or not message.startswith(MARKER):
        raise ValueError("lease_payload_invalid")
    if json.loads(message[len(MARKER):]) != {
            "run_id": OWNER_RUN, "run_attempt": 1, "source_sha": OWNER_SHA}:
        raise ValueError("lease_owner_changed")


def service_identity(data: dict[str, Any]) -> tuple[str, str]:
    if data.get("metadata", {}).get("name") != "janus-api":
        raise ValueError("unexpected_api_service")
    if not any(c.get("type") == "Ready" and c.get("status") == "True"
               for c in data.get("status", {}).get("conditions", [])):
        raise ValueError("api_not_ready")
    traffic = data.get("status", {}).get("traffic", [])
    live = [t for t in traffic if t.get("percent", 0) > 0]
    if (len(live) != 1 or live[0].get("percent") != 100
            or not live[0].get("revisionName")):
        raise ValueError("api_traffic_not_single_100")
    if str(data.get("spec", {}).get("template", {}).get("metadata", {}).get(
            "annotations", {}).get("autoscaling.knative.dev/minScale", "0")) != "0":
        raise ValueError("api_min_instances_cost_fence")
    return live[0]["revisionName"], json.dumps(traffic, sort_keys=True)


def _gh(*args: str) -> dict[str, Any]:
    proc = subprocess.run(["gh", "api", *args], text=True,
                          capture_output=True, check=False, timeout=30)
    if proc.returncode:
        raise ValueError("github_read_or_write_denied")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _service() -> dict[str, Any]:
    proc = subprocess.run(
        ["gcloud", "run", "services", "describe", "janus-api",
         "--project=gen-lang-client-0593591102", "--region=us-central1",
         "--format=json"], text=True, capture_output=True, check=False, timeout=50)
    if proc.returncode:
        raise ValueError("gcp_api_readback_denied")
    return json.loads(proc.stdout)


def main() -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("wrong_repository_or_branch")
    if os.environ.get("JANUS_TERMINAL_LEASE_RECOVERY") != str(OWNER_RUN):
        raise ValueError("recovery_authorization_missing")
    verify_owner(_gh(f"repos/{REPO}/actions/runs/{OWNER_RUN}"))
    verify_lease(_gh(LEASE_REF), _gh(LEASE_TAG))

    # Import the existing tested Cloud Run v2 operations, with all-page
    # execution fencing rather than only the last few visible executions.
    from ghcr_jobs_rollout import (REQUIRED_JOBS, fence, job,
                                   scheduler, legacy_writers)
    before = service_identity(_service())
    if scheduler().get("state") != "ENABLED":
        raise ValueError("scheduler_not_enabled")
    legacy_writers()
    fence()
    for name in REQUIRED_JOBS:
        job(name)  # Fail on reconciling, missing, or unhealthy Job.
    after = service_identity(_service())
    if before != after:
        raise ValueError("api_traffic_drift_during_recovery")
    # Exactly the same owner and annotated tag must remain immediately before
    # the only permitted write: deleting this abandoned Git ref.
    verify_owner(_gh(f"repos/{REPO}/actions/runs/{OWNER_RUN}"))
    verify_lease(_gh(LEASE_REF), _gh(LEASE_TAG))
    _gh("-X", "DELETE", f"repos/{REPO}/git/refs/tags/{TAG}")
    # For deletion readback, GitHub must return 404; all other errors fail.
    probe = subprocess.run(["gh", "api", LEASE_REF], text=True,
                           capture_output=True, check=False, timeout=30)
    if probe.returncode == 0 or "404" not in probe.stderr:
        raise ValueError("lease_delete_readback_uncertain")
    print(json.dumps({"status": "PASS", "operation": "terminal_lease_recovery",
                      "old_owner_run": OWNER_RUN, "tag": TAG,
                      "runtime_writes": 0, "api_traffic_unchanged": True,
                      "all_job_executions_terminal": True}, sort_keys=True))


if __name__ == "__main__":
    main()
