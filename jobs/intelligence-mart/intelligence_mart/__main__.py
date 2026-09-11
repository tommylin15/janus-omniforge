"""One-shot Intelligence Mart Cloud Run Job entrypoint."""

from __future__ import annotations

import json
import sys
import os

from .runtime import postgres_smoke, run_queued_analysis


def main() -> None:
    try:
        operation = run_queued_analysis if os.environ.get("MART_OPERATION") == "queue" else postgres_smoke
        print(json.dumps(operation(), sort_keys=True))
    except Exception as error:
        print(
            json.dumps({"component": "intelligence-mart", "status": "failed", "error": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
