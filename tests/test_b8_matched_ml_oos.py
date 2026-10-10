"""B8 PyIceberg vs immutable B5 BigQuery export, independent SQL-reduction checks."""
import runpy
from datetime import date, timedelta
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))
module = runpy.run_path(str(ROOT / "scripts/gcp/b8-matched-ml-oos.py"))
reduce_rows = module["reduce_ohlcv"]
compare = module["compare_ml_oos_rows"]


def identity(size=50):
    end = date(2026, 10, 6)
    return {
        "date_bounds": [(end - timedelta(days=size - 1)).isoformat(), end.isoformat()],
        "analysis_as_of": end.isoformat(), "core_snapshot_id": "sha256:pinned",
        "dataset_schema_version": "b5-ml-oos-v1",
        "query_contract_version": "b5-sql-reduction-v1",
        "feature_version": "2", "model_version": "deterministic-v1",
    }


def source_rows(size=50):
    end = date(2026, 10, 6)
    return [
        {"symbol": "2330", "trade_date": end - timedelta(days=size - 1 - i),
         "close": str(100 + i), "volume_shares": str(1000 + i),
         "turnover_twd": str(10000 + i),
         "source_id": "twse", "provenance_id": "p" + str(i)}
        for i in range(size)
    ]


def test_independent_b5_window_stride_and_label_maturity():
    result = reduce_rows(source_rows(), identity())
    assert len(result) == 2
    assert result[0]["trade_date"] == source_rows()[20]["trade_date"]
    assert result[0]["label_maturity_date"] == source_rows()[40]["trade_date"]
    assert result[1]["trade_date"] == source_rows()[25]["trade_date"]
    assert all(r["label_maturity_date"] <= date(2026, 10, 6) for r in result)
    assert result[0]["return_5d"] == pytest.approx(120 / 115 - 1)
    assert result[0]["label_return_20d"] == pytest.approx(140 / 120 - 1)
    assert compare(result, list(reversed(result)))["equal"] is True


def test_bad_labels_never_use_future_rows():
    assert reduce_rows(source_rows(40), identity(40)) == []


def test_duplicate_symbol_date_fails_closed_before_window_compare():
    rows = source_rows()
    with pytest.raises(ValueError, match="duplicate symbol/date"):
        reduce_rows(rows + [dict(rows[3])], identity())


def test_provenance_and_null_differences_are_not_numeric_tolerance():
    record = reduce_rows(source_rows(), identity())[0]
    same = dict(record, return_5d=record["return_5d"] + 1e-11)
    assert compare([record], [same])["equal"] is True
    assert compare([record], [dict(record, provenance_id="wrong")])["equal"] is False
    assert compare([dict(record, volume_shares=None)],
                   [dict(record, volume_shares="None")])["equal"] is False


def test_key_and_schema_drift_fail_closed():
    rows = reduce_rows(source_rows(), identity())
    assert compare(rows, rows[:-1])["different_keys"] == 1
    assert compare(rows, [dict(x, extra="unknown") for x in rows])["changed_rows"] == len(rows)
