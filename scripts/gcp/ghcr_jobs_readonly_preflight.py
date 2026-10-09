#!/usr/bin/env python3
"""Read-only live Jobs release diagnostics. No scheduler/job/traffic writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import ghcr_jobs_rollout as rollout


class RollbackImageBlocked(RuntimeError):
    def __init__(self, reason_code, job):
        self.reason_code = reason_code
        self.job = job
        super().__init__(reason_code)


def check(label, action, findings):
    try:
        action()
    except (Exception, SystemExit) as error:
        # Never emit an HTTP body, credential, command, env var or private payload.
        findings[label] = {"status": "BLOCKED", "error_type": type(error).__name__}
        if isinstance(error, RollbackImageBlocked):
            findings[label]["reason_code"] = error.reason_code
            findings[label]["job"] = error.job
    else:
        findings[label] = {"status": "PASS"}


def assert_baseline_scheduler():
    state = rollout.scheduler().get("state")
    if state != "ENABLED":
        raise ValueError("unexpected_scheduler_baseline")


def jobs_ready_readback():
    for name in rollout.REQUIRED_JOBS:
        rollout.job(name)


def rollback_images_readable():
    """Check all existing immutable rollback refs without updating or pulling Jobs."""
    for name in rollout.REQUIRED_JOBS:
        target = rollout.image(rollout.job(name))
        if not rollout.PIN.fullmatch(target):
            raise RollbackImageBlocked("ROLLBACK_IMAGE_NOT_PINNED", name)
        if target.startswith("ghcr.io/"):
            cmd = ["skopeo", "inspect", "--no-creds", "docker://" + target]
        else:
            cmd = ["gcloud", "artifacts", "docker", "images", "describe", target,
                   "--format=value(image_summary.digest)"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45, check=False)
        if result.returncode:
            # Classify the failure; never disclose registry response bodies or URLs.
            low = result.stderr.lower()
            if "permission_denied" in low or "permission denied" in low or "403" in low:
                code = "ROLLBACK_IMAGE_READ_IAM"
            elif "not found" in low or "not_found" in low or "404" in low:
                code = "ROLLBACK_IMAGE_NOT_FOUND"
            else:
                code = "ROLLBACK_IMAGE_READ_UNKNOWN"
            raise RollbackImageBlocked(code, name)
        if not result.stdout.strip():
            raise RollbackImageBlocked("ROLLBACK_IMAGE_NO_DIGEST_READBACK", name)


def scan():
    findings = {}
    check("legacy_cloud_build_not_competing", rollout.legacy_writers, findings)
    check("scheduler_expected_enabled_baseline", assert_baseline_scheduler, findings)
    check("five_jobs_readable_and_ready", jobs_ready_readback, findings)
    check("five_jobs_executions_terminal", rollout.fence, findings)
    check("jobs_update_and_canary_iam", rollout.job_update_permissions, findings)
    check("five_rollback_images_registry_readable", rollback_images_readable, findings)
    return {
        "mode": "read_only",
        "project": rollout.PROJECT,
        "region": rollout.REGION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "READONLY_PREFLIGHT_PASS"
                  if all(g["status"] == "PASS" for g in findings.values()) else "BLOCKED",
        "gcp_writes": 0,
        "does_not_validate": ["cross_writer_durable_mutex", "scheduler_pause_resume",
                              "canary_runtime", "job_rollout_and_rollback", "api_traffic_promotion"],
        "gates": findings,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = scan()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    # BLOCKED is an actual diagnostic finding; never a release approval.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
