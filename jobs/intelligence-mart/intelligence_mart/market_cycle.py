"""Bounded market work on the existing Mart Job, without a second schedule."""
import os
from time import monotonic


def run():
    from .market_screening import run_daily
    from .runtime import run_queued_analysis
    started = monotonic()
    screening = run_daily() if os.getenv("SCREENING_DATE", "").strip() else None
    analyses = []
    # Do not hold a controller or create one Cloud Run execution per stock.
    for _ in range(8):
        if monotonic() - started >= 900:
            break
        result = run_queued_analysis()
        if not result.get("claimed"):
            if result.get("status") != "idle":
                raise RuntimeError("analysis queue returned an unclaimed non-idle state")
            break
        analyses.append(result)
        if result.get("status") != "succeeded":
            # Keep the durable retry/failed state visible and stop this bounded drain.
            break
    incomplete = any(item.get("status") != "succeeded" for item in analyses)
    return {"component": "intelligence-mart", "operation": "market-cycle",
            "status": "partial" if incomplete else "succeeded", "screening": screening, "analyses": analyses,
            "queue_drain_bounded": True, "llm_api_tokens": 0}
