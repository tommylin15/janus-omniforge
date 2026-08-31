"""One-shot Intelligence Mart Cloud Run Job entrypoint."""

from __future__ import annotations

import json
import sys

from .runtime import postgres_smoke


def main() -> None:
    try:
        print(json.dumps(postgres_smoke(), sort_keys=True))
    except Exception as error:
        print(
            json.dumps({"component": "intelligence-mart", "status": "failed", "error": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
