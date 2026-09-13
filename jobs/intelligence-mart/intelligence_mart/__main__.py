"""One-shot Intelligence Mart Cloud Run Job entrypoint."""

from __future__ import annotations

import json
import sys
import os
from time import monotonic

from .runtime import postgres_smoke, run_queued_analysis


def main() -> None:
    started = monotonic()
    try:
        operation = run_queued_analysis if os.environ.get("MART_OPERATION") == "queue" else postgres_smoke
        result = operation()
        result["duration_ms"] = round((monotonic() - started) * 1000)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(
            json.dumps({"component": "intelligence-mart", "status": "failed",
                        "error_code": type(error).__name__.upper()[:64],
                        "duration_ms": round((monotonic() - started) * 1000)}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
