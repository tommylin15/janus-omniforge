"""One existing ingestion worker: supplements first, then the canonical ready event."""
import os


def run():
    from .__main__ import run_scheduled_collection
    from .stock_supplement import run_pending
    if os.getenv("MART_JOB", "").strip():
        raise ValueError("unified collection must leave dispatch to the Controller")
    demand = run_pending(daily=True) if os.getenv("JANUS_STOCK_SUPPLEMENT_ENABLED", "true").lower() == "true" else None
    collection = run_scheduled_collection()
    failed = collection.get("status") != "succeeded"
    failed = failed or (demand is not None and demand.get("status") in {"partial", "failed", "retrying"})
    return {"component": "ingestion-core", "operation": "unified-collection",
            "status": "partial" if failed else collection.get("status", "unknown"),
            "collection": collection, "stock_supplement": demand}
