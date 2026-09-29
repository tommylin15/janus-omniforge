"""Cloud Run Job entrypoint for Private Mart."""

from __future__ import annotations

from datetime import date
import os

from packages.postgres_bundle import load_postgres_bundle

from .private_pipeline import CorePriceReader, PrivatePipeline, resolve_valuation_date
from .repository import repository_from_env
from .store import PrivateIcebergStore


def main() -> None:
    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "PRIVATE_DATABASE_URL": ("pipeline_database_url", "database_url"),
        "PRIVATE_CATALOG_PASSWORD": ("pipeline_catalog_password", "catalog_password"),
        "CORE_CATALOG_PASSWORD": "core_catalog_password",
    })
    repository = repository_from_env()
    retired_count = repository.retire_offlist_watchlist()
    market = CorePriceReader.from_env()
    override = os.getenv("VALUATION_DATE") or None
    completed = PrivatePipeline(
        repository,
        PrivateIcebergStore.from_env(),
        market,
        market.memberships,
        lambda: resolve_valuation_date(None, market.latest_valuation_date),
    ).run(date.fromisoformat(override) if override else None)
    print(f"private pipeline checkpoint={completed} offlist_watchlist_retired={retired_count}")


if __name__ == "__main__":
    main()
