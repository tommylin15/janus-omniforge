"""SEQ-08: one bounded existing-Dev Mart Job with real Core data and true ACTIVE models.

No new resource, training, LLM call, Scheduler change, Owner ledger mutation or
model rollback. The resulting immutable Mart/PG projection is a normal Dev
workload; subsequent product readback must verify actual head predictions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time

import ghcr_jobs_rollout as jobs
from ghcr_mcp_route import LEASE

SOURCE = "a2881c5c2532beb5570e29a1fda4472c7bb0d448"
RELEASE_RUN = "40184318031"
JOBS_RUN = "40184957380"
API_RUN = "40192646498"
REGISTRY_RUN = "40193843435"
JOB = "janus-intelligence-mart"
POINTER = "models/registry/seq08-four-models-active.json"
BUCKET = "gen-lang-client-0593591102-dev-mart"


def authorize():
    request = json.loads(Path("ops/seq08-live-acceptance-request.json").read_text())
    if (request.get("intent") != "seq08-bounded-real-mart-acceptance"
            or request.get("approved") is not True
            or request.get("scope") != "existing-dev-one-intelligence-mart-job"
            or request.get("source_sha") != SOURCE
            or request.get("release_run") != RELEASE_RUN
            or request.get("jobs_run") != JOBS_RUN
            or request.get("api_run") != API_RUN
            or request.get("registry_run") != REGISTRY_RUN
            or request.get("mart_operation") != "deep-coverage"
            or request.get("job_runs_allowed") != 1
            or request.get("training_allowed") is not False
            or request.get("llm_allowed") is not False
            or request.get("owner_ledger_writes_allowed") is not False
            or request.get("new_resources_allowed") is not False):
        raise ValueError("seq08_real_mart_request_unapproved")
    return request


def successful(run, required):
    result = jobs.command(["gh", "run", "view", run,
                           "--json", "status,conclusion,jobs"])
    data = json.loads(result)
    matches = [r for r in data.get("jobs", []) if r.get("name") == required
               and r.get("status") == "completed" and r.get("conclusion") == "success"]
    if data.get("status") != "completed" or data.get("conclusion") != "success" or len(matches) != 1:
        raise ValueError("seq08_upstream_runtime_gate_incomplete")


def accepted_job():
    proof_dir = Path("/tmp/seq08-live-jobs-proof")
    proof_dir.mkdir(parents=True, exist_ok=True)
    receipt = proof_dir / "ghcr-jobs-rollout.json"
    if not receipt.exists():
        jobs.command(["gh", "run", "download", JOBS_RUN, "-n",
                      "ghcr-jobs-rollout-receipt", "-D", str(proof_dir)])
    proof = json.loads(receipt.read_text())
    image = proof.get("targets", {}).get(JOB)
    config_hash = proof.get("snapshots", {}).get(JOB, {}).get("configuration_hash")
    if (proof.get("source_sha") != SOURCE or proof.get("phase") != "PASS"
            or proof.get("rollback_baseline_verified") is not True
            or not isinstance(image, str) or "@sha256:" not in image
            or not isinstance(config_hash, str) or len(config_hash) != 64):
        raise ValueError("seq08_job_digest_receipt_not_verified")
    return jobs.checked_image(JOB, image, config_hash)


def pointer_readback():
    result = subprocess.run(["gcloud", "storage", "cat",
        f"gs://{BUCKET}/{POINTER}", "--project", jobs.PROJECT],
        capture_output=True, check=False, timeout=90)
    if result.returncode:
        raise ValueError("seq08_active_pointer_not_readable")
    import sys
    sys.path.insert(0, "jobs/intelligence-mart")
    from intelligence_mart.seq08_native_serving import expected_pointer
    if json.loads(result.stdout) != expected_pointer():
        raise ValueError("seq08_active_pointer_source_mismatch")


def execute(receipt_file):
    authorize()
    for run, job in ((RELEASE_RUN, "release-verify"), (JOBS_RUN, "jobs-rollout"),
                     (API_RUN, "promote-api-only"),
                     (REGISTRY_RUN, "seq08-model-activation")):
        successful(run, job)
    pointer_readback()
    target = accepted_job()
    jobs.legacy_writers()
    if jobs.scheduler().get("state") != "ENABLED":
        raise ValueError("existing_dev_scheduler_not_enabled")
    receipt = {"phase": "PREFLIGHT", "source_sha": SOURCE, "job": JOB,
               "mart_operation": "deep-coverage", "job_runs_allowed": 1,
               "registry_mutations": 0, "owner_ledger_mutations": 0,
               "llm_calls": 0, "new_resources": 0}
    def save():
        receipt_file.write_text(json.dumps(receipt, sort_keys=True))
    save()
    jobs.command(LEASE + ["acquire"])
    safe = False
    dispatched = False
    try:
        jobs.command(LEASE + ["assert"])
        jobs.wait_for_terminal_executions(timeout=720)
        target = accepted_job()  # verify unchanged source/image/config under lease
        container = target["template"]["template"]["containers"][0]
        command = container.get("command")
        if command not in (None, ["python"]):
            raise ValueError("mart_container_entrypoint_unknown")
        arguments = ["-m", "intelligence_mart.__main__"]
        if not command:
            arguments = ["python", *arguments]
        override = {"args": arguments, "env": [
            {"name": "MART_OPERATION", "value": "deep-coverage"},
            {"name": "MART_PRODUCT_PROJECTION", "value": "true"}]}
        if container.get("name"):
            override["name"] = container["name"]
        receipt["phase"] = "DISPATCH_REQUESTED"
        save()
        operation = jobs.cloud(f"{jobs.ROOT}/jobs/{JOB}:run",
            {"etag": target["etag"], "overrides": {
                "taskCount": 1, "timeout": "1200s", "containerOverrides": [override]}},
            "POST")
        dispatched = True
        operation_name = operation.get("name", "")
        if not operation_name.startswith(f"{jobs.ROOT}/operations/"):
            raise ValueError("unknown_mart_execution_operation")
        receipt["operation"] = operation_name.rsplit("/", 1)[-1]
        receipt["phase"] = "WAITING_FOR_REAL_DEV_JOB"
        save()
        deadline = time.monotonic() + 1400
        while not operation.get("done") and time.monotonic() < deadline:
            time.sleep(10)
            operation = jobs.cloud(operation_name)
        if not operation.get("done"):
            raise ValueError("real_mart_job_unknown_terminal")
        if operation.get("error"):
            safe = True
            raise ValueError("real_mart_job_operation_failed")
        result = operation.get("response", {})
        if not jobs.terminal(result):
            raise ValueError("real_mart_job_ambiguous_terminal")
        safe = True
        if result.get("succeededCount") != 1 or result.get("failedCount", 0) != 0:
            raise ValueError("real_mart_job_failed")
        receipt["cloud_run_execution"] = result["name"].rsplit("/", 1)[-1]
        receipt["phase"] = "REAL_JOB_PASS_PRODUCT_CONTENT_READBACK_PENDING"
        save()
        return receipt
    finally:
        if safe or not dispatched:
            jobs.command(LEASE + ["release", "--safe-to-release"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args()
    try:
        output = execute(args.receipt)
        print(json.dumps({"result": "PASS", "phase": output["phase"],
            "job": JOB, "source_sha": SOURCE}))
        return 0
    except Exception as error:
        print(json.dumps({"result": "BLOCKED_OR_FAILED",
            "reason": str(error) if isinstance(error, ValueError) else type(error).__name__}))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
