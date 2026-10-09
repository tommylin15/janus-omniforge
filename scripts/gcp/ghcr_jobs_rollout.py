#!/usr/bin/env python3
"""Controlled existing-dev image rollout; no secret/config payload in receipts."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ghcr_job_cutover_plan import JOB_COMPONENT
from ghcr_job_cutover_guard import PROJECT, REGION, SCHEDULER, REQUIRED_JOBS
from ghcr_mcp_route import command, LEASE

ROOT = f"projects/{PROJECT}/locations/{REGION}"
BASE = "https://run.googleapis.com/v2/"
PIN = re.compile(r"^[a-z0-9./-]+@sha256:[0-9a-f]{64}$")


def cloud(path, body=None, method=None):
    # Tokens stay in memory and headers, never argv, receipt or exception text.
    token = command(["gcloud", "auth", "print-access-token"]).strip()
    req = Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                  headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                  method=method)
    try:
        with urlopen(req, timeout=40) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"cloud_control_http_{error.code}") from None


def job(name):
    if name not in REQUIRED_JOBS:
        raise ValueError("job_outside_existing_dev_scope")
    data = cloud(f"{ROOT}/jobs/{name}")
    if data.get("name") != f"{ROOT}/jobs/{name}" or data.get("reconciling", False):
        raise ValueError("job_not_reconciled")
    if data.get("terminalCondition", {}).get("state") != "CONDITION_SUCCEEDED":
        raise ValueError("job_not_ready")
    return data


def image(data):
    containers = data["template"]["template"]["containers"]
    if len(containers) != 1:
        raise ValueError("single_container_required")
    return containers[0]["image"].removeprefix("cache.us-docker.pkg.dev/")


def fingerprint(data):
    config = {key: deepcopy(data.get(key, {})) for key in ("template", "labels", "annotations")}
    config["template"]["template"]["containers"][0].pop("image", None)
    # gcloud updates its own client metadata, not runtime configuration.
    for key in ("run.googleapis.com/client-name", "run.googleapis.com/client-version"):
        config["annotations"].pop(key, None)
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def checked_image(name, target, expected_hash):
    data = job(name)
    if image(data) != target or fingerprint(data) != expected_hash:
        raise ValueError("image_or_configuration_drift")
    return data


def terminal(data):
    completed = [c for c in data.get("conditions", []) if c.get("type") == "Completed"]
    return (not data.get("reconciling", False) and data.get("runningCount", 0) == 0
            and len(completed) == 1 and completed[0].get("state") in
            {"CONDITION_SUCCEEDED", "CONDITION_FAILED"}
            and completed[0].get("executionReason") not in
            {"JOB_STATUS_SERVICE_POLLING_ERROR", "CANCELLING", "DELAYED_START_PENDING"})


def fence():
    for name in REQUIRED_JOBS:
        path = f"{ROOT}/jobs/{name}/executions?pageSize=100"
        seen = set()
        while path:
            data = cloud(path)
            if not all(terminal(e) for e in data.get("executions", [])):
                raise ValueError("execution_not_terminal")
            token = data.get("nextPageToken")
            if token in seen:
                raise ValueError("execution_pagination_loop")
            if token:
                from urllib.parse import quote
                seen.add(token)
                path = f"{ROOT}/jobs/{name}/executions?pageSize=100&pageToken={quote(token, safe='')}"
            else:
                path = None


def job_update_permissions():
    """Fail closed before pausing Scheduler or modifying any Cloud Run Job.

    Canary executions use the v2 jobs.run overrides contract and require
    run.jobs.runWithOverrides, not merely run.jobs.run.
    """
    targets = {name for name, _ in JOB_COMPONENT}
    for name in REQUIRED_JOBS:
        # Research is read-only and MUST NOT receive update/execute privileges.
        required = {"run.jobs.get"}
        if name in targets:
            required |= {"run.jobs.update", "run.jobs.run", "run.jobs.runWithOverrides"}
        result = cloud(f"{ROOT}/jobs/{name}:testIamPermissions",
                       {"permissions": sorted(required)}, "POST")
        granted = result.get("permissions", [])
        if not isinstance(granted, list) or not required.issubset(set(granted)):
            raise ValueError("job_rollout_iam_missing")


def scheduler():
    rows = json.loads(command(["gcloud", "scheduler", "jobs", "list", f"--project={PROJECT}",
                               f"--location={REGION}", "--format=json"]))
    if (len(rows) != 1 or rows[0]["name"] != f"{ROOT}/jobs/{SCHEDULER}"
            or rows[0].get("schedule") != "30 * * * *" or rows[0].get("timeZone") != "Asia/Taipei"
            or rows[0].get("httpTarget", {}).get("uri") != BASE + ROOT + "/jobs/janus-batch-controller:run"):
        raise ValueError("scheduler_topology_drift")
    return rows[0]


def scheduler_fingerprint(data):
    config = {key: data.get(key) for key in ("name", "schedule", "timeZone", "httpTarget", "retryConfig", "attemptDeadline")}
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def set_scheduler(operation, state):
    command(["gcloud", "scheduler", "jobs", operation, SCHEDULER, f"--project={PROJECT}",
             f"--location={REGION}", "--quiet"])
    if scheduler()["state"] != state:
        raise ValueError("scheduler_state_not_confirmed")


def legacy_writers():
    triggers = json.loads(command(["gcloud", "builds", "triggers", "list", f"--project={PROJECT}",
                                   f"--region={REGION}", "--filter=name=janus-dev-v2", "--format=json(id,disabled)"]))
    builds = json.loads(command(["gcloud", "builds", "list", f"--project={PROJECT}", f"--region={REGION}",
                                 "--filter=status=QUEUED OR status=WORKING OR status=PENDING", "--limit=1", "--format=json(id)"]))
    if len(triggers) != 1 or triggers[0].get("disabled") is not True or builds:
        raise ValueError("legacy_writer_unfenced")


def writers():
    legacy_writers()
    command(LEASE + ["assert"])


def update(name, target, expected_hash):
    if not PIN.fullmatch(target):
        raise ValueError("immutable_image_required")
    writers()
    if scheduler()["state"] != "PAUSED":
        raise ValueError("scheduler_not_paused")
    fence()
    if fingerprint(job(name)) != expected_hash:
        raise ValueError("preupdate_configuration_drift")
    command(["gcloud", "run", "jobs", "update", name, f"--project={PROJECT}", f"--region={REGION}",
             "--image=" + target, "--quiet"])
    checked_image(name, target, expected_hash)


PRIVATE_PROBE = """import os,psycopg
from packages.postgres_bundle import load_postgres_bundle
load_postgres_bundle('JANUS_API_POSTGRES_BUNDLE', {'PRIVATE_DATABASE_URL':('pipeline_database_url','database_url')})
with psycopg.connect(os.environ['PRIVATE_DATABASE_URL'],sslmode='require',connect_timeout=5) as connection:
    connection.execute('SET TRANSACTION READ ONLY')
    connection.execute("SET LOCAL statement_timeout='15000ms'")
    connection.execute('SELECT event_id FROM private.ledger_events LIMIT 1').fetchall()
    connection.execute('SELECT user_id FROM private.current_positions LIMIT 1').fetchall()
print('Read-only private database canary PASS')
"""


def canary(name, expected_image, expected_hash, journal, save):
    data = checked_image(name, expected_image, expected_hash)
    container = data["template"]["template"]["containers"][0]
    if name == "janus-private-pipeline":
        args, env = ["-c", PRIVATE_PROBE], []
    elif name == "janus-intelligence-mart":
        args, env = ["-m", "intelligence_mart.__main__"], [{"name": "MART_OPERATION", "value": "postgres-smoke"}]
    else:
        args, env = ["-m", "ingestion_core.entrypoint"], [{"name": "JANUS_CICD_READINESS", "value": "check"}]
    if not container.get("command"):
        args = ["python"] + args
    elif container["command"] != ["python"]:
        raise ValueError("canary_entrypoint_unknown")
    override = {"args": args, "env": env}
    if container.get("name"):
        override["name"] = container["name"]
    writers()
    fence()
    operation = cloud(f"{ROOT}/jobs/{name}:run", {"etag": data["etag"], "overrides": {
        "taskCount": 1, "timeout": "300s", "containerOverrides": [override]}}, "POST")
    operation_name = operation.get("name")
    if not isinstance(operation_name, str) or not operation_name.startswith(ROOT + "/operations/"):
        raise ValueError("canary_operation_unknown")
    journal["operations"].append(operation_name)
    save()
    deadline = time.monotonic() + 420
    while not operation.get("done") and time.monotonic() < deadline:
        time.sleep(5)
        operation = cloud(operation_name)
    if not operation.get("done") or operation.get("error"):
        raise ValueError("canary_failed_or_unknown")
    result = operation.get("response", {})
    if not terminal(result) or result.get("succeededCount") != 1 or result.get("failedCount", 0) != 0:
        raise ValueError("canary_not_successful")
    journal["canaries"].append({"job": name, "execution": result["name"].split("/")[-1], "result": "PASS"})
    save()


def acceptance(sha):
    proof = json.loads(Path("ops/ghcr-owner-acceptance.json").read_text())
    if (proof.get("source_sha") != sha or proof.get("result") != "PASS"
            or not all(proof.get("gates", {}).get(key) is True for key in
                       ("google_oauth", "owner_a_read", "owner_b_isolation", "known_a_record_rejected", "pnl_parity", "readonly_mcp"))
            or proof.get("janus_dev_private") != "BYPASSED"):
        raise ValueError("owner_acceptance_not_verified")
    observed = datetime.fromisoformat(proof["observed_at"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - observed).total_seconds()
    if not 0 <= age < 86400:
        raise ValueError("owner_acceptance_stale")


def run(release_run, receipt):
    sha = json.loads(Path("ops/ghcr-candidate-request.json").read_text())["sha"]
    request = json.loads(Path("ops/ghcr-jobs-rollout-request.json").read_text())
    if (request.get("intent") != "approved-dev-ghcr-jobs-rollout"
            or request.get("approved") is not True
            or request.get("scope") != "existing-dev-four-jobs"
            or request.get("sha") != sha
            or request.get("release_run") != release_run
            or request.get("rollback_mode") != "user_authorized_forward_only"
            or request.get("accept_no_old_image_rollback") is not True):
        raise ValueError("forward_only_user_authorization_missing")
    acceptance(sha)
    release = json.loads(command(["gh", "run", "view", release_run, "--json", "headSha,status,conclusion,workflowName"]))
    if (release.get("headSha") != sha or release.get("status") != "completed"
            or release.get("conclusion") != "success" or release.get("workflowName") != "Janus GHCR full-test image publication"):
        raise ValueError("full_release_not_successful")
    targets = {}
    for name, component in JOB_COMPONENT:
        manifest = json.loads(command(["skopeo", "inspect", "--no-creds", f"docker://ghcr.io/tommylin15/janus-{component}:sha-{sha}"]))
        target = f"ghcr.io/tommylin15/janus-{component}@{manifest['Digest']}"
        if not PIN.fullmatch(target) or manifest.get("Labels", {}).get("org.opencontainers.image.revision") != sha:
            raise ValueError("public_image_identity_mismatch")
        command(["skopeo", "inspect", "--no-creds", "docker://" + target])
        targets[name] = target
    job_update_permissions()
    command(LEASE + ["acquire"])
    journal = {"source_sha": sha, "phase": "PREFLIGHT", "snapshots": {}, "operations": [], "canaries": []}
    def save():
        receipt.write_text(json.dumps(journal, sort_keys=True))
    paused, safe = False, False
    try:
        writers()
        schedule = scheduler()
        if schedule["state"] != "ENABLED":
            raise ValueError("scheduler_baseline_not_enabled")
        journal["scheduler_hash"] = scheduler_fingerprint(schedule)
        fence()
        full_snapshots = {}
        for name in REQUIRED_JOBS:
            data = job(name)
            full_snapshots[name] = data
            previous = image(data)
            if not PIN.fullmatch(previous):
                raise ValueError("rollback_image_not_pinned")
            # gcloud validates the existing private registry digest, no scanning API.
            if previous.startswith("ghcr.io/"):
                command(["skopeo", "inspect", "--no-creds", "docker://" + previous])
            else:
                command(["gcloud", "artifacts", "docker", "images", "describe", previous, "--format=value(image_summary.digest)"])
            journal["snapshots"][name] = {"image": previous, "configuration_hash": fingerprint(data)}
        # Full configs stay on the runner with restrictive permissions; only
        # immutable images and hashes enter the uploaded recovery receipt.
        full_path = receipt.with_name("ghcr-full-job-snapshots.json")
        full_path.write_text(json.dumps(full_snapshots))
        os.chmod(full_path, 0o600)
        save()
        # Mark intent before calling pause: an uncertain pause must be recovered.
        paused = True
        set_scheduler("pause", "PAUSED")
        writers()
        fence()
        for name, _ in JOB_COMPONENT:
            snap = journal["snapshots"][name]
            journal["phase"] = "REHEARSAL"
            save()
            update(name, targets[name], snap["configuration_hash"])
            canary(name, targets[name], snap["configuration_hash"], journal, save)
            update(name, snap["image"], snap["configuration_hash"])
        journal["phase"] = "ROLLBACK_REHEARSAL_PASS"
        save()
        for name, _ in JOB_COMPONENT:
            snap = journal["snapshots"][name]
            update(name, targets[name], snap["configuration_hash"])
            canary(name, targets[name], snap["configuration_hash"], journal, save)
        for name in REQUIRED_JOBS:
            snap = journal["snapshots"][name]
            checked_image(name, targets.get(name, snap["image"]), snap["configuration_hash"])
        fence()
        if scheduler_fingerprint(scheduler()) != journal["scheduler_hash"]:
            raise ValueError("scheduler_configuration_drift")
        set_scheduler("resume", "ENABLED")
        journal["phase"] = "PASS"
        save()
        safe = True
    except Exception:
        journal["phase"] = "RECOVERY_REQUIRED"
        save()
        if paused:
            recover(journal, save)
        else:
            # Preflight never changed a Job or Scheduler. Prove the baseline
            # is still intact and mark this state to prevent duplicate recovery.
            fence()
            if scheduler()["state"] != "ENABLED":
                raise RuntimeError("preflight_state_unknown_lease_retained") from None
            journal["phase"] = "PREFLIGHT_BLOCKED_NO_MUTATION"
            save()
        safe = True
        raise
    finally:
        if safe:
            command(LEASE + ["release", "--safe-to-release"])


def recover(journal, save):
    command(LEASE + ["assert"])
    fence()
    for name, _ in reversed(JOB_COMPONENT):
        snap = journal["snapshots"].get(name)
        if snap and image(job(name)) != snap["image"]:
            if scheduler()["state"] != "PAUSED":
                set_scheduler("pause", "PAUSED")
            update(name, snap["image"], snap["configuration_hash"])
    for name, snap in journal["snapshots"].items():
        checked_image(name, snap["image"], snap["configuration_hash"])
    if scheduler_fingerprint(scheduler()) != journal["scheduler_hash"]:
        raise ValueError("scheduler_configuration_drift")
    set_scheduler("resume", "ENABLED")
    journal["phase"] = "RESTORED"
    save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-run", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[0-9]+", args.release_run):
            raise ValueError("invalid_release_run")
        if args.recover:
            journal = json.loads(args.receipt.read_text())
            if journal["phase"] not in {"PASS", "RESTORED", "PREFLIGHT_BLOCKED_NO_MUTATION"}:
                recover(journal, lambda: args.receipt.write_text(json.dumps(journal)))
                command(LEASE + ["release", "--safe-to-release"])
        else:
            run(args.release_run, args.receipt)
        print(json.dumps({"result": "PASS", "receipt": args.receipt.name}))
        return 0
    except Exception as error:
        # Never print exception text from cloud, database or registry responses.
        reason = str(error) if re.fullmatch(r"[a-z][a-z0-9_]{3,100}", str(error)) else "control_failure"
        print(json.dumps({"result": "BLOCKED_OR_FAILED", "error_type": type(error).__name__, "reason": reason}))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
