#!/usr/bin/env python3
"""DRL-01D bounded official TWSE PE/PB 61-month, six-symbol dev backfill.

Only calls the existing deployed ingestion job with temporary execution overrides;
does not mutate a Job template, Scheduler, owner data, source catalog or images.
Every page is fenced, every execution is read back from its own terminal receipt.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from ghcr_jobs_rollout import ROOT, cloud, job, terminal, wait_for_terminal_executions

PROJECT = "gen-lang-client-0593591102"
JOB = "janus-ingestion-core"
SYMBOLS = ["1513", "2327", "2382", "3231", "3711", "5876"]
OFFSETS = [(60, 1), (48, 12), (36, 12), (24, 12), (12, 12), (0, 12)]
RECEIPT = Path("/tmp/drl01-valuation-5y.json")


def checked(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (data.get("intent") != "drl01-official-twse-focus-five-year-valuation"
            or data.get("approved") is not True
            or data.get("no_new_provider") is not True
            or data.get("no_owner_mutation") is not True
            or data.get("no_job_template_mutation") is not True
            or data.get("symbols") != SYMBOLS
            or data.get("target_end") != "2026-10"
            or data.get("target_start") != "2021-10"
            or not re.fullmatch(r"[a-f0-9]{40}", str(data.get("deployed_sha", "")))):
        raise ValueError("invalid_drl01_valuation_scope")
    return data


def job_digest_matches(commit_sha: str, existing_job: dict) -> bool:
    """Never send new valuation-only env to an older image that ignores it."""
    container = existing_job["template"]["template"]["containers"]
    if len(container) != 1:
        return False
    image = container[0].get("image", "")
    if not image.startswith("ghcr.io/tommylin15/janus-ingestion-core@sha256:"):
        return False
    result = subprocess.run(
        ["skopeo", "inspect", "--no-creds",
         f"docker://ghcr.io/tommylin15/janus-ingestion-core:sha-{commit_sha}"],
        capture_output=True, text=True, timeout=70, check=False,
    )
    if result.returncode:
        return False
    digest = json.loads(result.stdout).get("Digest")
    return bool(digest and image.endswith("@" + digest))


def log_receipt(execution_name: str) -> dict | None:
    query = ('resource.type="cloud_run_job" AND '
             'labels."run.googleapis.com/execution_name"="' + execution_name + '"')
    for attempt in range(5):
        process = subprocess.run(
            ["gcloud", "logging", "read", query, "--project=" + PROJECT,
             "--limit=150", "--format=json"],
            capture_output=True, text=True, timeout=55, check=False,
        )
        if process.returncode == 0:
            for line in json.loads(process.stdout):
                value = line.get("jsonPayload")
                if not isinstance(value, dict):
                    try:
                        value = json.loads(line.get("textPayload", ""))
                    except (ValueError, TypeError):
                        continue
                if isinstance(value, dict) and value.get("operation") == "valuation_history" and "symbols" in value:
                    return value
        time.sleep(4 + attempt)
    return None


def save(report: dict):
    RECEIPT.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"operation":"drl01-valuation-five-year", "status":report["status"],
                      "completed_slices":len(report["slices"]), "remaining_slices":
                      len(OFFSETS)-len(report["slices"])}, sort_keys=True), flush=True)


def run(path: str):
    request = checked(path)
    report = {"schema_version":"drl01-valuation-backfill.v1",
              "deployed_sha":request["deployed_sha"],
              "symbols": SYMBOLS, "scope":"TWSE equity only; bond ETFs PE/PB N/A",
              "no_job_template_mutation":True, "no_owner_mutation":True,
              "slices":[], "status":"PARTIAL"}
    save(report)
    current = job(JOB)
    if not job_digest_matches(request["deployed_sha"], current):
        report["status"] = "BLOCKED_IMAGE_SHA_MISMATCH"
        save(report)
        raise RuntimeError(report["status"])
    container = current["template"]["template"]["containers"][0]
    if container.get("command") not in (None, [], ["python"]):
        raise ValueError("unexpected_ingestion_entrypoint")
    for offset, count in OFFSETS:
        # All Jobs (including Controller and Private) need to be terminal
        # before a new write. Do not blindly redispatch an unknown operation.
        wait_for_terminal_executions(timeout=700)
        current = job(JOB)
        if not job_digest_matches(request["deployed_sha"], current):
            raise RuntimeError("job_image_changed_during_backfill")
        expected_months = []
        ending = 2026*12 + 10 - 1 - offset
        for value in range(ending-count+1, ending+1):
            y,m = divmod(value,12)
            expected_months.append(f"{y}-{m+1:02d}")
        options = {
            "JANUS_DATA_SUPPLEMENT_MODE":"valuation-history",
            "JANUS_DATA_SUPPLEMENT_SYMBOLS":",".join(SYMBOLS),
            "JANUS_VALUATION_HISTORY_MONTHS":str(count),
            "JANUS_VALUATION_HISTORY_OFFSET":str(offset),
            "QUEUE_CONSUMER":"false",
            "MART_JOB":"",
        }
        overrides = {"env":[{"name":key,"value":value} for key,value in options.items()]}
        if container.get("name"):
            overrides["name"] = container["name"]
        operation = cloud(f"{ROOT}/jobs/{JOB}:run",
            {"etag":current["etag"], "overrides":{
                "taskCount":1, "timeout":"1800s",
                "containerOverrides":[overrides]}}, "POST")
        name = operation.get("name", "")
        if not name.startswith(ROOT + "/operations/"):
            raise RuntimeError("unknown_submission_do_not_retry")
        end = time.monotonic()+1860
        while not operation.get("done") and time.monotonic()<end:
            time.sleep(10)
            operation=cloud(name)
        if not operation.get("done") or operation.get("error"):
            raise RuntimeError("valuation_execution_unknown_do_not_retry")
        execution=operation.get("response", {})
        if not terminal(execution) or execution.get("succeededCount") != 1 or execution.get("failedCount", 0):
            raise RuntimeError("valuation_job_not_successful")
        execution_name=execution.get("name", "").rsplit("/",1)[-1]
        if not execution_name.startswith(JOB + "-"):
            raise ValueError("invalid_valuation_execution_identity")
        observed=log_receipt(execution_name)
        if observed is None:
            raise RuntimeError("valuation_receipt_missing")
        received=observed.get("valuation_periods_requested")
        if received != expected_months or observed.get("symbols") != SYMBOLS:
            raise RuntimeError("valuation_receipt_scope_drift")
        relevant=[x for x in observed.get("failures",[]) if x.get("dataset")=="valuation"]
        slice_info={
            "offset":offset, "months":expected_months,
            "execution":execution_name,
            "core_created":observed.get("core_created"),
            "core_updated":observed.get("core_updated"),
            "core_reused":observed.get("core_reused"),
            "snapshot_ref":observed.get("core_snapshot_id"),
            "valuation_failures":len(relevant),
            "failed_pairs":[[x.get("symbol"),x.get("period"),x.get("reason")] for x in relevant][:80],
            "receipt_status":observed.get("status"),
        }
        report["slices"].append(slice_info)
        save(report)
    report["status"]=("SOURCE_BACKFILL_PASS" if len(report["slices"])==len(OFFSETS)
         and not any(s["valuation_failures"] for s in report["slices"])
         else "PARTIAL_SOURCE_GAPS")
    save(report)
    if report["status"] != "SOURCE_BACKFILL_PASS":
        raise RuntimeError("drl01_valuation_source_gaps_need_review")


if __name__ == "__main__":
    if len(sys.argv)!=2:
        raise SystemExit("requires one versioned request")
    run(sys.argv[1])
