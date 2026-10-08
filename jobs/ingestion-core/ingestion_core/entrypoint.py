"""Thin ingestion entrypoint for allow-listed serving schema migrations."""

from __future__ import annotations

import json
import os
import sys
from time import monotonic


MIGRATION_RUNNER_VERSION = "2026-10-06.latest-price-v2"


def main() -> None:
    readiness = os.environ.get("JANUS_CICD_READINESS", "").strip()
    if readiness:
        if readiness not in {"check", "apply-missing"}:
            raise SystemExit("unsupported CI/CD readiness mode")
        from .__main__ import _control_plane
        from .serving_schema_migration import cicd_readiness
        control = _control_plane()
        try:
            result = cicd_readiness(control, apply_missing=readiness == "apply-missing")
            print(json.dumps(result, sort_keys=True))
        except Exception as error:
            print(json.dumps({"status": "failed", "operation": "cicd_readiness",
                              "error_code": type(error).__name__.upper()}), file=sys.stderr)
            raise SystemExit(1) from None
        finally:
            control.close()
        return
    migration = os.environ.get("JANUS_SERVING_SCHEMA_MIGRATION", "").strip()
    if not migration:
        from .runtime_entrypoint import main as runtime_main
        runtime_main()
        return

    started = monotonic()
    backfill: dict[str, object] | None = None
    stage = "bootstrap"
    try:
        from .__main__ import _control_plane
        from .serving_schema_migration import MIGRATION_STOCK_SERVING, SUPPORTED, run

        if migration not in SUPPORTED:
            raise ValueError("unsupported serving schema migration")
        stage = "control_connect"
        control = _control_plane()
        try:
            stage = "schema_migration"
            run(control, migration)
        finally:
            control.close()

        if migration == MIGRATION_STOCK_SERVING:
            from .__main__ import _iceberg_core
            from .serving_projection import StockServingProjection, backfill_recent

            core_bucket = os.environ.get("CORE_BUCKET", "").strip()
            if not core_bucket:
                raise ValueError("CORE_BUCKET is required for stock serving backfill")
            stage = "backfill_core_connect"
            core = _iceberg_core(core_bucket)
            try:
                stage = "backfill"
                backfill = backfill_recent(core, StockServingProjection.from_env())
            finally:
                core.close()

        payload: dict[str, object] = {
            "component": "ingestion-core",
            "status": "succeeded",
            "operation": "serving_schema_migration",
            "migration": migration,
            "runner_version": MIGRATION_RUNNER_VERSION,
            "duration_ms": round((monotonic() - started) * 1000),
        }
        if backfill is not None:
            payload["backfill"] = backfill
        print(json.dumps(payload, sort_keys=True))
    except Exception as error:
        failure_stage = str(getattr(error, "stage", stage))[:64]
        error_code = str(
            getattr(error, "error_code", type(error).__name__.upper())
        )[:64]
        payload = {
            "component": "ingestion-core",
            "status": "failed",
            "operation": "serving_schema_migration",
            "migration": migration,
            "runner_version": MIGRATION_RUNNER_VERSION,
            "stage": failure_stage,
            "error_code": error_code,
            "duration_ms": round((monotonic() - started) * 1000),
        }
        sqlstate = getattr(error, "sqlstate", None)
        if sqlstate:
            payload["sqlstate"] = str(sqlstate)[:16]
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
