"""B8 matching/fidelity gates must fail closed before any default cutover."""
import runpy
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = runpy.run_path(str(ROOT / "scripts/gcp/b8-matched-screening.py"))
compare = NAMESPACE["compare_snapshots"]

from intelligence_mart.analytics_reader import AnalyticsSnapshot


def snapshot(rows, *, identity="sha256:fixed", source="pyiceberg"):
    return AnalyticsSnapshot(identity, {"ohlcv": rows}, {"source": source})


def row(symbol, *, close="100.00", provenance="official", published_at=None):
    return {
        "symbol": symbol, "trade_date": "2026-10-06", "close": close,
        "source_id": "twse", "provenance_id": provenance,
        "published_at": published_at, "__snapshot_id": 42,
        "__table_identifier": "core.ohlcv_v1",
    }


def test_row_order_is_not_a_fidelity_difference():
    first = snapshot([row("2330"), row("2317")])
    second = snapshot([row("2317"), row("2330")], source="bigquery")
    result = compare(first, second, core_identity="sha256:fixed")
    assert result["all_tables_equal"] is True
    assert result["tables"]["ohlcv"]["reference_rows"] == 2


@pytest.mark.parametrize("changed", [
    row("2330", close="100.01"),
    row("2330", provenance="unapproved"),
    row("2330", published_at="2026-10-07"),
    {**row("2330"), "close": None},
    {**row("2330"), "__snapshot_id": 43},
])
def test_fidelity_rejects_value_null_pit_and_provenance_drift(changed):
    result = compare(snapshot([row("2330")]), snapshot([changed], source="bigquery"),
                     core_identity="sha256:fixed")
    assert result["all_tables_equal"] is False


def test_missing_and_duplicate_rows_fail_closed():
    first = snapshot([row("2330"), row("2317")])
    for rows in ([row("2330")], [row("2330"), row("2330")]):
        result = compare(first, snapshot(rows), core_identity="sha256:fixed")
        assert result["all_tables_equal"] is False


def test_rejects_different_core_identity_and_table_scope():
    left = snapshot([row("2330")])
    with pytest.raises(ValueError, match="Core snapshot"):
        compare(left, snapshot([row("2330")], identity="sha256:other"),
                core_identity="sha256:fixed")
    with pytest.raises(ValueError, match="scope"):
        compare(left, AnalyticsSnapshot("sha256:fixed", {"benchmark": []}, {}),
                core_identity="sha256:fixed")
