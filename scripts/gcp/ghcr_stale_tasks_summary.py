#!/usr/bin/env python3
"""Bounded read-only Cloud Run execution task summary; no payload or task IDs.

This is evidence for resolving historical nonterminal executions, never an
authorization to cancel, delete, retry, or promote a Cloud Run Job. No observed
tasks does not mean an execution has a terminal status.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

EXECUTION_RE = re.compile(r"^janus-private-pipeline-[a-z0-9-]+$")
MAX_TASKS = 100


def inspect_tasks(execution: str, tasks: Any) -> dict[str, Any]:
    """Fail closed on unexpected task schema or pagination ambiguity."""
    if not EXECUTION_RE.fullmatch(execution):
        raise ValueError("invalid execution identifier")
    if not isinstance(tasks, list) or len(tasks) >= MAX_TASKS or any(
        not isinstance(item, dict) for item in tasks
    ):
        return {"execution": execution, "task_readback": "UNVERIFIABLE",
                "tasks_scanned": None, "tasks_started": None,
                "tasks_completed": None, "terminal_confirmed": False}
    started = 0
    completed = 0
    for item in tasks:
        status = item.get("status")
        if status is not None and not isinstance(status, dict):
            return {"execution": execution, "task_readback": "UNVERIFIABLE",
                    "tasks_scanned": None, "tasks_started": None,
                    "tasks_completed": None, "terminal_confirmed": False}
        state = status or {}
        if state.get("startTime") or item.get("startTime"):
            started += 1
        if state.get("completionTime") or item.get("completionTime"):
            completed += 1
    return {"execution": execution, "task_readback": "READABLE_BOUNDED",
            "tasks_scanned": len(tasks), "tasks_started": started,
            "tasks_completed": completed,
            # Only actual execution status can authorize terminal classification.
            "terminal_confirmed": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution", required=True)
    parser.add_argument("--tasks-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = inspect_tasks(args.execution, json.loads(args.tasks_json.read_text()))
    except (ValueError, OSError, UnicodeError):
        result = {"execution": args.execution if EXECUTION_RE.fullmatch(args.execution) else "INVALID",
                  "task_readback": "UNVERIFIABLE", "tasks_scanned": None,
                  "tasks_started": None, "tasks_completed": None,
                  "terminal_confirmed": False}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["task_readback"] == "READABLE_BOUNDED" else 78


if __name__ == "__main__":
    raise SystemExit(main())
