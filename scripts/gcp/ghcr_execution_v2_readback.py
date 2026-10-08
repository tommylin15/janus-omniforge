#!/usr/bin/env python3
"""Read only v2 Cloud Run control-plane state for bounded unresolved executions.

Do not infer terminal success from 0 tasks, False condition, or a missing
start time. OAuth access token stays in subprocess memory; no token/headers,
env, owner payload, logUri or raw Cloud Run JSON is written to evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
JOB = "janus-private-pipeline"
EXECUTION_RE = re.compile(r"^janus-private-pipeline-[a-z0-9-]+$")
MAX_UNRESOLVED = 20
API_BASE = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}/jobs/{JOB}/executions"


def classify(execution: str, data: object) -> dict:
    """Sanitize v2 output; never promote Job safety on an ambiguous response."""
    result = {
        "execution": execution,
        "v2_readback": "UNKNOWN_OR_BLOCKED",
        "readback_reason": "INVALID_EXECUTION_OR_PAYLOAD",
        "reconciling": None,
        "start_observed": None,
        "completion_observed": None,
        "running_count": None,
        "task_count": None,
        "condition_states": [],
        "terminal_confirmed": False,
        "terminal_outcome": "UNKNOWN",
    }
    if not EXECUTION_RE.fullmatch(execution) or not isinstance(data, dict):
        return result
    if data.get("name") != f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}/executions/{execution}":
        result["readback_reason"] = "RESOURCE_NAME_MISMATCH"
        return result
    if data.get("job") not in (None, JOB, f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}"):
        result["readback_reason"] = "JOB_SCOPE_MISMATCH"
        return result
    # Cloud Run v2 uses protobuf JSON: an omitted bool is its default False,
    # not an unknown schema. Explicit null/string still fail closed.
    if "reconciling" in data and not isinstance(data["reconciling"], bool):
        result["readback_reason"] = "RECONCILING_FIELD_BAD"
        return result
    reconciling = data.get("reconciling", False)
    if not isinstance(data.get("conditions"), list):
        result["readback_reason"] = "CONDITIONS_FIELD_ABSENT_OR_BAD"
        return result
    if data.get("startTime") is not None and not isinstance(data["startTime"], str):
        return result
    if data.get("completionTime") is not None and not isinstance(data["completionTime"], str):
        return result
    counters = {}
    for field in ("runningCount", "taskCount"):
        val = data.get(field)
        if val is not None and (not isinstance(val, int) or isinstance(val, bool) or val < 0):
            return result
        counters[field] = val
    conds = []
    for cond in data["conditions"]:
        if not isinstance(cond, dict):
            return result
        kind, state = cond.get("type"), cond.get("state")
        if not isinstance(kind, str) or not isinstance(state, str):
            return result
        if not re.fullmatch(r"[a-zA-Z_]{1,40}", kind) or not re.fullmatch(r"[A-Z_]{1,40}", state):
            return result
        reason = cond.get("executionReason")
        if reason is not None and (
            not isinstance(reason, str) or not re.fullmatch(r"[A-Z_]{1,64}", reason)
        ):
            return result
        conds.append({"type": kind, "state": state, "execution_reason": reason})
    # Official Cloud Run v2 Condition.State defines CONDITION_FAILED as a
    # *terminal reconciliation failure*. An execution can fail before any
    # tasks are instantiated and have no completionTime; such a terminal
    # failure must never be presented as success or as an active task.
    completed = [c for c in conds if c["type"] == "Completed"]
    bad_reasons = {"JOB_STATUS_SERVICE_POLLING_ERROR", "CANCELLING",
                   "DELAYED_START_PENDING"}
    terminal_failed = (
        not reconciling and len(completed) == 1
        and completed[0]["state"] == "CONDITION_FAILED"
        and completed[0]["execution_reason"] not in bad_reasons
        and counters["runningCount"] in (None, 0)
    )
    terminal_succeeded = (
        not reconciling and bool(data.get("completionTime"))
        and len(completed) == 1
        and completed[0]["state"] == "CONDITION_SUCCEEDED"
        and counters["runningCount"] in (None, 0)
    )
    result.update(
        v2_readback="READABLE",
        readback_reason="NONE",
        reconciling=reconciling,
        start_observed=bool(data.get("startTime")),
        completion_observed=bool(data.get("completionTime")),
        running_count=counters["runningCount"],
        task_count=counters["taskCount"],
        condition_states=conds[:10],
        terminal_confirmed=terminal_failed or terminal_succeeded,
        terminal_outcome=("FAILED_TERMINAL_CONDITION" if terminal_failed else
                          "SUCCEEDED_TERMINAL_CONDITION" if terminal_succeeded else "UNKNOWN"),
    )
    # Terminal failed reconciliation is not a successful Job, and never
    # authorizes retry/cancel/delete/image mutation without a separate fence.
    return result


def read_only_v2(execution: str, access_token: str) -> dict:
    if not EXECUTION_RE.fullmatch(execution):
        return classify(execution, None)
    url = f"{API_BASE}/{execution}"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        method="GET")
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            if response.status != 200:
                return classify(execution, None)
            # Do not log the raw response, which may include labels or template env.
            data = json.loads(response.read(524288))
            return classify(execution, data)
    except urllib.error.HTTPError as exc:
        result = classify(execution, None)
        result["readback_reason"] = f"HTTP_{exc.code}" if 400 <= exc.code <= 599 else "HTTP_UNKNOWN"
        return result
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        result = classify(execution, None)
        result["readback_reason"] = "TRANSPORT_OR_BODY_UNREADABLE"
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executions-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        names = [x.strip() for x in args.executions_file.read_text().splitlines()]
    except OSError:
        names = []
    if (not names or len(names) > MAX_UNRESOLVED or
            len(set(names)) != len(names) or any(not EXECUTION_RE.fullmatch(x) for x in names)):
        print(json.dumps({"status": "BLOCKED", "reason": "invalid_bounded_execution_inventory",
                          "resource_writes": 0}))
        return 78
    try:
        token = subprocess.run(
            ["gcloud", "auth", "print-access-token"], capture_output=True,
            text=True, timeout=30, check=False,
        )
        secret = token.stdout.strip() if token.returncode == 0 else ""
        if not secret or "\n" in secret:
            rows = [classify(name, None) for name in names]
        else:
            rows = [read_only_v2(name, secret) for name in names]
        print(json.dumps({
            "scope": "cloud_run_v2_read_only_execution_status",
            "expected_count": len(names),
            "records": rows,
            "all_readable": all(x["v2_readback"] == "READABLE" for x in rows),
            "all_terminal_confirmed": all(x["terminal_confirmed"] is True for x in rows),
            "resource_writes": 0,
            "cancel_executions": False,
            "authorize_job_promotion": False,
        }, sort_keys=True))
        return 0
    except (subprocess.TimeoutExpired, OSError):
        print(json.dumps({"scope": "cloud_run_v2_read_only_execution_status",
                          "status": "BLOCKED", "reason": "identity_token_unavailable",
                          "resource_writes": 0}))
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
