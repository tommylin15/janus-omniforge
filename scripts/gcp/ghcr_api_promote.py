#!/usr/bin/env python3
"""Promote only an accepted existing dev candidate, rehearse and verify rollback."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from collections import Counter

import ghcr_jobs_rollout as jobs
from ghcr_jobs_rollout import acceptance, JOB_COMPONENT, REQUIRED_JOBS
from ghcr_mcp_route import BASE, PROJECT, REGION, SERVICE, LEASE, command, describe, request, probe


def active(data):
    rows = [(row["revisionName"], row["percent"]) for row in data["status"]["traffic"]
            if row.get("percent", 0) > 0]
    if len(rows) != 1 or rows[0][1] != 100:
        raise ValueError("single_active_revision_required")
    return rows[0][0]


def revision_image(revision):
    """Fail closed on an unexpected gcloud Revision JSON shape, no raw config in logs."""
    spec = revision.get("spec") if isinstance(revision, dict) else None
    containers = spec.get("containers") if isinstance(spec, dict) else None
    if not isinstance(containers, list) or len(containers) != 1:
        raise ValueError("candidate_revision_container_unknown")
    container = containers[0]
    if not isinstance(container, dict) or not isinstance(container.get("image"), str):
        raise ValueError("candidate_revision_image_unknown")
    return container["image"].removeprefix("cache.us-docker.pkg.dev/")


def tags(data):
    return {row["tag"]: row["revisionName"] for row in data["status"]["traffic"] if row.get("tag")}




def approved_previous_baseline(candidate_sha):
    data = json.loads(Path("ops/ghcr-active-baseline.json").read_text())
    sha = data.get("source_sha")
    if (data.get("status") != "VERIFIED_PUBLIC_GHCR_ROLLBACK_BASELINE"
            or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)
            or sha == candidate_sha
            or not isinstance(data.get("api_image"), str)
            or not re.fullmatch(r"ghcr\.io/tommylin15/janus-api@sha256:[0-9a-f]{64}",
                                data["api_image"])
            or data.get("private_historical_config_parity") != "NOT_VERIFIED"
            or data.get("old_ar_rollback_exercised") is not False):
        raise ValueError("approved_ghcr_baseline_missing")
    command(["git", "merge-base", "--is-ancestor", sha, candidate_sha])
    return data


def verify_previous_ghcr_rollback(baseline, previous_source_sha):
    """Require an actual public GHCR previous image before any traffic write.

    A historical AR reference is insufficient. The previous revision must be
    Ready and the digest and source SHA must match an anonymous registry read.
    """
    old_revision = active(baseline)
    revision = json.loads(command(["gcloud", "run", "revisions", "describe",
                    old_revision, f"--project={PROJECT}", f"--region={REGION}",
                    "--format=json"]))
    current_image = revision_image(revision)
    if not re.fullmatch(r"ghcr\.io/tommylin15/janus-api@sha256:[0-9a-f]{64}", current_image):
        raise ValueError("previous_ghcr_rollback_image_required")
    conditions = revision.get("status", {}).get("conditions", [])
    if not any(c.get("type") == "Ready" and c.get("status") == "True" for c in conditions):
        raise ValueError("previous_ghcr_revision_not_ready")
    manifest = json.loads(command(["skopeo", "inspect", "--no-creds", "docker://" + current_image]))
    if (manifest.get("Digest") != current_image.rsplit("@", 1)[-1]
            or manifest.get("Labels", {}).get("org.opencontainers.image.revision") != previous_source_sha):
        raise ValueError("previous_ghcr_registry_source_unverified")
    return current_image


def switch(revision, baseline):
    command(LEASE + ["assert"])
    command(["gcloud", "run", "services", "update-traffic", SERVICE, f"--project={PROJECT}",
             f"--region={REGION}", f"--to-revisions={revision}=100", "--quiet"])
    current = describe()
    if active(current) != revision or tags(current) != tags(baseline):
        raise ValueError("traffic_readback_mismatch")
    if not any(c.get("type") == "Ready" and c.get("status") == "True" for c in current["status"]["conditions"]):
        raise ValueError("service_not_ready")


def health(sha):
    for path in ("/health", "/api/v1/public/health"):
        if request(BASE + path)[0] != 200:
            raise ValueError("active_health_failed")
    status, _, body = request(BASE + "/app/build-id.txt")
    if status != 200 or body.decode().strip() != sha:
        raise ValueError("active_sha_mismatch")
    if request(BASE + "/api/v1/me/profile")[0] != 401:
        raise ValueError("active_auth_boundary_failed")


def check_jobs_receipt(proof, source_sha):
    if proof.get("source_sha") != source_sha:
        raise ValueError("jobs_receipt_not_matching_release")
    if proof.get("phase") == "PASS":
        snapshots = proof.get("snapshots")
        if not isinstance(snapshots, dict) or set(snapshots) != set(REQUIRED_JOBS):
            raise ValueError("jobs_snapshot_coverage_incomplete")
        for snapshot in snapshots.values():
            if not isinstance(snapshot, dict) or not snapshot.get("image") or not snapshot.get("configuration_hash"):
                raise ValueError("jobs_snapshot_incomplete")
    elif proof.get("phase") == "FORWARD_ONLY_PASS_WITH_PRIVATE_CONFIG_UNVERIFIED":
        if (proof.get("mode") != "user_authorized_forward_only_owner_recovery"
                or proof.get("scheduler_resumed") is not True
                or proof.get("original_private_full_config_verified") is not False
                or proof.get("old_ar_image_rollback_exercised") is not False
                or proof.get("job_images") != {name: "GHCR" for name, _ in JOB_COMPONENT}):
            raise ValueError("forward_jobs_receipt_not_accepted")
    else:
        raise ValueError("jobs_receipt_not_matching_release")
    rows = proof.get("canaries")
    expected = Counter({name: 2 for name, _ in JOB_COMPONENT})
    if not isinstance(rows, list) or len(rows) != sum(expected.values()):
        raise ValueError("jobs_canary_coverage_incomplete")
    if any(not isinstance(row, dict) or row.get("result") != "PASS"
           or not isinstance(row.get("execution"), str) or not row["execution"] for row in rows):
        raise ValueError("jobs_canary_evidence_invalid")
    if Counter(row["job"] for row in rows) != expected:
        raise ValueError("jobs_canary_coverage_incomplete")
    if len({row["execution"] for row in rows}) != len(rows):
        raise ValueError("jobs_canary_execution_duplicated")


def check_forward_promotion_request(release_run, jobs_run, sha):
    """Explicit, bounded forward-only Jobs acceptance: never claim private config parity."""
    data = json.loads(Path("ops/ghcr-api-forward-promote-request.json").read_text())
    if (data.get("intent") != "promote-existing-dev-ghcr-api-after-forward-jobs"
            or data.get("approved") is not True
            or data.get("scope") != "existing-dev-janus-api-only"
            or data.get("source_sha") != sha
            or data.get("release_run") != release_run
            or data.get("jobs_run") != jobs_run
            or data.get("private_config_parity") != "NOT_VERIFIED"):
        raise ValueError("forward_api_request_unapproved")
    images = data.get("job_images")
    if not isinstance(images, dict) or set(images) != {name for name, _ in JOB_COMPONENT}:
        raise ValueError("forward_job_images_missing")
    for name, component in JOB_COMPONENT:
        expected = images[name]
        if not isinstance(expected, str) or not re.fullmatch(
                rf"ghcr\.io/tommylin15/janus-{component}@sha256:[0-9a-f]{{64}}", expected):
            raise ValueError("forward_job_image_invalid")
    if data.get("research_image") != (
            "us-central1-docker.pkg.dev/gen-lang-client-0593591102/"
            "janusai-poc/research-cloud-cohort-500@sha256:"
            "7320443730ff487315211710612216e044cd453388622fc852d3cdd081201f59"):
        raise ValueError("research_baseline_changed")
    return data


def verify_forward_runtime(data):
    """API traffic cannot change when current GHCR jobs/scheduled ingestion are unsafe."""
    jobs.legacy_writers()
    if jobs.scheduler()["state"] != "ENABLED":
        raise ValueError("scheduler_not_enabled_for_api_promotion")
    jobs.fence()
    for name, image in data["job_images"].items():
        if jobs.image(jobs.job(name)) != image:
            raise ValueError("forward_job_digest_live_mismatch")
    if jobs.image(jobs.job("janus-research-big-move-500")) != data["research_image"]:
        raise ValueError("protected_research_job_drift")


def promote(release_run, jobs_run, receipt, forward_recovery=False):
    sha = json.loads(Path("ops/ghcr-candidate-request.json").read_text())["sha"]
    def checkpoint(name):
        receipt.write_text(json.dumps({
            "source_sha": sha, "phase": "PREFLIGHT", "stage": name,
            "gcp_traffic_write": False}))
    checkpoint("owner_acceptance")
    acceptance(sha)
    checkpoint("bounded_request")
    if forward_recovery:
        forward_request = check_forward_promotion_request(release_run, jobs_run, sha)
    else:
        approved_baseline = approved_previous_baseline(sha)
    checkpoint("run_provenance")
    for run, expected in ((release_run, "Janus GHCR full-test image publication"),
                          (jobs_run, ("Janus fenced forward-only GHCR Jobs recovery"
                                      if forward_recovery else "Janus GHCR controlled Jobs rollout"))):
        metadata = json.loads(command(["gh", "run", "view", run, "--json", "headSha,conclusion,status,workflowName"]))
        if metadata.get("status") != "completed" or metadata.get("conclusion") != "success" or metadata.get("workflowName") != expected:
            raise ValueError("release_or_jobs_gate_incomplete")
        if run == release_run and metadata.get("headSha") != sha:
            raise ValueError("release_sha_mismatch")
    checkpoint("jobs_receipt")
    jobs_receipt = json.loads(Path("/tmp/ghcr-jobs-proof/ghcr-jobs-rollout.json").read_text())
    check_jobs_receipt(jobs_receipt, sha)
    if forward_recovery:
        if jobs_receipt.get("phase") != "FORWARD_ONLY_PASS_WITH_PRIVATE_CONFIG_UNVERIFIED":
            raise ValueError("wrong_forward_jobs_receipt")
        checkpoint("live_jobs_scheduler_fence")
        verify_forward_runtime(forward_request)
    elif jobs_receipt.get("phase") != "PASS":
        raise ValueError("wrong_regular_jobs_receipt")
    checkpoint("previous_release_ancestry")
    if Path("ops/ghcr-last-success.json").exists():
        previous = json.loads(Path("ops/ghcr-last-success.json").read_text())
        if previous.get("result") == "PASS":
            command(["git", "merge-base", "--is-ancestor", previous["source_sha"], sha])
    checkpoint("lease_acquire")
    command(LEASE + ["acquire"])
    baseline, old_sha, safe, mutated = None, None, False, False
    journal = {"source_sha": sha, "phase": "PREFLIGHT", "stage": "service_preflight"}
    try:
        journal["stage"] = "service_baseline_readback"
        receipt.write_text(json.dumps(journal))
        baseline = describe()
        journal["stage"] = "candidate_tag_lookup"
        receipt.write_text(json.dumps(journal))
        candidate_tag = "ghcr-" + sha[:12]
        candidate = tags(baseline)[candidate_tag]
        previous_revision = active(baseline)
        journal["stage"] = "previous_service_build_id"
        receipt.write_text(json.dumps(journal))
        status, _, body = request(BASE + "/app/build-id.txt")
        old_sha = body.decode().strip()
        if status != 200 or not re.fullmatch(r"[0-9a-f]{40}", old_sha):
            raise ValueError("previous_sha_unknown")
        if not forward_recovery and previous_revision != candidate:
            journal["stage"] = "verified_public_previous_ghcr_rollback"
            receipt.write_text(json.dumps(journal))
            if old_sha != approved_baseline["source_sha"]:
                raise ValueError("previous_release_source_not_approved_baseline")
            old_image = verify_previous_ghcr_rollback(baseline, old_sha)
            if old_image != approved_baseline["api_image"]:
                raise ValueError("previous_release_digest_not_approved_baseline")
            journal["previous_ghcr_image"] = old_image
            health(old_sha)
        journal["stage"] = "candidate_revision_image"
        receipt.write_text(json.dumps(journal))
        revision = json.loads(command(["gcloud", "run", "revisions", "describe", candidate,
            f"--project={PROJECT}", f"--region={REGION}", "--format=json"]))
        image = revision_image(revision)
        if not re.fullmatch(r"ghcr\.io/tommylin15/janus-api@sha256:[0-9a-f]{64}", image):
            raise ValueError("candidate_digest_unknown")
        journal.update(previous_revision=previous_revision, previous_sha=old_sha, candidate=candidate, image=image,
                       tags=tags(baseline), phase="PREPARED")
        receipt.write_text(json.dumps(journal))
        journal["stage"] = "candidate_probe"
        receipt.write_text(json.dumps(journal))
        probe("https://" + candidate_tag + "---" + BASE.removeprefix("https://"), sha)
        if previous_revision == candidate:
            health(sha)
            journal["phase"] = "PASS_IDEMPOTENT"
        else:
            journal["stage"] = "switch_candidate_first"
            receipt.write_text(json.dumps(journal))
            mutated = True
            switch(candidate, baseline)
            health(sha)
            journal["stage"] = "switch_back_to_previous"
            receipt.write_text(json.dumps(journal))
            switch(previous_revision, baseline)
            health(old_sha)
            journal["rollback_rehearsal"] = "PASS"
            journal["stage"] = "promote_candidate_final"
            receipt.write_text(json.dumps(journal))
            switch(candidate, baseline)
            health(sha)
            journal["phase"] = "PASS"
        receipt.write_text(json.dumps(journal))
        safe = True
    except Exception as error:
        journal["error_type"] = type(error).__name__
        receipt.write_text(json.dumps(journal))
        if mutated and baseline is not None:
            switch(active(baseline), baseline)
            health(old_sha)
            journal["phase"] = "RESTORED"
            receipt.write_text(json.dumps(journal))
            safe = True
        elif baseline is not None and active(describe()) == active(baseline):
            safe = True
        raise
    finally:
        if safe:
            command(LEASE + ["release", "--safe-to-release"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-run", required=True)
    parser.add_argument("--jobs-run", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--forward-recovery", action="store_true")
    args = parser.parse_args()
    try:
        if not all(re.fullmatch(r"[0-9]+", run) for run in (args.release_run, args.jobs_run)):
            raise ValueError("invalid_run_identity")
        promote(args.release_run, args.jobs_run, args.receipt, forward_recovery=args.forward_recovery)
        print(json.dumps({"result": "PASS"}))
        return 0
    except Exception as error:
        reason = str(error) if re.fullmatch(r"[a-z][a-z0-9_]{3,100}", str(error)) else "control_failure"
        print(json.dumps({"result": "BLOCKED_OR_FAILED", "reason": reason}))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
