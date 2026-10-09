#!/usr/bin/env python3
"""Read-only live Jobs release diagnostics. No scheduler/job/traffic writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import ghcr_jobs_rollout as rollout


def check(label, action, findings):
    try:
        action()
    except (Exception, SystemExit) as error:
        # Never emit an HTTP body, credential, command, env var or private payload.
        findings[label] = {"status": "BLOCKED", "error_type": type(error).__name__}
    else:
        findings[label] = {"status": "PASS"}


def assert_baseline_scheduler():
    state = rollout.scheduler().get("state")
    if state != "ENABLED":
        raise ValueError("unexpected_scheduler_baseline")


def jobs_ready_readback():
    for name in rollout.REQUIRED_JOBS:
        rollout.job(name)


def scan():
    findings = {}
    check("legacy_cloud_build_not_competing", rollout.legacy_writers, findings)
    check("scheduler_expected_enabled_baseline", assert_baseline_scheduler, findings)
    check("five_jobs_readable_and_ready", jobs_ready_readback, findings)
    check("five_jobs_executions_terminal", rollout.fence, findings)
    check("jobs_update_and_canary_iam", rollout.job_update_permissions, findings)
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
