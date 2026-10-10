"""B8 equal-run benchmark safety and comparison guard tests (offline)."""
from datetime import date
from pathlib import Path
import runpy
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "jobs/intelligence-mart")]
bench = runpy.run_path(str(ROOT / "scripts/gcp/b8-ml-oos-equal-run.py"))
old = runpy.run_path(str(ROOT / "scripts/gcp/b8-matched-ml-oos.py"))


def test_phase_order_has_both_bq_and_reference_cold_warm():
    assert bench["path_order"]() == (
        ("pyiceberg", "cold"), ("bigquery-export", "cold"),
        ("bigquery-export", "warm"), ("pyiceberg", "warm"),
    )


def test_research_prefix_is_new_and_not_a_b5_cache_key():
    prefix = bench["output_prefix"]("gen-lang-client-0593591102-dev-mart", "a" * 32, "cold")
    assert prefix.startswith("gs://gen-lang-client-0593591102-dev-mart/b8-ml-oos-benchmark/v1/")
    assert "/ml-oos-data/" not in prefix
    for run, phase in (("abc", "cold"), ("b" * 32, "../cached"), ("", "warm")):
        with pytest.raises(ValueError):
            bench["output_prefix"]("bucket", run, phase)


def test_reason_classification_avoids_raw_gcp_error():
    assert bench["safe_reason"](RuntimeError("HTTP 403 token xxx")) == "permission_denied"
    assert bench["safe_reason"](TimeoutError("aborted")) == "timeout"
    assert bench["safe_reason"](RuntimeError("unknown private identifier")) == "unknown"


def test_parquet_roundtrip_nulls_and_schema_protected():
    import pyarrow as pa
    import pyarrow.parquet as pq
    import io
    record = {
        "symbol": "2330", "trade_date": date(2026, 4, 1),
        "return_5d": 0.01, "return_20d": 0.03,
        "log_turnover_twd": None, "volume_shares": 300.0,
        "label_return_20d": 0.1, "label_maturity_date": date(2026, 4, 29),
        "source_id": "twse", "provenance_id": "orig", "core_snapshot_id": "sha256:frozen",
        "analysis_as_of": "2026-10-06", "dataset_schema_version": "b5-ml-oos-v1",
        "query_contract_version": "b5-sql-reduction-v1", "feature_version": "2",
        "model_version": "deterministic-v1",
    }
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist([record]), buf)
    from intelligence_mart.ml_oos_data import REQUIRED_COLUMNS, FORBIDDEN_COLUMNS
    got = bench["restore_parquet"](buf.getvalue(), REQUIRED_COLUMNS, FORBIDDEN_COLUMNS)
    assert old["compare_ml_oos_rows"]([record], got)["equal"]
    with pytest.raises(ValueError, match="schema"):
        bench["restore_parquet"](buf.getvalue(), REQUIRED_COLUMNS | {"private_field"}, FORBIDDEN_COLUMNS)


def test_no_partial_or_cache_promote_behavior_in_source():
    src = (ROOT / "scripts/gcp/b8-ml-oos-equal-run.py").read_text()
    assert "ifGenerationMatch=0" not in src  # no B5 cached manifest writer
    assert "overwrite=false" in src
    assert "ml_retraining_triggered" in src
    assert "b8_export_reduced" in src
