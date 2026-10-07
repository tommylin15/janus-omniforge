"""Cloud Run Job entrypoint for Private Mart."""

from __future__ import annotations

from datetime import date
import json
import os

from packages.postgres_bundle import load_postgres_bundle

from .mobile_ledger_consumer import MobileLedgerQueueError, probe_mobile_ledger_consumer, process_mobile_ledger_queue
from .private_pipeline import CorePriceReader, PrivatePipeline, resolve_valuation_date
from .private_recalc_queue import run_queue_worker
from .repository import NotFoundError, PostgresWorkspaceRepository, repository_from_env
from .store import PrivateIcebergStore


def main() -> None:
    if os.getenv("MOBILE_LEDGER_PROBE_ONLY", "").strip().lower() == "true":
        load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
            "PRIVATE_DATABASE_URL": ("pipeline_database_url", "database_url"),
        })
        repository = repository_from_env()
        try:
            result = probe_mobile_ledger_consumer(repository)
        except MobileLedgerQueueError as error:
            print(json.dumps({"mobile_ledger_probe": "failed", "error_code": str(error)}, sort_keys=True))
            raise
        except NotFoundError:
            print(json.dumps({"mobile_ledger_probe": "failed", "error_code": "OWNER_BINDING"}, sort_keys=True))
            raise
        print(json.dumps(result, sort_keys=True))
        return

    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "PRIVATE_DATABASE_URL": ("pipeline_database_url", "database_url"),
        "MOBILE_LEDGER_DATABASE_URL": "database_url",
        "PRIVATE_CATALOG_PASSWORD": ("pipeline_catalog_password", "catalog_password"),
        "CORE_CATALOG_PASSWORD": "core_catalog_password",
    })
    repository = repository_from_env()
    try:
        process_mobile_ledger_queue(PostgresWorkspaceRepository(os.environ["MOBILE_LEDGER_DATABASE_URL"]))
    except (MobileLedgerQueueError, NotFoundError):
        pass
    market = CorePriceReader.from_env()
    override = os.getenv("VALUATION_DATE") or None
    pipeline = PrivatePipeline(
        repository,
        PrivateIcebergStore.from_env(),
        market,
        market.memberships,
        lambda: resolve_valuation_date(None, market.latest_valuation_date),
    )
    execution_name = os.getenv("CLOUD_RUN_EXECUTION") or None
    if os.getenv("PRIVATE_RECALC_QUEUE_MODE", "").strip().lower() == "true":
        result = run_queue_worker(repository, pipeline)
        print(json.dumps({"private_recalc_queue": result}, sort_keys=True))
        return
    try:
        completed = pipeline.run(date.fromisoformat(override) if override else None)
    except Exception:
        try:
            repository.record_pipeline_status(
                valuation_date=pipeline.last_valuation_date,
                result="failed",
                execution_name=execution_name,
            )
        except Exception:
            print("private pipeline aggregate status write failed")
        raise
    repository.record_pipeline_status(
        valuation_date=pipeline.last_valuation_date,
        result="succeeded",
        execution_name=execution_name,
    )
    print(f"private pipeline checkpoint={completed}")


if __name__ == "__main__":
    main()
