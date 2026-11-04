"""Weekly ETF identity maintenance piggybacking on the existing ingestion job."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.etf_catalog import EtfCatalogUnavailable, weekly_official_catalogue


def run_weekly() -> dict[str, object]:
    from .__main__ import _control_plane

    control = _control_plane()
    try:
        with control._tx() as cur:
            cur.execute("SELECT last_success_at FROM control.etf_catalog_sync_state WHERE singleton")
            state = cur.fetchone()
            if state is None:
                raise RuntimeError("ETF sync schema not installed")
            last = state[0]
            if last is not None and last > datetime.now(timezone.utc) - timedelta(days=7):
                return {"status": "skipped", "reason": "up_to_date"}

        # Fetching occurs outside a database transaction; old identities survive
        # even if either official market source is unavailable.
        records = weekly_official_catalogue()
        with control._tx() as cur:
            cur.execute(
                "SELECT last_success_at FROM control.etf_catalog_sync_state WHERE singleton FOR UPDATE"
            )
            refreshed = cur.fetchone()
            if refreshed and refreshed[0] is not None and (
                refreshed[0] > datetime.now(timezone.utc) - timedelta(days=7)
            ):
                return {"status": "skipped", "reason": "concurrent_sync"}
            for etf in records:
                cur.execute(
                    "SELECT control.register_verified_etf(%s,%s,%s,%s)",
                    (etf.symbol, etf.name, etf.market, etf.listed_on),
                )
            cur.execute(
                """UPDATE control.etf_catalog_sync_state
                   SET last_success_at=now(), last_count=%s, updated_at=now()
                   WHERE singleton""",
                (len(records),),
            )
        return {"status": "succeeded", "verified_count": len(records)}
    finally:
        control.close()
