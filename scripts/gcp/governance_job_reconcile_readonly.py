#!/usr/bin/env python3
"""C1-A read-only Cloud Run execution reconciliation, tied to a bounded PG receipt.

No dispatch, launch, job updates, Scheduler mutation, owner data, or private rows.
PG control.executions and Cloud Run executions are DIFFERENT namespaces: only
a controller occurrence with an explicit Cloud Run execution is exact-joinable.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghcr_jobs_rollout as gcp

PG_RECEIPT = Path("governance-metadata-readonly-receipt.json")
OUTPUT = Path("governance-job-reconcile-readonly-receipt.json")
MAX_PAGES_PER_JOB = 12
PAGE_SIZE = 100
MAX_ACTIVE_REFS = 100
ALLOWED_JOBS = tuple(sorted(gcp.REQUIRED_JOBS))

def error_code(error):
    # Never print third-party exception messages, response bodies or tokens.
    msg = str(error)
    return msg if re.fullmatch(r"cloud_control_http_\d{3}", msg) else type(error).__name__[:64]

def utc(date):
    return datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(timezone.utc)

def cloud_state(item):
    if gcp.terminal(item):
        return ("SUCCEEDED" if item.get("succeededCount", 0) > 0 and
                not item.get("failedCount", 0) else "FAILED_OR_CANCELLED")
    return "NONTERMINAL"

def exact_controller_refs(rows):
    if len(rows) > MAX_ACTIVE_REFS:
        raise ValueError("controller_refs_exceed_cap")
    result = []
    for row in rows:
        if len(row) != 5:
            raise ValueError("invalid_controller_ref_shape")
        job, controller_state, batch, execution, scheduled_at = row
        if batch is not None and not re.fullmatch(r"[a-z0-9-]{1,64}",str(batch)):
            raise ValueError("controller_batch_identity_invalid")
        if job not in ALLOWED_JOBS or controller_state not in ("running","dispatching","ambiguous"):
            raise ValueError("controller_ref_outside_allowlist")
        record = {"job": job, "controller_state": controller_state, "batch": batch,
                  "scheduled_at": scheduled_at, "cloud_state": "NO_EXECUTION_REFERENCE"}
        if execution:
            # Exact resource names only; prevents arbitrary host/path queries.
            pattern = (re.escape(gcp.ROOT + "/jobs/" + job + "/executions/") +
                       r"[a-z0-9-]{1,128}")
            if not re.fullmatch(pattern, execution):
                raise ValueError("cloud_execution_ref_invalid")
            record["execution_ref_hash"] = sha256(execution.encode()).hexdigest()[:20]
            try:
                actual = gcp.cloud(execution)  # GET only
                if actual.get("name") != execution:
                    raise ValueError("cloud_execution_identity_mismatch")
                record["cloud_state"] = cloud_state(actual)
                record["cloud_create_time"] = actual.get("createTime")
            except Exception as error:
                record["cloud_state"] = "UNREADABLE"
                record["error_code"] = error_code(error)
        result.append(record)
    return result

def list_existing_job_executions(job, cutoff):
    if job not in ALLOWED_JOBS:
        raise ValueError("job_outside_allowlist")
    counts = Counter()
    max_create, page_token, complete = None, "", False
    scanned = 0
    for _ in range(MAX_PAGES_PER_JOB):
        suffix = "?pageSize=" + str(PAGE_SIZE)
        if page_token:
            import urllib.parse
            suffix += "&pageToken=" + urllib.parse.quote(page_token, safe="")
        response = gcp.cloud(gcp.ROOT + "/jobs/" + job + "/executions" + suffix)  # GET only
        for item in response.get("executions", []):
            name = str(item.get("name", ""))
            if not name.startswith(gcp.ROOT + "/jobs/" + job + "/executions/"):
                raise ValueError("job_execution_name_mismatch")
            stamp = item.get("createTime")
            if not stamp:
                raise ValueError("job_execution_create_time_missing")
            when = utc(stamp)
            if when < cutoff:
                # Listing is newest first; older records are outside requested window.
                complete = True
                break
            counts[cloud_state(item)] += 1
            scanned += 1
            if max_create is None or when > max_create:
                max_create = when
        if complete:
            break
        page_token = response.get("nextPageToken", "")
        if not page_token:
            complete = True
            break
    return {"job": job, "last_30d_by_cloud_state": dict(counts), "scanned": scanned,
            "most_recent_cloud_create_utc": max_create.isoformat() if max_create else None,
            "pagination_complete": complete}

def main():
    source_sha = os.environ.get("GITHUB_SHA", "")
    r = json.loads(PG_RECEIPT.read_text(encoding="utf-8"))
    if source_sha != r.get("source_git_sha"):
        raise ValueError("pg_receipt_sha_mismatch")
    required = ("control_execution_30d","control_nonterminal_lease_30d",
                "control_nonterminal_occurrence_link_30d","control_active_batch_occurrences_30d")
    if not all(r.get("sections", {}).get(key, {}).get("status") == "PASS" for key in required):
        raise ValueError("pg_active_reference_section_incomplete")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    controller = exact_controller_refs(
        r["sections"]["control_active_batch_occurrences_30d"]["items"])
    jobs = []
    for job in ALLOWED_JOBS:
        try:
            result = list_existing_job_executions(job, cutoff)
        except Exception as error:
            result = {"job": job, "error_code": error_code(error),
                      "pagination_complete": False, "last_30d_by_cloud_state": {}}
        jobs.append(result)
    statuses = Counter(x["cloud_state"] for x in controller)
    all_readable = (all(x["cloud_state"] != "UNREADABLE" for x in controller)
                    and all(x["pagination_complete"] for x in jobs))
    out = {"component": "janus_governance_c1a_job_reconcile_v1",
           "checked_at_utc": now.isoformat(), "source_git_sha": source_sha,
           "status": "PASS" if all_readable else "PARTIAL",
           "read_only": True, "data_mutations": 0, "iam_changes": 0,
           "new_resources": 0, "job_configuration_unchanged": True,
           "controller_active_refs": controller,
           "controller_cloud_state_counts": dict(statuses),
           "cloud_run_job_last_30d": jobs,
           "control_pg_lease_groups":
               r["sections"]["control_nonterminal_lease_30d"]["items"],
           "control_pg_occurrence_link_groups":
               r["sections"]["control_nonterminal_occurrence_link_30d"]["items"],
           "pg_to_cloud_full_row_join": "NOT_AVAILABLE_WITHOUT_EXPLICIT_OCCURRENCE_LINK"}
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True),
                      encoding="utf-8")
    print("JANUS_GOVERNANCE_C1A_JOB_RECONCILE_V1:" +
          json.dumps(out, ensure_ascii=False, sort_keys=True))
    if out["status"] != "PASS":
        raise RuntimeError("bounded_cloud_execution_readback_partial")

if __name__ == "__main__":
    main()
