"""B8 operational routing, fallback, PIT-fence and fail-closed governance."""
from __future__ import annotations
import pytest

from intelligence_mart.ml_oos_backend_policy import (
    BigQueryOperationalError, backend_for, check_fixed_core, execute_ml_oos,
)


def identity():
    return {
        "core_snapshot_id": "sha256:" + "a" * 64,
        "core_manifest_sha256": "sha256:" + "b" * 64,
        "source_tables": {"core.ohlcv_v1": {
            "snapshot_id": 123,
            "metadata_location": "gs://core-bucket/metadata/immutable.metadata.json"}},
        "analysis_as_of": "2026-10-06",
        "date_bounds": ["2026-02-07", "2026-10-06"],
        "label_horizon_trading_days": 20,
        "cohort_stride_trading_days": 5,
        "dataset_schema_version": "b5-ml-oos-v1",
        "query_contract_version": "b5-sql-reduction-v1",
        "feature_version": "2", "model_version": "deterministic-v1",
    }


def test_default_never_queries_bigquery():
    calls = []
    def py():
        calls.append("py")
        return {"rows": 10}
    outcome = execute_ml_oos(identity=identity(), pyiceberg_worker=py,
                             verify=lambda result: None)
    assert calls == ["py"]
    assert outcome.audit["effective_backend"] == "pyiceberg"
    assert not outcome.audit["fallback_triggered"]
    assert not outcome.audit["cutover"]


def test_screening_cannot_be_routed_bigquery():
    assert backend_for("market-screening") == "pyiceberg"
    with pytest.raises(ValueError, match="opt-in"):
        backend_for("market-screening", "bigquery", bigquery_opt_in=True)
    with pytest.raises(ValueError, match="opt-in"):
        backend_for("ml-oos", "bigquery")


def test_optional_bigquery_success_only_after_verification():
    order = []
    outcome = execute_ml_oos(
        identity=identity(), requested_backend="bigquery", bigquery_opt_in=True,
        pyiceberg_worker=lambda: order.append("py"),
        bigquery_worker=lambda: (order.append("bq"), {"snapshot": "ok"})[1],
        verify=lambda x: order.append("verify") if x["snapshot"] == "ok" else None)
    assert order == ["bq", "verify"]
    assert outcome.audit["effective_backend"] == "bigquery"
    assert not outcome.audit["fallback_triggered"]


def test_transient_backend_failure_executes_fresh_py_once():
    order = []
    def bq():
        order.append("bq")
        raise BigQueryOperationalError("permission_denied")
    def py():
        order.append("py")
        return {"snapshot": identity()["core_snapshot_id"], "row_count": 10978}
    def verify(x):
        order.append("verify")
        assert x["snapshot"] == identity()["core_snapshot_id"]
        assert x["row_count"] == 10978
    r = execute_ml_oos(
        identity=identity(), requested_backend="bigquery", bigquery_opt_in=True,
        pyiceberg_worker=py, bigquery_worker=bq, verify=verify)
    assert order == ["bq", "py", "verify"]
    assert r.audit["fallback_status"] == "validated"
    assert r.audit["operational_failure_code"] == "permission_denied"
    assert r.audit["partial_bigquery_artifact_policy"] == "quarantined_not_promoted"
    assert r.audit["effective_backend"] == "pyiceberg"
    assert not r.audit["cache_promotion"]


@pytest.mark.parametrize("error", [ValueError("Core drift"), RuntimeError("provenance mismatch")])
def test_identity_and_data_errors_do_not_fallback(error):
    def bq():
        raise error
    with pytest.raises(type(error)):
        execute_ml_oos(
            identity=identity(), requested_backend="bigquery", bigquery_opt_in=True,
            pyiceberg_worker=lambda: pytest.fail("identity error must not invoke fallback"),
            bigquery_worker=bq, verify=lambda x: None)


def test_bigquery_bad_data_fails_closed_without_fallback():
    with pytest.raises(ValueError, match="fidelity"):
        execute_ml_oos(
            identity=identity(), requested_backend="bigquery", bigquery_opt_in=True,
            pyiceberg_worker=lambda: pytest.fail("fidelity mismatch must not fallback"),
            bigquery_worker=lambda: {"untrusted": True},
            verify=lambda x: (_ for _ in ()).throw(ValueError("fidelity mismatch")))


@pytest.mark.parametrize("key,value", [
    ("core_snapshot_id", "latest"), ("core_manifest_sha256", ""),
    ("date_bounds", None), ("label_horizon_trading_days", 21),
    ("cohort_stride_trading_days", 3),
])
def test_missing_or_weakened_pit_fence_fails_before_io(key, value):
    bad = identity()
    bad[key] = value
    with pytest.raises(ValueError):
        check_fixed_core(bad)
    with pytest.raises(ValueError):
        execute_ml_oos(
            identity=bad, pyiceberg_worker=lambda: pytest.fail("no IO before fence"),
            verify=lambda x: None)


def test_fallback_failure_does_not_return_success():
    def bq():
        raise BigQueryOperationalError("timeout")
    with pytest.raises(ValueError, match="maturity"):
        execute_ml_oos(identity=identity(), requested_backend="bigquery",
                       bigquery_opt_in=True, bigquery_worker=bq,
                       pyiceberg_worker=lambda: {"bad": "data"},
                       verify=lambda _: (_ for _ in ()).throw(ValueError("maturity mismatch")))


def test_unknown_operational_error_code_cannot_mask_corruption():
    with pytest.raises(ValueError, match="unsupported"):
        BigQueryOperationalError("data_mismatch")
