"""One-shot Intelligence Mart provider-enabled Cloud Run Job entrypoint."""

from __future__ import annotations

import json
import os
import sys
from time import monotonic

from .ai_providers import provider_smoke, run_provider_queued_analysis
from .compat import build_compatibility_sidecar, validate_compatibility_sidecar
from .runtime import postgres_smoke


def compatibility_smoke() -> dict[str, object]:
    interpretation_hash = "sha256:" + "1" * 64
    report = {"schema_version": "1.1.0", "execution_id": "compat-smoke", "analysis_as_of": "2026-09-30",
              "core_snapshot_id": "compat-smoke-core", "scope": {"type": "symbol", "id": "2330"},
              "deterministic_hash": "sha256:" + "2" * 64}
    references = [
        {"artifact_kind": "mart_ai_interpretation_v1", "role": "fundamental", "artifact_hash": interpretation_hash,
         "artifact_uri": "gs://janus-runtime-smoke/compat/interpretation.json", "status": "schema_validated",
         "output_contract_version": "1.0.0"},
        {"artifact_kind": "mart_ai_validation_v1", "role": "fundamental", "artifact_hash": "sha256:" + "3" * 64,
         "artifact_uri": "gs://janus-runtime-smoke/compat/validation.json", "status": "validated",
         "validator_version": "role-validator-v1", "source_artifact_hash": interpretation_hash,
         "publication_authority": False},
    ]
    sidecar = validate_compatibility_sidecar(build_compatibility_sidecar(report, references), report)
    return {"component": "intelligence-mart", "status": "ok", "operation": "compat-smoke",
            "schema_version": sidecar["schema_version"], "artifact_count": len(sidecar["artifacts"]),
            "publication_authority": sidecar["publication_authority"]}


def main() -> None:
    started = monotonic()
    try:
        name = os.environ.get("MART_OPERATION", "").strip().lower()
        if name == "retention":
            from .retention import run
            operation = run
        else:
            operation = run_provider_queued_analysis if name == "queue" else provider_smoke if name == "provider-smoke" else compatibility_smoke if name == "compat-smoke" else postgres_smoke
        result = operation(); result["duration_ms"] = round((monotonic() - started) * 1000)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(json.dumps({"component": "intelligence-mart", "status": "failed", "error_code": type(error).__name__.upper()[:64],
                          "duration_ms": round((monotonic() - started) * 1000)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
