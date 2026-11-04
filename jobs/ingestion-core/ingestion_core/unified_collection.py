"""One existing ingestion worker: supplements, ETF identities, canonical ready event."""
import os


def run():
    from .__main__ import run_scheduled_collection
    from .stock_supplement import run_pending
    from .etf_catalog_sync import run_weekly

    if os.getenv("MART_JOB", "").strip():
        raise ValueError("unified collection must leave dispatch to the Controller")
    demand = run_pending(daily=True) if os.getenv("JANUS_STOCK_SUPPLEMENT_ENABLED", "true").lower() == "true" else None

    etf_catalog = {"status": "disabled"}
    if os.getenv("JANUS_ETF_CATALOG_SYNC_ENABLED", "true").lower() == "true":
        try:
            etf_catalog = run_weekly()
        except Exception as error:
            # Catalogue discovery never invalidates already-collected market data.
            # Missing/newly incompatible migration is reported, not silently passed.
            etf_catalog = {"status": "unavailable", "error_code": type(error).__name__[:64]}
    collection = run_scheduled_collection()
    failed = collection.get("status") != "succeeded"
    failed = failed or (demand is not None and demand.get("status") in {"partial", "failed", "retrying"})
    return {"component": "ingestion-core", "operation": "unified-collection",
            "status": "partial" if failed else collection.get("status", "unknown"),
            "collection": collection, "stock_supplement": demand,
            "etf_catalog": etf_catalog}
