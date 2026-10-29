"""Controlled existing-dev pipeline acceptance under the shared deployment lease."""
import argparse
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import time
import ghcr_jobs_rollout as jobs
from ghcr_mcp_route import LEASE


def source_gate(release_run, jobs_run):
    for run, operation in ((release_run, "release"), (jobs_run, "jobs-rollout")):
        if not re.fullmatch(r"[0-9]+", run):
            raise ValueError("invalid_upstream_run")
        metadata = json.loads(jobs.command(["gh", "run", "view", run, "--json", "headSha,status,conclusion,workflowName"]))
        if not jobs.successful_operation(metadata, run, "", operation):
            raise ValueError("upstream_not_successful")
        if operation == "release":
            sha = metadata["headSha"]
    # Same code must have passed Release; later request-only commits are allowed.
    jobs.command(["git", "diff", "--exit-code", sha, "HEAD", "--", "jobs", "services", "packages",
                  "scripts/gcp/three_pipeline_acceptance.py", "tests/test_three_pipelines.py"])
    request = json.loads(Path("ops/ghcr-jobs-rollout-request.json").read_text())
    if request.get("sha") != sha or request.get("release_run") != release_run:
        raise ValueError("rollout_source_mismatch")
    # Fetch actual successful rollout artifact, not just a green workflow.
    folder = Path("/tmp/three-pipeline-rollout")
    folder.mkdir(exist_ok=True)
    jobs.command(["gh", "run", "download", jobs_run, "--name", "ghcr-jobs-rollout-receipt", "--dir", str(folder)])
    proof = json.loads((folder / "ghcr-jobs-rollout.json").read_text())
    if proof.get("phase") != "PASS" or proof.get("source_sha") != sha:
        raise ValueError("rollout_receipt_mismatch")
    for name, target in proof["targets"].items():
        if jobs.image(jobs.job(name)) != target:
            raise ValueError("deployed_image_drift")
    return sha


def invoke(name, env, proof, save, timeout="3600s"):
    job = jobs.job(name)
    override = {"env": [{"name": key, "value": value} for key, value in env.items()]}
    container = job["template"]["template"]["containers"][0]
    if container.get("name"):
        override["name"] = container["name"]
    operation = jobs.cloud(f"{jobs.ROOT}/jobs/{name}:run", {"etag": job["etag"], "overrides": {
        "taskCount": 1, "timeout": timeout, "containerOverrides": [override]}}, "POST")
    identity = operation.get("name", "")
    if not identity.startswith(jobs.ROOT + "/operations/"):
        raise RuntimeError("dispatch_unknown_lease_retained")
    proof.setdefault("operations", []).append(identity)
    save()
    deadline = time.monotonic() + 3700
    while not operation.get("done") and time.monotonic() < deadline:
        time.sleep(15)
        operation = jobs.cloud(identity)
    execution = operation.get("response", {})
    if execution.get("name", "").startswith(jobs.ROOT + f"/jobs/{name}/executions/"):
        execution = jobs.cloud(execution["name"])
    if (not operation.get("done") or operation.get("error") or not jobs.terminal(execution)
            or execution.get("succeededCount") != 1 or execution.get("failedCount", 0)):
        raise RuntimeError("pipeline_execution_failed_or_unknown")
    proof.setdefault("executions", []).append({"job": name, "execution": execution["name"], "status": "PASS"})
    save()
    return execution["name"].split("/")[-1]


def run(args):
    proof = {"phase": "PREFLIGHT", "trigger": "controlled", "group": args.group, "new_resources": 0}
    def save():
        args.receipt.write_text(json.dumps(proof, sort_keys=True))
    save()
    proof["source_sha"] = source_gate(args.release_run, args.jobs_run)
    date.fromisoformat(args.source_date)
    baseline = jobs.existing_jobs()
    expected_hashes = {name: jobs.fingerprint(value) for name, value in baseline.items()}
    jobs.command(LEASE + ["acquire"])
    safe = False
    before = None
    try:
        jobs.legacy_writers()
        before = jobs.scheduler()
        if before["state"] != "ENABLED" or before["schedule"] != "30 */2 * * *":
            raise ValueError("scheduler_baseline_invalid")
        jobs.set_scheduler("pause", "PAUSED")
        jobs.wait_for_terminal_executions(timeout=900)
        jobs.command(LEASE + ["assert"])
        if args.group == "configure":
            current = jobs.job("janus-batch-controller")
            expected = deepcopy(current)
            expected["template"]["template"]["timeout"] = "3600s"
            cutoff = datetime.now(timezone.utc).isoformat()
            env = expected["template"]["template"]["containers"][0].setdefault("env", [])
            activation = next((item for item in env if item["name"] == "BATCH_CONTROLLER_NOT_BEFORE"), None)
            if activation is None:
                env.append({"name": "BATCH_CONTROLLER_NOT_BEFORE", "value": cutoff})
            else:
                activation["value"] = cutoff
            jobs.command(["gcloud", "run", "jobs", "update", "janus-batch-controller",
                "--project=" + jobs.PROJECT, "--region=" + jobs.REGION, "--task-timeout=3600s",
                "--update-env-vars=BATCH_CONTROLLER_NOT_BEFORE=" + cutoff, "--quiet"])
            expected_hashes["janus-batch-controller"] = jobs.fingerprint(expected)
            jobs.checked_image("janus-batch-controller", jobs.image(current), expected_hashes["janus-batch-controller"])
            proof["controller_timeout_seconds"] = 3600
            proof["new_schedule_cutoff"] = cutoff
            save()
            invoke("janus-batch-controller", {"BATCH_CONTROLLER_MODE": "retire-legacy",
                "BATCH_CONTROLLER_NOT_BEFORE": cutoff, "BATCH_ACCEPTANCE_GROUP": ""}, proof, save)
        else:
            invoke("janus-batch-controller", {"BATCH_CONTROLLER_MODE": "active",
                "BATCH_ACCEPTANCE_GROUP": args.group, "BATCH_ACCEPTANCE_DATE": args.source_date}, proof, save)
        jobs.wait_for_terminal_executions(timeout=900)
        if jobs.scheduler_fingerprint(jobs.scheduler()) != jobs.scheduler_fingerprint(before):
            raise ValueError("scheduler_configuration_drift")
        jobs.set_scheduler("resume", "ENABLED")
        proof["phase"] = "PASS"
        save()
        safe = True
    except Exception:
        proof["phase"] = "FAILED_INSPECT_PERSISTED_WORK_LEASE_RETAINED"
        save()
        # A proven terminal business failure does not justify stranding the Scheduler.
        # Unknown execution/config state retains the original owner lease.
        try:
            jobs.wait_for_terminal_executions(timeout=900)
            for name, value in baseline.items():
                jobs.checked_image(name, jobs.image(value), expected_hashes[name])
            if before is None or jobs.scheduler_fingerprint(jobs.scheduler()) != jobs.scheduler_fingerprint(before):
                raise ValueError("recovery_configuration_unknown")
            if jobs.scheduler()["state"] == "PAUSED":
                jobs.set_scheduler("resume", "ENABLED")
            if jobs.scheduler()["state"] != "ENABLED":
                raise ValueError("recovery_scheduler_unknown")
            proof["phase"] = "FAILED_SAFE_SCHEDULER_RESTORED"
            save()
            safe = True
        except Exception:
            pass
        raise
    finally:
        if safe:
            jobs.command(LEASE + ["release", "--safe-to-release"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-run", required=True)
    parser.add_argument("--jobs-run", required=True)
    parser.add_argument("--group", choices=["configure", "eod", "compensation", "backup", "maintenance"], required=True)
    parser.add_argument("--source-date", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    try:
        run(parser.parse_args())
    except Exception as error:
        reason = str(error) if re.fullmatch(r"[a-z][a-z0-9_]{3,100}", str(error)) else "bounded_acceptance_failure"
        print(json.dumps({"status": "FAILED", "reason": reason}))
        raise SystemExit(1)
