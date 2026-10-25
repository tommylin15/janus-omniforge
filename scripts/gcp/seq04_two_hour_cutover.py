#!/usr/bin/env python3
"""SEQ-04: modify only the existing dev controller Scheduler with fenced rollback."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import ghcr_api_promote as api
import ghcr_jobs_rollout as jobs
from ghcr_mcp_route import LEASE

REQUEST = Path("ops/seq04-two-hour-cutover-request.json")
OLD = "30 * * * *"
NEW = "30 */2 * * *"
SHA = re.compile(r"^[0-9a-f]{40}$")


def checked_request():
    value = json.loads(REQUEST.read_text())
    if (value.get("intent") != "seq04-existing-dev-two-hour-controller-cutover"
            or value.get("approved") is not True
            or value.get("project") != "gen-lang-client-0593591102"
            or value.get("location") != "us-central1"
            or value.get("scheduler") != "janus-ingestion-daily"
            or value.get("old_cron") != OLD or value.get("new_cron") != NEW
            or value.get("time_zone") != "Asia/Taipei"
            or value.get("no_new_resources") is not True
            or not isinstance(value.get("source_sha"), str)
            or SHA.fullmatch(value["source_sha"]) is None
            or not isinstance(value.get("job_images"), dict)
            or set(value["job_images"]) != {name for name, _ in jobs.JOB_COMPONENT}
            or not all(jobs.PIN.fullmatch(image) for image in value["job_images"].values())):
        raise ValueError("seq04_request_not_authorized")
    for kind, op in (("release_run", "release"), ("jobs_run", "jobs-rollout"),
                     ("api_promotion_run", "promote")):
        run_id = value.get(kind)
        if not isinstance(run_id, str) or not re.fullmatch(r"[0-9]+", run_id):
            raise ValueError("seq04_run_id_invalid")
        meta = json.loads(jobs.command(
            ["gh", "run", "view", run_id, "--json",
             "headSha,status,conclusion,workflowName"]))
        if not jobs.successful_operation(
                meta, run_id,
                {"release": "Janus GHCR full-test image publication",
                 "jobs-rollout": "Janus GHCR controlled Jobs rollout",
                 "promote": "Janus GHCR controlled API promotion"}[op], op):
            raise ValueError("seq04_upstream_gate_unverified")
        if kind == "release_run" and meta["headSha"] != value["source_sha"]:
            raise ValueError("seq04_release_source_mismatch")
    return value


def invariant(before, after):
    keys = ("name", "timeZone", "httpTarget", "retryConfig",
            "attemptDeadline", "description")
    return (all(before.get(key) == after.get(key) for key in keys)
            and after.get("timeZone") == "Asia/Taipei"
            and after.get("name") ==
                "projects/gen-lang-client-0593591102/locations/us-central1/jobs/janus-ingestion-daily")


def change_schedule(cron):
    # Preserve stdout/stderr in memory; expose ONLY a closed error classification.
    # The actual GCloud error might include a resource URL or sensitive payload.
    args = ["gcloud", "scheduler", "jobs", "update", "http",
            "janus-ingestion-daily", "--project=gen-lang-client-0593591102",
            "--location=us-central1", f"--schedule={cron}",
            "--time-zone=Asia/Taipei", "--quiet"]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120,
                            check=False)
    if result.returncode:
        message = result.stderr.lower()
        category = (
            "permission_denied" if ("permission_denied" in message
                                   or "permission denied" in message
                                   or "does not have permission" in message
                                   or "403" in message)
            else "invalid_argument" if ("invalid_argument" in message
                                         or "invalid value" in message
                                         or "400" in message)
            else "cli_argument" if ("unrecognized arguments" in message
                                    or "unrecognized argument" in message)
            else "not_found" if ("not_found" in message
                                 or "not found" in message
                                 or "404" in message)
            else "unknown")
        raise ValueError("seq04_scheduler_update_" + category)


def run(receipt):
    proof = {"phase": "PREFLIGHT", "gcp_new_resources": 0,
             "scheduler_name": "janus-ingestion-daily", "writes": 0}
    def save():
        receipt.write_text(json.dumps(proof, sort_keys=True) + "\n")
    save()
    held = False
    paused = False
    original = None
    try:
        req = checked_request()
        proof["source_sha"] = req["source_sha"]
        live = api.describe()
        if api.active(live) != api.tags(live).get(
                "ghcr-" + req["source_sha"][:12]):
            raise ValueError("seq04_live_api_not_promoted")
        api.health(req["source_sha"])
        jobs.legacy_writers()
        for name, _ in jobs.JOB_COMPONENT:
            current = jobs.job(name)
            if jobs.image(current) != req["job_images"][name]:
                raise ValueError("seq04_live_job_digest_drift")
        original = jobs.scheduler()
        if original.get("state") != "ENABLED" or original.get("schedule") not in (OLD, NEW):
            raise ValueError("seq04_scheduler_baseline_invalid")
        proof["previous_cron"] = original["schedule"]
        proof["target_sha256"] = hashlib.sha256(
            json.dumps(original.get("httpTarget"), sort_keys=True).encode()).hexdigest()
        if original["schedule"] == NEW:
            proof["phase"] = "PASS_ALREADY_CUT_OVER"
            proof["new_cron"] = NEW
            save()
            return 0
        jobs.command(LEASE + ["acquire"])
        held = True
        jobs.command(LEASE + ["assert"])
        locked = jobs.scheduler()
        if (locked.get("state") != "ENABLED" or locked.get("schedule") != OLD
                or not invariant(original, locked)):
            raise ValueError("seq04_scheduler_changed_before_pause")
        jobs.wait_for_terminal_executions(timeout=600)
        proof["phase"] = "PAUSE_INTENT"
        save()
        paused = True  # Unknown pause outcomes must enter recovery, not blind retry.
        jobs.set_scheduler("pause", "PAUSED")
        jobs.wait_for_terminal_executions(timeout=600)
        jobs.command(LEASE + ["assert"])
        proof["phase"] = "CRON_CHANGE_INTENT"
        save()
        change_schedule(NEW)
        changed = jobs.scheduler()
        if (changed.get("schedule") != NEW or changed.get("state") != "PAUSED"
                or not invariant(original, changed)):
            raise ValueError("seq04_new_cron_or_target_readback_mismatch")
        jobs.command(LEASE + ["assert"])
        jobs.set_scheduler("resume", "ENABLED")
        final = jobs.scheduler()
        if (final.get("schedule") != NEW or final.get("state") != "ENABLED"
                or not invariant(original, final)):
            raise ValueError("seq04_final_scheduler_readback_mismatch")
        paused = False
        proof.update(phase="PASS", new_cron=NEW, scheduler_enabled=True,
                     target_identity_unchanged=True, writes=3)
        save()
        jobs.command(LEASE + ["release", "--safe-to-release"])
        return 0
    except Exception as error:
        proof["phase"] = "RECOVERY_REQUIRED"
        # Only a finite code-owned reason leaves the runner; never echo raw credentials.
        reason = str(error)
        proof["reason"] = reason if re.fullmatch(r"[a-z][a-z0-9_]{3,90}", reason) else "bounded_control_failure"
        save()
        if held:
            try:
                current = jobs.scheduler()
                if not original or not invariant(original, current):
                    raise ValueError("seq04_rollback_identity_drift")
                if current.get("schedule") != OLD:
                    if current.get("state") != "PAUSED":
                        jobs.set_scheduler("pause", "PAUSED")
                    change_schedule(OLD)
                current = jobs.scheduler()
                if not invariant(original, current) or current.get("schedule") != OLD:
                    raise ValueError("seq04_rollback_cron_unverified")
                if current.get("state") == "PAUSED":
                    jobs.set_scheduler("resume", "ENABLED")
                final = jobs.scheduler()
                if (final.get("schedule") != OLD or final.get("state") != "ENABLED"
                        or not invariant(original, final)):
                    raise ValueError("seq04_rollback_readback_failed")
                proof.update(phase="ROLLED_BACK", restored_cron=OLD,
                             scheduler_enabled=True)
                save()
                jobs.command(LEASE + ["release", "--safe-to-release"])
            except Exception:
                proof["phase"] = "BLOCKED_LEASE_RETAINED"
                save()
        return 78


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    return run(parser.parse_args().receipt)


if __name__ == "__main__":
    raise SystemExit(main())
