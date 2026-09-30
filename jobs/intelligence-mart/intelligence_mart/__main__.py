"""One-shot Intelligence Mart Cloud Run Job entrypoint."""

from __future__ import annotations

import json
import sys
import os
from time import monotonic

from .compat import build_compatibility_sidecar, validate_compatibility_sidecar
from .runtime import postgres_smoke, run_queued_analysis


def compatibility_smoke() -> dict[str, object]:
    """Exercise the additive mart.v1 sidecar in the deployed container without writes."""
    interpretation_hash = "sha256:" + "1" * 64
    report = {
        "schema_version": "1.1.0",
        "execution_id": "compat-smoke",
        "analysis_as_of": "2026-09-30",
        "core_snapshot_id": "compat-smoke-core",
        "scope": {"type": "symbol", "id": "2330"},
        "deterministic_hash": "sha256:" + "2" * 64,
    }
    references = [
        {
            "artifact_kind": "mart_ai_interpretation_v1",
            "role": "fundamental",
            "artifact_hash": interpretation_hash,
            "artifact_uri": "gs://janus-runtime-smoke/compat/interpretation.json",
            "status": "schema_validated",
            "output_contract_version": "1.0.0",
        },
        {
            "artifact_kind": "mart_ai_validation_v1",
            "role": "fundamental",
            "artifact_hash": "sha256:" + "3" * 64,
            "artifact_uri": "gs://janus-runtime-smoke/compat/validation.json",
            "status": "validated",
            "validator_version": "role-validator-v1",
            "source_artifact_hash": interpretation_hash,
            "publication_authority": False,
        },
    ]
    sidecar = build_compatibility_sidecar(report, references)
    validated = validate_compatibility_sidecar(sidecar, report)
    return {
        "component": "intelligence-mart",
        "status": "ok",
        "operation": "compat-smoke",
        "schema_version": validated["schema_version"],
        "base_contract": validated["base"]["contract"],
        "base_contract_version": validated["base"]["contract_version"],
        "artifact_count": len(validated["artifacts"]),
        "publication_authority": validated["publication_authority"],
    }


def main() -> None:
    started = monotonic()
    try:
        operation_name = os.environ.get("MART_OPERATION", "").strip().lower()
        if operation_name == "queue":
            operation = run_queued_analysis
        elif operation_name == "compat-smoke":
            operation = compatibility_smoke
        else:
            operation = postgres_smoke
        result = operation()
        result["duration_ms"] = round((monotonic() - started) * 1000)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(
            json.dumps({"component": "intelligence-mart", "status": "failed",
                        "error_code": type(error).__name__.upper()[:64],
                        "duration_ms": round((monotonic() - started) * 1000)}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
