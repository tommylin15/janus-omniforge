#!/usr/bin/env python3
"""Read-only verified GHCR rollback baseline for future Janus dev releases.

A healthy GHCR deployment is a *new* rollback source, not evidence that its
pre-GHCR Private Pipeline configuration or AR images can be restored.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys

import ghcr_api_promote as api
import ghcr_jobs_rollout as jobs
from ghcr_mcp_route import BASE, LEASE, PROJECT, REGION, SERVICE, command, describe, probe

REQUEST = Path("ops/ghcr-reversible-baseline-request.json")
PIN = re.compile(r"^ghcr\.io/tommylin15/janus-api@sha256:[0-9a-f]{64}$")


def validated_request():
    data = json.loads(REQUEST.read_text())
    if (data.get("intent") != "verify-existing-ghcr-release-baseline"
            or data.get("scope") != "existing-dev-read-only"
            or data.get("source_sha") != "fbcc5f58a2fa31f2f36dc4c82702fb62910c7361"
            or data.get("release_run") != "37876247130"
            or data.get("api_revision") != "janus-api-00451-cuw"
            or not isinstance(data.get("api_image"), str)
            or not PIN.fullmatch(data["api_image"])
            or data.get("no_gcp_mutation") is not True
            or data.get("prior_private_config_parity") != "NOT_VERIFIED"
            or data.get("old_ar_rollback_exercised") is not False):
        raise ValueError("baseline_request_invalid")
    jobs.release_rollback_mode({
        "rollback_mode": "reversible_ghcr",
        "accept_no_old_image_rollback": False,
        "baseline_source_sha": data["source_sha"],
        "rollback_images": data.get("job_images"),
        "rollback_config_hashes": data.get("job_config_hashes")}, "a" * 40)
    return data


def ready(service, revision, expected):
    status = service.get("status", {})
    meta = service.get("metadata", {})
    if (not str(meta.get("generation")).isdigit()
            or not str(status.get("observedGeneration")).isdigit()
            or int(meta["generation"]) != int(status["observedGeneration"])
            or status.get("latestReadyRevisionName") != expected):
        raise ValueError("baseline_service_not_reconciled")
    if (not isinstance(status.get("conditions"), list)
            or not any(x.get("type") == "Ready" and x.get("status") == "True"
                       for x in status["conditions"])
            or any(x.get("type") == "RoutesReady" and x.get("status") != "True"
                   for x in status["conditions"])):
        raise ValueError("baseline_service_not_ready")
    if not any(x.get("type") == "Ready" and x.get("status") == "True"
               for x in revision.get("status", {}).get("conditions", [])):
        raise ValueError("baseline_revision_not_ready")


def inspect(receipt: Path):
    evidence = {"status": "BLOCKED", "gcp_writes": 0, "phase": "PREFLIGHT",
                "private_historical_config_parity": "NOT_VERIFIED",
                "old_ar_rollback_exercised": False}
    def save():
        receipt.write_text(json.dumps(evidence, sort_keys=True))
    save()
    try:
        req = validated_request()
        sha = req["source_sha"]
        lease = json.loads(command(LEASE + ["inspect"]))
        if lease.get("status") != "ABSENT":
            raise ValueError("deployment_lease_present_or_unknown")
        run = json.loads(command(["gh", "run", "view", req["release_run"],
                                  "--json", "headSha,status,conclusion,workflowName"]))
        if (run.get("headSha") != sha or run.get("status") != "completed"
                or run.get("conclusion") != "success"
                or run.get("workflowName") != "Janus GHCR full-test image publication"):
            raise ValueError("baseline_source_release_unverified")
        jobs.legacy_writers()
        scheduler = jobs.scheduler()
        if scheduler.get("state") != "ENABLED":
            raise ValueError("baseline_scheduler_unhealthy")
        jobs.fence()
        current = describe()
        if (current.get("metadata", {}).get("name") != SERVICE
                or api.active(current) != req["api_revision"]
                or api.tags(current).get("ghcr-" + sha[:12]) != req["api_revision"]):
            raise ValueError("baseline_api_routing_mismatch")
        revision = json.loads(command(["gcloud", "run", "revisions", "describe",
                           req["api_revision"], f"--project={PROJECT}",
                           f"--region={REGION}", "--format=json"]))
        ready(current, revision, req["api_revision"])
        if api.revision_image(revision) != req["api_image"]:
            raise ValueError("baseline_api_image_drift")
        manifest = json.loads(command(["skopeo", "inspect", "--no-creds",
                                       "docker://" + req["api_image"]]))
        if (manifest.get("Digest") != req["api_image"].rsplit("@", 1)[-1]
                or manifest.get("Labels", {}).get("org.opencontainers.image.revision") != sha):
            raise ValueError("baseline_public_api_image_unverified")
        live = {name: jobs.job(name) for name in jobs.REQUIRED_JOBS}
        jobs.verify_reversible_baseline({
            "baseline_source_sha": sha,
            "rollback_images": req["job_images"],
            "rollback_config_hashes": req["job_config_hashes"]}, live)
        if jobs.image(live["janus-research-big-move-500"]) != req["research_image"]:
            raise ValueError("baseline_research_job_drift")
        api.health(sha)
        probe("https://ghcr-" + sha[:12] + "---" + BASE.removeprefix("https://"), sha)
        # A second readback prevents a successful probe being attached to drift.
        jobs.fence()
        if (jobs.scheduler()["state"] != "ENABLED"
                or api.active(describe()) != req["api_revision"]):
            raise ValueError("baseline_postcheck_drift")
        evidence.update({
            "status": "PASS", "phase": "VERIFIED_PUBLIC_GHCR_ROLLBACK_BASELINE",
            "source_sha": sha, "release_run": req["release_run"],
            "api_revision": req["api_revision"], "api_image": req["api_image"],
            "jobs": {name: {"image": jobs.image(live[name]),
                            "config_fingerprint": jobs.fingerprint(live[name])}
                     for name, _ in jobs.JOB_COMPONENT},
            "scheduler_enabled": True, "research_protected": True,
            "service_ready": True, "ready_for_future_reversible_release": True,
            "old_ar_rollback_exercised": False,
            "private_historical_config_parity": "NOT_VERIFIED"})
        save()
        return 0
    except Exception as error:
        text = str(error)
        evidence["reason"] = text if re.fullmatch(r"[a-z][a-z0-9_]{3,100}", text) else "control_failure"
        evidence["error_type"] = type(error).__name__
        save()
        return 78


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    return inspect(parser.parse_args().receipt)


if __name__ == "__main__":
    sys.exit(main())
