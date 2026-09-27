"""Cloud Run Job entrypoint for Private Mart plus bounded market-coverage registration."""

from __future__ import annotations

from datetime import date
import os
from typing import Any

from packages.postgres_bundle import load_postgres_bundle

from .private_pipeline import CorePriceReader, PrivatePipeline, resolve_valuation_date
from .repository import repository_from_env
from .store import PrivateIcebergStore


def register_active_portfolio_market_coverage(repository: Any) -> tuple[int, int]:
    """Register only distinct active symbols; never move owner/quantity/cost into control plane."""
    with repository._connection() as connection:
        active_rows = connection.execute(
            """WITH reversed AS (
                 SELECT reverses_event_id FROM private.ledger_events
                 WHERE event_action='REVERSAL'
               ), positions AS (
                 SELECT e.user_id,e.symbol,e.currency,
                   SUM(CASE WHEN e.event_type IN ('BUY','STOCK_DIV') THEN e.shares
                            WHEN e.event_type='SELL' THEN -e.shares ELSE 0 END) AS shares
                 FROM private.ledger_events e
                 WHERE COALESCE(e.event_action,'')<>'REVERSAL'
                   AND NOT EXISTS (SELECT 1 FROM reversed r WHERE r.reverses_event_id=e.event_id)
                 GROUP BY e.user_id,e.symbol,e.currency
               )
               SELECT DISTINCT symbol FROM positions WHERE shares>0 ORDER BY symbol"""
        ).fetchall()
        requested = sorted(
            {str(row["symbol"]).strip().upper() for row in active_rows if str(row["symbol"]).strip()}
        )
        if not requested:
            return 0, 0
        accepted_rows = connection.execute(
            "SELECT symbol FROM control.request_portfolio_market_coverage(%s)",
            (requested,),
        ).fetchall()
    accepted = {
        str(row["symbol"]).strip().upper()
        for row in accepted_rows
        if str(row["symbol"]).strip()
    }
    return len(requested), len(accepted)


def main() -> None:
    load_postgres_bundle("JANUS_API_POSTGRES_BUNDLE", {
        "PRIVATE_DATABASE_URL": ("pipeline_database_url", "database_url"),
        "PRIVATE_CATALOG_PASSWORD": ("pipeline_catalog_password", "catalog_password"),
        "CORE_CATALOG_PASSWORD": "core_catalog_password",
    })
    repository = repository_from_env()
    market = CorePriceReader.from_env()
    override = os.getenv("VALUATION_DATE") or None
    completed = PrivatePipeline(
        repository,
        PrivateIcebergStore.from_env(),
        market,
        market.memberships,
        lambda: resolve_valuation_date(None, market.latest_valuation_date),
    ).run(date.fromisoformat(override) if override else None)
    requested_count, accepted_count = register_active_portfolio_market_coverage(repository)
    missing_count = requested_count - accepted_count
    coverage_status = "not_applicable" if not requested_count else "partial" if missing_count else "complete"
    missing_reason = "no_eligible_enabled_symbol_scoped_ohlcv_config" if missing_count else "none"
    print(
        "private pipeline "
        f"checkpoint={completed} portfolio_coverage_status={coverage_status} "
        f"portfolio_coverage_requested={requested_count} "
        f"portfolio_coverage_accepted={accepted_count} "
        f"portfolio_coverage_missing={missing_count} "
        f"portfolio_coverage_missing_reason={missing_reason}"
    )


if __name__ == "__main__":
    main()
