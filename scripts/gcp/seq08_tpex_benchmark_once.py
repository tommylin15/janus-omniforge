#!/usr/bin/env python3
"""One bounded existing-Dev Cloud Run ingestion Job for official TPEx Core data.

Never retry an ambiguous POST. Uses current GHCR pinned image, one shared
runtime lease, exact Cloud Run execution, GCS immutable Core snapshot readback.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from ghcr_jobs_rollout import ROOT, command, cloud, job, terminal, wait_for_terminal_executions
from ghcr_mcp_route import LEASE

REQUEST = Path("ops/seq08-tpex-benchmark-request.json")
RECEIPT = Path("/tmp/seq08-tpex-benchmark-receipt.json")
JOB = "janus-ingestion-core"
CORE_BUCKET = "gen-lang-client-0593591102-dev-core"
PREVIOUS_CORE = "sha256:544970f64e6dd965ca6cf57786a120f3eb39ffeddacd6255bdcc373ade74ffd3"

def approved(payload: dict) -> dict:
    if (payload.get("intent") != "seq08-official-tpex-price-benchmark-only"
            or payload.get("approved") is not True
            or payload.get("apply") is not True
            or payload.get("scope") != "existing-dev-ingestion-one-job"
            or payload.get("months") != ["2026-09", "2026-10"]
            or payload.get("date_start") != "2026-09-01"
            or payload.get("date_end") != "2026-10-22"
            or payload.get("max_runs") != 1
            or any(payload.get(k) is not False for k in
                   ("new_resources_allowed", "owner_mutation_allowed",
                    "job_template_mutation_allowed", "scheduler_mutation_allowed",
                    "retraining_allowed"))
            or not re.fullmatch("[0-9a-f]{40}", str(payload.get("source_sha", "")))
            or not re.fullmatch("[0-9]{6,15}", str(payload.get("release_run", "")))
            or not re.fullmatch("[0-9]{6,15}", str(payload.get("jobs_run", "")))):
        raise ValueError("tpex_benchmark_bounded_request_invalid")
    return payload

def successful(run_id: str, name: str) -> None:
    data = json.loads(command(["gh", "run", "view", run_id,
                               "--json", "status,conclusion,jobs"]))
    jobs = [job for job in data.get("jobs", []) if job.get("name") == name
            and job.get("conclusion") == "success"
            and job.get("status") == "completed"]
    if data.get("status") != "completed" or data.get("conclusion") != "success" or len(jobs) != 1:
        raise ValueError("tpex_benchmark_source_release_gate_incomplete")

def pinned(source: str, current: dict) -> bool:
    from drl01_market_volume_replay import digest_matches
    return digest_matches(source, current)

def log_result(execution: str) -> dict:
    query = ('resource.type="cloud_run_job" AND '
             'labels."run.googleapis.com/execution_name"="' + execution + '"')
    for attempt in range(5):
        response = subprocess.run(["gcloud", "logging", "read", query,
            "--project=gen-lang-client-0593591102", "--limit=100", "--format=json"],
            capture_output=True, text=True, check=False, timeout=60)
        if response.returncode != 0:
            raise ValueError("tpex_benchmark_log_permission_denied")
        hits = []
        for line in json.loads(response.stdout):
            payload = line.get("jsonPayload")
            if not isinstance(payload, dict):
                try:
                    payload = json.loads(line.get("textPayload", ""))
                except (ValueError, TypeError):
                    continue
            if isinstance(payload, dict) and payload.get("component") == "seq08_tpex_benchmark":
                hits.append(payload)
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ValueError("tpex_benchmark_execution_log_ambiguous")
        time.sleep(3 + attempt)
    raise ValueError("tpex_benchmark_execution_log_unavailable")

def snapshot(proof: dict) -> dict:
    name = proof.get("core_snapshot_uri", "")
    identity = proof.get("execution_id", "")
    if (not re.fullmatch("[0-9a-f-]{36}", str(identity))
            or name != "gs://" + CORE_BUCKET + "/executions/" + identity + "/core-snapshot.json"):
        raise ValueError("tpex_benchmark_snapshot_uri_invalid")
    data = json.loads(command(["gcloud", "storage", "cat", name,
                               "--project=gen-lang-client-0593591102"]))
    if (data.get("execution_id") != identity
            or data.get("snapshot_id") != proof.get("core_snapshot_id")
            or data.get("snapshot_id") == PREVIOUS_CORE
            or "core.benchmark_v1" not in data.get("iceberg_tables", {})
            or any(proof.get("months", {}).get(m, {}).get("official_sessions", 0) < 10
                   for m in ("2026-09", "2026-10"))
            or proof.get("market_stock_ohlcv_writes") != 0):
        raise ValueError("tpex_benchmark_new_core_fence_invalid")
    return {"core_snapshot_id": data["snapshot_id"],
            "analysis_as_of": data["analysis_as_of"],
            "execution_id": identity, "benchmark_fence": True}

def execute(path=REQUEST, receipt=RECEIPT) -> dict:
    import os
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise ValueError("tpex_benchmark_github_rerun_forbidden")
    request = approved(json.loads(Path(path).read_text()))
    successful(request["release_run"], "release-verify")
    successful(request["jobs_run"], "jobs-rollout")
    report = {"phase": "PREFLIGHT", "result": "UNKNOWN",
              "source_sha": request["source_sha"], "cloud_run_writes": "NOT_DISPATCHED"}
    def save():
        Path(receipt).write_text(json.dumps(report, sort_keys=True))
    save()
    lease = False
    dispatched = False
    safe = False
    try:
        command(LEASE + ["acquire"])
        lease = True
        command(LEASE + ["assert"])
        wait_for_terminal_executions(timeout=720)
        current = job(JOB)
        if not pinned(request["source_sha"], current):
            raise ValueError("tpex_benchmark_serving_ingestion_digest_drift")
        container = current["template"]["template"]["containers"][0]
        entry = container.get("command")
        if entry not in (None, [], ["python"]):
            raise ValueError("tpex_benchmark_entrypoint_unknown")
        args = ["-m", "ingestion_core.tpex_benchmark"]
        if not entry:
            args = ["python", *args]
        overrides = {"args": args, "env": [
            {"name": "SEQ08_TPEX_BENCHMARK_ONLY", "value": "true"},
            {"name": "BACKFILL_START_DATE", "value": request["date_start"]},
            {"name": "BACKFILL_END_DATE", "value": request["date_end"]},
            {"name": "QUEUE_CONSUMER", "value": "false"},
            {"name": "MART_JOB", "value": ""},
            {"name": "JANUS_DATA_SUPPLEMENT_MODE", "value": ""},
        ]}
        if container.get("name"):
            overrides["name"] = container["name"]
        report["phase"] = "DISPATCH_OUTCOME_UNKNOWN_NO_RETRY"
        report["cloud_run_writes"] = "POSSIBLE"
        save()
        dispatched = True
        operation = cloud(ROOT + "/jobs/" + JOB + ":run", {
            "etag": current["etag"], "overrides": {
                "taskCount": 1, "timeout": "1200s",
                "containerOverrides": [overrides]}}, "POST")
        name = operation.get("name", "")
        if not name.startswith(ROOT + "/operations/"):
            raise ValueError("tpex_benchmark_operation_identity_ambiguous")
        report["operation"] = name
        report["phase"] = "RUNNING"
        save()
        deadline = time.monotonic() + 1350
        while not operation.get("done") and time.monotonic() < deadline:
            time.sleep(10)
            operation = cloud(name)
        if not operation.get("done"):
            raise ValueError("tpex_benchmark_terminal_unknown_no_retry")
        if operation.get("error"):
            safe = True
            raise ValueError("tpex_benchmark_cloud_run_failed")
        result = operation.get("response", {})
        if not terminal(result):
            raise ValueError("tpex_benchmark_execution_terminal_ambiguous")
        safe = True
        if result.get("succeededCount") != 1 or result.get("failedCount", 0) != 0:
            raise ValueError("tpex_benchmark_execution_failed")
        execution = result.get("name", "").rsplit("/", 1)[-1]
        if not re.fullmatch("janus-ingestion-core-[a-z0-9-]+", execution):
            raise ValueError("tpex_benchmark_execution_name_invalid")
        report["execution"] = execution
        report["phase"] = "GCS_AND_LOG_READBACK"
        save()
        proof = log_result(execution)
        if proof.get("status") != "succeeded":
            raise ValueError("tpex_benchmark_source_partial")
        report["core"] = snapshot(proof)
        report["official_months"] = proof["months"]
        report["phase"] = "PASS_NEW_OFFICIAL_TPEX_CORE"
        report["result"] = "PASS"
        save()
        return report
    finally:
        if lease and (safe or not dispatched):
            command(LEASE + ["release", "--safe-to-release"])
            report["lease_released"] = True
            save()

if __name__ == "__main__":
    try:
        print(json.dumps(execute(), sort_keys=True), flush=True)
    except Exception as error:
        print(json.dumps({"status": "BLOCKED_OR_FAILED",
                          "reason": str(error) if isinstance(error, ValueError)
                          and re.fullmatch("[a-z0-9_]+", str(error)) else type(error).__name__,
                          "no_auto_retry": True}), flush=True)
        sys.exit(78)
