"""One existing ingestion worker: supplements, ETF identities, canonical ready event."""
import os


def run():
    from .__main__ import run_scheduled_collection
    from .corporate_actions_sync import run_daily as sync_corporate_actions
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

    corporate_actions = {"status": "disabled"}
    if os.getenv("JANUS_CORPORATE_ACTIONS_SYNC_ENABLED", "true").lower() == "true":
        try:
            corporate_actions = sync_corporate_actions()
        except Exception as error:
            # 除權息同步失敗不得影響主盤後收盤資料採集
            corporate_actions = {"status": "unavailable", "error_code": type(error).__name__[:64]}

    collection = run_scheduled_collection()
    failed = collection.get("status") != "succeeded"
    failed = failed or (demand is not None and demand.get("status") in {"partial", "failed", "retrying"})
    return {"component": "ingestion-core", "operation": "unified-collection",
            "status": "partial" if failed else collection.get("status", "unknown"),
            "collection": collection, "stock_supplement": demand,
            "etf_catalog": etf_catalog, "corporate_actions": corporate_actions}
