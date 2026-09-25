"""Cloud Run entrypoint with bounded, secret-safe failure diagnostics."""

from __future__ import annotations

import json
import os
import sys
from time import monotonic
from typing import Any

from .__main__ import consume_queued_collection, run_scheduled_collection


def _failure_details(error: Exception) -> list[dict[str, str]]:
    """Return only allow-listed aggregate failure fields from collect_stage()."""
    if not isinstance(error, RuntimeError):
        return []
    try:
        payload = json.loads(str(error))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    failures = payload.get("failures") if isinstance(payload, dict) else None
    if not isinstance(failures, list):
        return []
    result: list[dict[str, str]] = []
    for item in failures[:20]:
        if not isinstance(item, dict):
            continue
        safe = {
            key: str(item[key])[:80]
            for key in ("dataset", "date", "error")
            if item.get(key) is not None
        }
        if safe:
            result.append(safe)
    return result


def main() -> None:
    started = monotonic()
    try:
        operation = (
            consume_queued_collection
            if os.environ.get("QUEUE_CONSUMER", "false").lower() in {"1", "true", "yes"}
            else run_scheduled_collection
        )
        result: dict[str, Any] = operation()
        result["duration_ms"] = round((monotonic() - started) * 1000)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except Exception as error:
        output: dict[str, Any] = {
            "component": "ingestion-core",
            "status": "failed",
            "error_code": type(error).__name__.upper()[:64],
            "duration_ms": round((monotonic() - started) * 1000),
        }
        failures = _failure_details(error)
        if failures:
            output["failures"] = failures
        print(json.dumps(output, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
