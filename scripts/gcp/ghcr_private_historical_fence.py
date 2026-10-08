#!/usr/bin/env python3
"""Fail-closed reconciliation of nine known pre-task Cloud Run failures.

Three independent fresh control-plane readbacks are required:
v1 execution descriptions, task lists including succeeded, and REST v2
terminal conditions. This proves *no active task*, not successful processing.
Never cancel, retry, delete, pause Scheduler, or authorize Job image updates.
"""
from __future__ import annotations

from typing import Any

KNOWN_FAILED_PRETASK = frozenset({
    "janus-private-pipeline-7rkz7",
    "janus-private-pipeline-5hzdn",
    "janus-private-pipeline-nz2cl",
    "janus-private-pipeline-wdx6q",
    "janus-private-pipeline-kbvj9",
    "janus-private-pipeline-rcjr7",
    "janus-private-pipeline-4mtr6",
    "janus-private-pipeline-glwzh",
    "janus-private-pipeline-fhfsg",
})


def _by_name(rows: Any, key: str) -> dict[str, dict] | None:
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return None
    entries = {}
    for row in rows:
        name = row.get(key)
        if not isinstance(name, str) or name in entries:
            return None
        entries[name] = row
    return entries


def verified_failed_count(
    v1_records: Any, task_records: Any, v2_readback: Any, potentially_active: Any,
    diagnostics: list[str] | None = None,
) -> int:
    """Only return nine if *all* prescribed historical failures are proven."""
    def _reject(reason: str) -> int:
        if diagnostics is not None:
            diagnostics.append(reason)
        return 0
    if not isinstance(potentially_active, int) or isinstance(potentially_active, bool):
        return _reject("invalid_active_count")
    if potentially_active != len(KNOWN_FAILED_PRETASK):
        return _reject("active_count_not_exactly_nine")
    a = _by_name(v1_records, "execution")
    b = _by_name(task_records, "execution")
    if not isinstance(v2_readback, dict):
        return _reject("invalid_v2_payload")
    c = _by_name(v2_readback.get("records"), "execution")
    if (a is None or b is None or c is None
            or any(set(rows) != KNOWN_FAILED_PRETASK for rows in (a,b,c))
            or v2_readback.get("expected_count") != len(KNOWN_FAILED_PRETASK)
            or v2_readback.get("all_readable") is not True
            or v2_readback.get("all_terminal_confirmed") is not True
            or v2_readback.get("authorize_job_promotion") is not False
            or v2_readback.get("cancel_executions") is not False
            or v2_readback.get("resource_writes") != 0):
        return _reject("readback_identity_or_batch_mismatch")
    for name in KNOWN_FAILED_PRETASK:
        v1, task, v2 = a[name], b[name], c[name]
        created = v1.get("created")
        if (v1.get("describe_status") != "READABLE"
                or not isinstance(created, str)
                or not ("2026-09-01" <= created[:10] < "2026-10-01")
                or v1.get("started") is not None
                or v1.get("completed") is not None
                or v1.get("runningCount") != 0
                or v1.get("succeededCount") != 0
                or v1.get("failedCount") != 0
                or v1.get("cancelledCount") != 0):
            return _reject("v1_preflight_failed")
        conds = v1.get("conditions")
        if (not isinstance(conds, list) or len(conds) != 1
                or conds[0].get("type") != "Completed"
                or str(conds[0].get("status")) != "False"):
            return _reject("v1_completed_condition_mismatch")
        if (task.get("task_readback") != "READABLE_BOUNDED"
                or task.get("tasks_scanned") != 0
                or task.get("tasks_started") != 0
                or task.get("tasks_completed") != 0
                or task.get("terminal_confirmed") is not False):
            return _reject("task_state_mismatch")
        cstate = v2.get("condition_states")
        if (v2.get("v2_readback") != "READABLE"
                or v2.get("readback_reason") != "NONE"
                or v2.get("reconciling") is not False
                or v2.get("start_observed") is not False
                or v2.get("completion_observed") is not False
                or v2.get("running_count") not in (None, 0)
                or v2.get("task_count") != 1
                or v2.get("terminal_confirmed") is not True
                or v2.get("terminal_outcome") != "FAILED_TERMINAL_CONDITION"
                or not isinstance(cstate, list) or len(cstate) != 1
                or cstate[0].get("type") != "Completed"
                or cstate[0].get("state") != "CONDITION_FAILED"
                or cstate[0].get("execution_reason") in (
                    "JOB_STATUS_SERVICE_POLLING_ERROR",
                    "CANCELLING", "DELAYED_START_PENDING",
                )):
            return _reject("v2_terminal_failure_mismatch")
    return len(KNOWN_FAILED_PRETASK)
