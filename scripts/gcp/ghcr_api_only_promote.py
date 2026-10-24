#!/usr/bin/env python3
"""Promote one existing dev API 0%-traffic candidate without touching Jobs/Stage.

Reuses release, candidate, auth and GHCR rollback gates. Traffic is changed
only under the shared owner lease. Failures after traffic mutation restore the
verified previous revision; unknown rollback retains the lease for recovery.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import ghcr_api_promote as api
from ghcr_mcp_route import BASE, PROJECT, REGION, SERVICE, LEASE, command, describe, request


REQUEST = Path("ops/ghcr-api-only-promote-request.json")
SHA_RE = re.compile(r"[0-9a-f]{40}")
RUN_RE = re.compile(r"[0-9]{6,15}")
IMAGE_RE = re.compile(r"ghcr[.]io/tommylin15/janus-api@sha256:[0-9a-f]{64}")


def approved_request(payload: dict) -> dict:
    keys = ("source_sha", "release_run", "candidate_run", "auth_boundary_run", "prior_serving_sha")
    if (payload.get("intent") != "promote-existing-dev-api-only-fixed-ghcr"
            or payload.get("approved") is not True
            or payload.get("scope") != "existing-dev-janus-api-only"
            or payload.get("rollback_mode") != "reversible_ghcr"
            or payload.get("traffic_validation_mode", "rehearsal") not in {"direct", "rehearsal"}
            or payload.get("no_jobs_mutation") is not True
            or payload.get("no_scheduler_mutation") is not True
            or payload.get("no_storage_mutation") is not True
            or payload.get("no_iam_mutation") is not True
            or any(not isinstance(payload.get(k), str) for k in keys)
            or not SHA_RE.fullmatch(payload["source_sha"])
            or not SHA_RE.fullmatch(payload["prior_serving_sha"])
            or payload["source_sha"] == payload["prior_serving_sha"]
            or any(not RUN_RE.fullmatch(payload[k]) for k in
                   ("release_run", "candidate_run", "auth_boundary_run"))):
        raise ValueError("api_only_request_not_approved")
    return payload


def check_run(number: str, job_name: str) -> None:
    result = json.loads(command(["gh", "run", "view", number,
                                 "--json", "status,conclusion,workflowName,jobs"]))
    if result.get("status") != "completed" or result.get("conclusion") != "success":
        raise ValueError("upstream_run_not_successful")
    jobs = result.get("jobs", [])
    matching = [j for j in jobs if j.get("name") == job_name]
    if len(matching) != 1 or matching[0].get("conclusion") != "success":
        raise ValueError("upstream_job_receipt_invalid")


def preflight(payload: dict) -> None:
    source = payload["source_sha"]
    command(["git", "merge-base", "--is-ancestor", source, "HEAD"])
    candidate = json.loads(Path("ops/ghcr-candidate-request.json").read_text())
    boundary = json.loads(Path("ops/ghcr-candidate-boundary-request.json").read_text())
    if (candidate.get("sha") != source
            or candidate.get("release_run") != payload["release_run"]
            or candidate.get("promotion") is not False
            or boundary.get("sha") != source
            or boundary.get("no_gcp_mutation") is not True):
        raise ValueError("candidate_boundary_source_not_matching")
    check_run(payload["release_run"], "release-verify")
    for name in ("release-flutter", "release-tests"):
        check_run(payload["release_run"], name)
    check_run(payload["candidate_run"], "candidate")
    check_run(payload["auth_boundary_run"], "auth-boundary")
    manifest = json.loads(command(["skopeo", "inspect", "--no-creds",
                                   "docker://ghcr.io/tommylin15/janus-api:sha-" + source]))
    digest = manifest.get("Digest")
    if (not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
            or manifest.get("Labels", {}).get("org.opencontainers.image.revision") != source):
        raise ValueError("candidate_registry_digest_invalid")


def live_pair(payload: dict) -> tuple[dict, str, str, str]:
    baseline = describe()
    previous = api.active(baseline)
    if not any(c.get("type") == "Ready" and c.get("status") == "True"
               for c in baseline.get("status", {}).get("conditions", [])):
        raise ValueError("service_not_ready")
    tag = "ghcr-" + payload["source_sha"][:12]
    selected = [row for row in baseline.get("status", {}).get("traffic", [])
                if row.get("tag") == tag and row.get("percent", 0) == 0]
    if len(selected) != 1:
        raise ValueError("candidate_not_zero_traffic")
    candidate = selected[0]["revisionName"]
    if candidate == previous:
        raise ValueError("candidate_already_active_or_invalid")
    revision = json.loads(command(["gcloud", "run", "revisions", "describe",
                                  candidate, "--project=" + PROJECT, "--region=" + REGION,
                                  "--format=json"]))
    image = api.revision_image(revision)
    if not IMAGE_RE.fullmatch(image):
        raise ValueError("candidate_digest_not_pinned")
    manifest = json.loads(command(["skopeo", "inspect", "--no-creds", "docker://" + image]))
    if (manifest.get("Digest") != image.rsplit("@", 1)[-1]
            or manifest.get("Labels", {}).get("org.opencontainers.image.revision") != payload["source_sha"]):
        raise ValueError("candidate_image_source_mismatch")
    if not any(c.get("type") == "Ready" and c.get("status") == "True"
               for c in revision.get("status", {}).get("conditions", [])):
        raise ValueError("candidate_revision_not_ready")
    code, _, body = request(selected[0]["url"] + "/app/build-id.txt")
    if code != 200 or body.decode().strip() != payload["source_sha"]:
        raise ValueError("candidate_build_not_ready")
    code, _, _ = request(selected[0]["url"] + "/api/v1/admin/gcs-storage/inspect", {})
    if code not in (401, 403):
        raise ValueError("candidate_admin_auth_exposed")
    status, _, body = request(BASE + "/app/build-id.txt")
    if status != 200 or body.decode().strip() != payload["prior_serving_sha"]:
        raise ValueError("prior_live_source_not_matching_request")
    api.verify_previous_ghcr_rollback(baseline, payload["prior_serving_sha"])
    return baseline, previous, candidate, image


def promote(receipt: Path) -> int:
    journal = {"component": "ghcr-api-only-promotion", "phase": "PREFLIGHT",
               "service": SERVICE, "jobs_mutated": False, "scheduler_mutated": False,
               "storage_mutated": False, "iam_mutated": False,
               "traffic_mutation": False, "rollback_exercised": False}
    def save():
        receipt.write_text(json.dumps(journal, sort_keys=True))
    save()
    lease = False
    previous = None
    baseline = None
    mutated = False
    safe = False
    try:
        payload = approved_request(json.loads(REQUEST.read_text()))
        journal["source_sha"] = payload["source_sha"]
        journal["prior_serving_sha"] = payload["prior_serving_sha"]
        journal["release_run"] = payload["release_run"]
        journal["candidate_run"] = payload["candidate_run"]
        journal["auth_boundary_run"] = payload["auth_boundary_run"]
        preflight(payload)
        journal["phase"] = "GCP_READONLY_PREFLIGHT"
        save()
        baseline, previous, candidate, image = live_pair(payload)
        journal["prior_revision"] = previous
        journal["candidate_revision"] = candidate
        journal["candidate_image"] = image
        save()
        command(LEASE + ["acquire"])
        lease = True
        command(LEASE + ["assert"])
        locked, locked_previous, locked_candidate, _ = live_pair(payload)
        if locked_previous != previous or locked_candidate != candidate:
            raise ValueError("serving_or_candidate_drift_under_lease")
        baseline = locked
        mode = payload.get("traffic_validation_mode", "rehearsal")
        journal["traffic_validation_mode"] = mode
        if mode == "rehearsal":
            journal["phase"] = "REHEARSE_TRAFFIC_AND_ROLLBACK"
            journal["traffic_mutation"] = True
            save()
            mutated = True
            api.switch(candidate, baseline)
            api.health(payload["source_sha"])
            api.switch(previous, baseline)
            api.health(payload["prior_serving_sha"])
            journal["rollback_exercised"] = True
            save()
        # In explicitly approved direct mode, switch only once; revert to the
        # pinned previous revision strictly on an actual post-switch failure.
        journal["phase"] = "PROMOTE_API_100_PERCENT"
        journal["traffic_mutation"] = True
        save()
        mutated = True
        api.switch(candidate, baseline)
        api.health(payload["source_sha"])
        if api.active(describe()) != candidate:
            raise ValueError("post_promotion_revision_drift")
        journal["phase"] = "PASS_API_ONLY_100_PERCENT"
        safe = True
        save()
    except Exception as exc:
        journal["failure_type"] = type(exc).__name__
        journal["phase"] = "FAILED_ROLLBACK_REQUIRED" if mutated else "PREFLIGHT_BLOCKED"
        save()
        if mutated and previous and baseline:
            try:
                api.switch(previous, baseline)
                api.health(journal["prior_serving_sha"])
                journal["phase"] = "RESTORED_PREVIOUS_100_PERCENT"
                safe = True
            except Exception:
                journal["phase"] = "ROLLBACK_UNVERIFIED_LEASE_RETAINED"
                safe = False
            save()
        elif lease and previous and baseline:
            if api.active(describe()) == previous:
                safe = True
    finally:
        if lease and safe:
            command(LEASE + ["release", "--safe-to-release"])
            journal["lease_released"] = True
            save()
    return 0 if journal.get("phase") == "PASS_API_ONLY_100_PERCENT" else 78


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    sys.exit(promote(args.receipt))
