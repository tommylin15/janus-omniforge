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
    try:
        name = os.environ.get("MART_OPERATION", "").strip().lower()
        if name == "retention":
            from .retention import run
            operation = run
        elif name == "queue":
            operation = run_queued_analysis
        elif name == "specialist-smoke":
            operation = specialist_smoke
        elif name == "specialist-acceptance":
            from .specialist_runtime import run_acceptance
            operation = run_acceptance
        elif name == "specialist-baseline":
            from .specialist_runtime import run_baseline
            operation = run_baseline
        elif name == "specialist-retrain":
            from .specialist_runtime import run_retraining
            operation = run_retraining
        elif name in {"", "postgres-smoke"}:
            operation = postgres_smoke
        else:
            raise ValueError("unsupported Mart operation")
        result = operation()
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
