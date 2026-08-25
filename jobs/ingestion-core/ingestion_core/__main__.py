"""Cloud Run Job entrypoint."""

from __future__ import annotations

import json


def main() -> None:
    print(json.dumps({"component": "ingestion-core", "status": "ready", "schema_version": "1.0.0"}))


if __name__ == "__main__":
    main()
