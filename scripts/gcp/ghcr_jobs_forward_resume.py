#!/usr/bin/env python3
"""One-time verified recovery of a forward-only GHCR Job rollout.

The original run is finished but its Git tag lease remains held. No stolen or
force-replaced tag, no old AR-image rollback, no Scheduler resume on partial
success, and no publishing without eight independent read-only canaries.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import ghcr_jobs_rollout as rollout


REQUEST = Path("ops/ghcr-jobs-forward-resume-request.json")
RECOVERING_JOB = "janus-private-pipeline"
GHCR_SHA = "fbcc5f58a2fa31f2f36dc4c82702fb62910c7361"


def contract(job):
    """Fields whose runtime semantics must remain identical across image updates."""
    outer = job["template"]
    inner = outer["template"]
    containers = inner["containers"]
    if len(containers) != 1:
        raise ValueError("runtime_container_count_drift")
    container = containers[0]
    return {
        "task_count": outer.get("taskCount"),
        "parallelism": outer.get("parallelism"),
        "execution_labels": outer.get("labels"),
        "execution_annotations": outer.get("annotations"),
        "task": {k: inner.get(k) for k in (
            "serviceAccount", "timeout", "maxRetries", "vpcAccess",
            "volumes", "executionEnvironment", "encryptionKey")},
        "container": {k: container.get(k) for k in (
            "name", "command", "args", "env", "resources", "volumeMounts",
            "ports", "startupProbe", "workingDir", "dependsOn")},
    }


def assert_contract(before, after):
    if contract(before) != contract(after):
        raise ValueError("runtime_contract_drift")


def request_data():
    data = json.loads(REQUEST.read_text())
    if (data.get("intent") != "resume-stalled-forward-only-ghcr-jobs"
            or data.get("approved") is not True
            or data.get("project") != rollout.PROJECT
            or data.get("region") != rollout.REGION
            or data.get("source_sha") != GHCR_SHA
            or data.get("failed_run") != "37913564122"
            or data.get("failed_run_sha") != "2b4607481e41e2789a6c05aee0e085272e244a5e"
            or data.get("failed_attempt") != 1
            or data.get("keep_scheduler_paused_on_partial") is not True):
        raise ValueError("recovery_request_invalid")
    h = data.get("original_job_hashes")
    if not isinstance(h, dict) or set(h) != set(rollout.REQUIRED_JOBS):
        raise ValueError("recovery_original_hashes_missing")
    if not all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
               for v in h.values()):
        raise ValueError("recovery_original_hash_invalid")
    return data


def owner_lease(request):
    # Recorded owner is no longer executing. The old run must be an actual
    # completed failure, not a still-active or unrelated workflow.
    run = json.loads(rollout.command(
        ["gh", "run", "view", request["failed_run"],
         "--json", "headSha,status,conclusion,workflowName"]))
    if (run.get("headSha") != request["failed_run_sha"]
            or run.get("status") != "completed"
            or run.get("conclusion") != "failure"
            or run.get("workflowName") != "Janus GHCR controlled Jobs rollout"):
        raise ValueError("original_lease_owner_not_finished")
    rollout.LEASE = rollout.LEASE + [
        "--run-id", request["failed_run"],
        "--run-attempt", str(request["failed_attempt"]),
        "--sha", request["failed_run_sha"]]
    rollout.command(rollout.LEASE + ["assert"])


def get_targets(request):
    release = json.loads(rollout.command(
        ["gh", "run", "view", "37876247130",
         "--json", "headSha,status,conclusion,workflowName"]))
    if (release.get("headSha") != GHCR_SHA or release.get("conclusion") != "success"
            or release.get("workflowName") != "Janus GHCR full-test image publication"):
        raise ValueError("release_provenance_invalid")
    targets = {}
    for name, component in rollout.JOB_COMPONENT:
        manifest = json.loads(rollout.command(
            ["skopeo", "inspect", "--no-creds",
             f"docker://ghcr.io/tommylin15/janus-{component}:sha-{GHCR_SHA}"]))
        if manifest.get("Labels", {}).get("org.opencontainers.image.revision") != GHCR_SHA:
            raise ValueError("ghcr_source_label_invalid")
        target = f"ghcr.io/tommylin15/janus-{component}@{manifest['Digest']}"
        if not rollout.PIN.fullmatch(target):
            raise ValueError("ghcr_digest_invalid")
        rollout.command(["skopeo", "inspect", "--no-creds", "docker://" + target])
        targets[name] = target
    return targets


def image_only_update(name, target, before, save):
    rollout.writers()
    if rollout.scheduler()["state"] != "PAUSED":
        raise ValueError("scheduler_no_longer_paused")
    rollout.fence()
    if rollout.image(rollout.job(name)) != rollout.image(before):
        raise ValueError("job_changed_during_recovery")
    argv = ["gcloud", "run", "jobs", "update", name,
            f"--project={rollout.PROJECT}", f"--region={rollout.REGION}",
            "--image=" + target, "--quiet"]
    result = subprocess.run(argv, capture_output=True, text=True,
                            check=False, timeout=300)
    if result.returncode:
        raise RuntimeError("bounded_image_update_failed")
    after = rollout.job(name)
    if rollout.image(after) != target:
        raise ValueError("ghcr_image_readback_failed")
    assert_contract(before, after)
    save()
    return after


def run(receipt):
    output = {"mode": "user_authorized_forward_only_owner_recovery",
              "source_sha": GHCR_SHA, "phase": "PREFLIGHT",
              "job_images": {}, "canaries": [], "operations": [],
              "original_private_full_config_verified": False,
              "old_ar_image_rollback_exercised": False,
              "scheduler_resumed": False}
    def save():
        receipt.write_text(json.dumps(output, sort_keys=True) + "\n")
    save()
    try:
        req = request_data()
        rollout.acceptance(GHCR_SHA)
        owner_lease(req)
        rollout.legacy_writers()
        rollout.job_update_permissions()
        if rollout.scheduler()["state"] != "PAUSED":
            raise ValueError("scheduler_not_fenced")
        if rollout.scheduler_fingerprint(rollout.scheduler()) != req["scheduler_hash"]:
            raise ValueError("scheduler_drift")
        rollout.fence()
        targets = get_targets(req)
        before = {name: rollout.job(name) for name in rollout.REQUIRED_JOBS}
        for name in rollout.REQUIRED_JOBS:
            if name == RECOVERING_JOB:
                if rollout.image(before[name]) != targets[name]:
                    raise ValueError("private_ghcr_partial_image_missing")
            elif rollout.fingerprint(before[name]) != req["original_job_hashes"][name]:
                raise ValueError("unmodified_job_baseline_drift")
        output["phase"] = "FIRST_CANARIES"
        save()
        for name, _ in rollout.JOB_COMPONENT:
            current = rollout.job(name)
            if name == RECOVERING_JOB:
                # The original gcloud update changed multiple config fields;
                # its original full fingerprint cannot be reconstructed. A
                # live isolated canary is required, and the uncertainty is
                # recorded rather than represented as full parity.
                after = current
            else:
                if rollout.image(current) != rollout.image(before[name]):
                    raise ValueError("unexpected_job_image_before_update")
                after = image_only_update(name, targets[name], current, save)
            output["job_images"][name] = "GHCR"
            save()
            rollout.canary(name, targets[name], rollout.fingerprint(after), output, save)
        output["phase"] = "SECOND_CANARIES"
        save()
        for name, _ in rollout.JOB_COMPONENT:
            current = rollout.job(name)
            rollout.canary(name, targets[name], rollout.fingerprint(current), output, save)
        output["phase"] = "FINAL_READBACK"
        save()
        rollout.fence()
        for name, _ in rollout.JOB_COMPONENT:
            current = rollout.job(name)
            if rollout.image(current) != targets[name]:
                raise ValueError("ghcr_target_image_mismatch")
        research = "janus-research-big-move-500"
        if rollout.fingerprint(rollout.job(research)) != req["original_job_hashes"][research]:
            raise ValueError("protected_research_job_drift")
        successful = [c for c in output["canaries"] if c["result"] == "PASS"]
        if len(successful) != 8 or any(
            sum(c["job"] == name for c in successful) != 2 for name, _ in rollout.JOB_COMPONENT):
            raise ValueError("canary_counts_incomplete")
        if rollout.scheduler_fingerprint(rollout.scheduler()) != req["scheduler_hash"]:
            raise ValueError("scheduler_configuration_drift")
        rollout.set_scheduler("resume", "ENABLED")
        output["scheduler_resumed"] = True
        save()
        rollout.command(rollout.LEASE + ["release", "--safe-to-release"])
        output["phase"] = "FORWARD_ONLY_PASS_WITH_PRIVATE_CONFIG_UNVERIFIED"
        save()
        return 0
    except Exception as error:
        output["phase"] = "RECOVERY_REQUIRED"
        reason = str(error)
        output["reason"] = (reason if re.fullmatch(r"[a-z][a-z0-9_]{3,110}", reason)
                            else "control_failure")
        save()
        return 78


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    return run(parser.parse_args().receipt)


if __name__ == "__main__":
    sys.exit(main())
