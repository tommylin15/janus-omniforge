#!/usr/bin/env python3
"""Promote only an accepted existing dev candidate, rehearse and verify rollback."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from ghcr_jobs_rollout import acceptance
from ghcr_mcp_route import BASE, PROJECT, REGION, SERVICE, LEASE, command, describe, request, probe


def active(data):
    rows = [(row["revisionName"], row["percent"]) for row in data["status"]["traffic"]
            if row.get("percent", 0) > 0]
    if len(rows) != 1 or rows[0][1] != 100:
        raise ValueError("single_active_revision_required")
    return rows[0][0]


def tags(data):
    return {row["tag"]: row["revisionName"] for row in data["status"]["traffic"] if row.get("tag")}


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


def promote(release_run, jobs_run, receipt):
    sha = json.loads(Path("ops/ghcr-candidate-request.json").read_text())["sha"]
    acceptance(sha)
    for run, expected in ((release_run, "Janus GHCR full-test image publication"),
                          (jobs_run, "Janus GHCR controlled Jobs rollout")):
        metadata = json.loads(command(["gh", "run", "view", run, "--json", "headSha,conclusion,status,workflowName"]))
        if metadata.get("status") != "completed" or metadata.get("conclusion") != "success" or metadata.get("workflowName") != expected:
            raise ValueError("release_or_jobs_gate_incomplete")
        if run == release_run and metadata.get("headSha") != sha:
            raise ValueError("release_sha_mismatch")
    jobs_receipt = json.loads(Path("/tmp/ghcr-jobs-proof/ghcr-jobs-rollout.json").read_text())
    if jobs_receipt.get("source_sha") != sha or jobs_receipt.get("phase") != "PASS" or len(jobs_receipt.get("canaries", [])) != 8:
        raise ValueError("jobs_receipt_not_matching_release")
    if Path("ops/ghcr-last-success.json").exists():
        previous = json.loads(Path("ops/ghcr-last-success.json").read_text())
        if previous.get("result") == "PASS":
            command(["git", "merge-base", "--is-ancestor", previous["source_sha"], sha])
    command(LEASE + ["acquire"])
    baseline, old_sha, safe, mutated = None, None, False, False
    journal = {"source_sha": sha, "phase": "PREFLIGHT"}
    try:
        baseline = describe()
        candidate_tag = "ghcr-" + sha[:12]
        candidate = tags(baseline)[candidate_tag]
        previous_revision = active(baseline)
        status, _, body = request(BASE + "/app/build-id.txt")
        old_sha = body.decode().strip()
        if status != 200 or not re.fullmatch(r"[0-9a-f]{40}", old_sha):
            raise ValueError("previous_sha_unknown")
        revision = json.loads(command(["gcloud", "run", "revisions", "describe", candidate,
            f"--project={PROJECT}", f"--region={REGION}", "--format=json(spec.containers.image,status.conditions)"]))
        image = revision["spec"]["containers"][0]["image"].removeprefix("cache.us-docker.pkg.dev/")
        if not re.fullmatch(r"ghcr\.io/tommylin15/janus-api@sha256:[0-9a-f]{64}", image):
            raise ValueError("candidate_digest_unknown")
        journal.update(previous_revision=previous_revision, previous_sha=old_sha, candidate=candidate, image=image,
                       tags=tags(baseline), phase="PREPARED")
        receipt.write_text(json.dumps(journal))
        probe("https://" + candidate_tag + "---" + BASE.removeprefix("https://"), sha)
        if previous_revision == candidate:
            health(sha)
            journal["phase"] = "PASS_IDEMPOTENT"
        else:
            mutated = True
            switch(candidate, baseline)
            health(sha)
            switch(previous_revision, baseline)
            health(old_sha)
            journal["rollback_rehearsal"] = "PASS"
            receipt.write_text(json.dumps(journal))
            switch(candidate, baseline)
            health(sha)
            journal["phase"] = "PASS"
        receipt.write_text(json.dumps(journal))
        safe = True
    except Exception:
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
    args = parser.parse_args()
    try:
        if not all(re.fullmatch(r"[0-9]+", run) for run in (args.release_run, args.jobs_run)):
            raise ValueError("invalid_run_identity")
        promote(args.release_run, args.jobs_run, args.receipt)
        print(json.dumps({"result": "PASS"}))
        return 0
    except Exception as error:
        reason = str(error) if re.fullmatch(r"[a-z][a-z0-9_]{3,100}", str(error)) else "control_failure"
        print(json.dumps({"result": "BLOCKED_OR_FAILED", "reason": reason}))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
