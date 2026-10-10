"""B8 governed ML/OOS backend choice: PyIceberg default, BQ opt-in only.

This module is deliberately IO-free. Calling workloads provide fixed-Core readers,
Parquet validation and an audit sink. An operational BQ failure can fall back;
identity/provenance/fidelity failures MUST fail closed, never hide data corruption.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_BACKEND = "pyiceberg"
BIGQUERY_ALLOWED_WORKLOAD = "ml-oos"
MAX_BILLED_BYTES = 1_073_741_824
QUERY_TIMEOUT_SECONDS = 60


class BigQueryOperationalError(RuntimeError):
    """Explicitly classified backend unavailability (NOT an identity/data error)."""

    def __init__(self, code: str):
        if code not in {"timeout", "unavailable", "permission_denied", "quota"}:
            raise ValueError("unsupported operational failure class")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class BackendResult:
    data: Any
    audit: dict[str, Any]


def backend_for(workload: str, requested: str | None = None, *,
                bigquery_opt_in: bool = False) -> str:
    """Never select BigQuery for screening or by default."""
    requested = requested or DEFAULT_BACKEND
    if requested == DEFAULT_BACKEND:
        return requested
    if (requested == "bigquery" and workload == BIGQUERY_ALLOWED_WORKLOAD
            and bigquery_opt_in):
        return requested
    raise ValueError("BigQuery is opt-in for ML/OOS only; PyIceberg remains default")


def check_fixed_core(identity: dict[str, Any]) -> None:
    """A reproducible identity must be present *before* any attempt."""
    source = identity.get("source_tables", {})
    table = source.get("core.ohlcv_v1") if isinstance(source, dict) else None
    if (not re.fullmatch(r"sha256:[0-9a-f]{64}", str(identity.get("core_snapshot_id", "")))
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(identity.get("core_manifest_sha256", "")))
            or not isinstance(table, dict) or not table.get("snapshot_id")
            or not str(table.get("metadata_location", "")).startswith("gs://")
            or not identity.get("analysis_as_of")
            or not identity.get("date_bounds")
            or identity.get("label_horizon_trading_days") != 20
            or identity.get("cohort_stride_trading_days") != 5
            or not all(identity.get(k) for k in (
                "dataset_schema_version", "query_contract_version",
                "feature_version", "model_version"))):
        raise ValueError("ML/OOS immutable Core, PIT or source fence is invalid")


def execute_ml_oos(
    *,
    identity: dict[str, Any],
    workload: str = "ml-oos",
    requested_backend: str | None = None,
    bigquery_opt_in: bool = False,
    pyiceberg_worker: Callable[[], Any],
    bigquery_worker: Callable[[], Any] | None = None,
    verify: Callable[[Any], None],
) -> BackendResult:
    """Run a single fixed-Core operation, or operational-only fallback.

    Caller MUST use exact snapshot IDs, validate row/PIT/provenance and NOT
    promote any partial BigQuery output. verify() raising never triggers fallback.
    Returns sanitized audit only after verified output; no raw errors or tokens.
    """
    check_fixed_core(identity)
    backend = backend_for(workload, requested_backend, bigquery_opt_in=bigquery_opt_in)
    audit: dict[str, Any] = {
        "workload": workload, "requested_backend": backend,
        "default_backend": DEFAULT_BACKEND, "source_core_snapshot_id": identity["core_snapshot_id"],
        "source_table_snapshot_id": identity["source_tables"]["core.ohlcv_v1"]["snapshot_id"],
        "analysis_as_of": identity["analysis_as_of"],
        "cutover": False, "canonical_write": False,
        "cache_promotion": False, "storage_read_api_used": False,
        "budget_bytes": MAX_BILLED_BYTES, "query_timeout_seconds": QUERY_TIMEOUT_SECONDS,
        "fallback_triggered": False, "fallback_status": "not_needed",
        "operational_failure_code": None, "effective_backend": None,
    }
    if backend == DEFAULT_BACKEND:
        result = pyiceberg_worker()
        verify(result)
        audit["effective_backend"] = DEFAULT_BACKEND
        return BackendResult(result, audit)
    if bigquery_worker is None:
        raise ValueError("explicit BigQuery worker required for opt-in")
    try:
        result = bigquery_worker()
    except BigQueryOperationalError as error:
        audit["operational_failure_code"] = error.code
        audit["fallback_triggered"] = True
        # No BigQuery repeat. Avoid using any partial BigQuery output.
        # The PyIceberg worker MUST re-read the exact pinned Core snapshot.
        result = pyiceberg_worker()
        verify(result)
        audit["effective_backend"] = DEFAULT_BACKEND
        audit["fallback_status"] = "validated"
        audit["partial_bigquery_artifact_policy"] = "quarantined_not_promoted"
        return BackendResult(result, audit)
    verify(result)  # Identity/PIT/parity failures MUST NOT fall back.
    audit["effective_backend"] = "bigquery"
    return BackendResult(result, audit)
