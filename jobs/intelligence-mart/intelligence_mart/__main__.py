"""One-shot deterministic Intelligence Mart Cloud Run Job."""
import json
import os
import sys
import traceback
from time import monotonic
from .runtime import postgres_smoke, run_queued_analysis


def specialist_smoke():
    from .specialists import DEPENDENCIES, analyze_specialists
    artifacts = analyze_specialists({}, "2330", "2026-10-03", "smoke")
    assert {a["role"] for a in artifacts} == set(DEPENDENCIES)
    assert all(a["llm_api_tokens"] == 0 and not a["publication_authority"] for a in artifacts)
    return {"component": "intelligence-mart", "status": "ok", "operation": "specialist-smoke",
            "roles": sorted(DEPENDENCIES), "llm_api_tokens": 0}


def main():
    started = monotonic()
    # Exact-SHA release readiness requires migration 051 before this image can
    # execute. Direct processor unit tests retain their explicit opt-in boundary.
    os.environ.setdefault('MART_PRODUCT_PROJECTION', 'true')
    try:
        name = os.environ.get("MART_OPERATION", "").strip().lower()
        if name == "risk-activation":
            from .risk_activation_runtime import run_risk_activation
            operation = run_risk_activation
        elif name == "ceo-request":
            from .product_runtime import run_ceo_request
            operation = run_ceo_request
        elif name == "retention":
            from .retention import run
            operation = run
        elif name == "queue":
            operation = run_queued_analysis
        elif name == "specialist-smoke":
            operation = specialist_smoke
        elif name == "specialist-acceptance":
            from .specialist_runtime import run_acceptance
            operation = run_acceptance
        elif name == "risk-target-acceptance":
            from .specialist_runtime import run_acceptance
            operation = lambda: run_acceptance(operation="risk-target-acceptance")
        elif name == "deep-coverage":
            from .specialist_runtime import run_deep_coverage
            operation = run_deep_coverage
        elif name == "market-cycle":
            from .market_cycle import run
            operation = run
        elif name == "market-screening":
            from .market_screening import run_daily
            operation = run_daily
        elif name == "market-screening-acceptance":
            from .market_screening import run_acceptance
            operation = run_acceptance
        elif name in {"", "postgres-smoke"}:
            operation = postgres_smoke
        else:
            raise ValueError("unsupported Mart operation")
        result = operation()
        if result.get("status") in {"failed", "retrying", "partial"}:
            raise RuntimeError("Mart operation did not complete successfully")
        result["duration_ms"] = round((monotonic() - started) * 1000)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(json.dumps({"component": "intelligence-mart", "status": "failed",
                          "error_code": type(error).__name__.upper()[:64],
                          "locations": [{"function": frame.name, "line": frame.lineno,
                                         "file": os.path.basename(frame.filename)}
                                        for frame in traceback.extract_tb(error.__traceback__)]}), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
