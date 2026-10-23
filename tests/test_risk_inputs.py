"""Risk only scans selected ordinary OHLCV in a frozen 220-day Core window."""
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.risk_inputs import (
    read_risk_ohlcv, risk_quality_report, risk_read_plan,
    FIELDS, MAX_ROWS_PER_SYMBOL, TABLE)


def fixture():
    source = []
    start = date(2026, 2, 1)
    for market, symbol in (("TWSE", "2330"), ("TPEX", "6488")):
        for i in range(137):
            day = start + timedelta(days=i)
            if day.weekday() >= 5:
                continue
            close = 100. + i * .13 + (i % 7) * .04
            source.append({
                "symbol": symbol, "market": market,
                "trade_date": day.isoformat(), "open": close * .999,
                "high": close * 1.015, "low": close * .985, "close": close,
                "volume_shares": 1000 + i, "turnover_twd": (1000 + i) * close,
                "source_id": market.lower(), "provenance_id": f"{symbol}-{i}",
                "quality_flag": "pass", "source_authorization": "approved",
            })
    as_of = max(row["trade_date"] for row in source)
    core = {
        "snapshot_id": "frozen-core-id",
        "analysis_as_of": as_of,
        "iceberg_tables": {
            TABLE: {"snapshot_id": 218},
            "core.financials_v1": {"snapshot_id": 992},
        },
        "datasets": {
            "ohlcv": [*source],
            "financials": [{"symbol": "9999", "fake": True} for _ in range(1000)],
        },
    }
    return core, as_of


def test_frozen_risk_plan_never_admits_financials_or_broad_market():
    core, as_of = fixture()
    plan, date_bound = risk_read_plan(core, as_of, ("2330", "6488"))
    assert list(plan["iceberg_tables"]) == [TABLE]
    assert list(plan["datasets"]) == ["ohlcv"]
    assert date_bound[1] == "trade_date"
    assert date_bound[-1] == as_of
    assert (date.fromisoformat(date_bound[-1])-date.fromisoformat(date_bound[2])).days == 220
    for bad in ((), ("2330", "2330"), tuple(str(i) for i in range(51))):
        with pytest.raises(ValueError):
            risk_read_plan(core, as_of, bad)
    with pytest.raises(ValueError, match="date"):
        risk_read_plan(core, "2028-01-01", ("2330",))


def test_only_selected_symbols_read_with_hard_row_budget_and_same_snapshot():
    core, as_of = fixture()
    class Catalog:
        engine = None
    result, telemetry = read_risk_ohlcv(
        core, as_of, ("2330",), "frozen-core-id", catalog_factory=Catalog)
    assert {r["symbol"] for r in result} == {"2330"}
    assert telemetry["selected_ordinary_target_count"] == 1
    assert telemetry["rows_read"] <= MAX_ROWS_PER_SYMBOL
    assert telemetry["core_snapshot_id"] == "frozen-core-id"
    assert len(FIELDS) > 8
    with pytest.raises(ValueError, match="identity mismatch"):
        read_risk_ohlcv(core, as_of, ("2330",), "wrong-id", catalog_factory=Catalog)
    # Embedded readers do not enforce date bounds. Post-read fencing catches
    # out-of-scope future or too-old Core content, rather than silently leaking.
    corrupted = dict(core)
    corrupted["datasets"] = {"ohlcv": [dict(result[-1], trade_date="2030-01-01")]}
    with pytest.raises(ValueError, match="out-of-scope"):
        read_risk_ohlcv(corrupted, as_of, ("2330",), "frozen-core-id", catalog_factory=Catalog)


def test_per_symbol_eight_factor_quality_does_not_fill_missing_session():
    core, as_of = fixture()
    rows = core["datasets"]["ohlcv"]
    receipt = risk_quality_report(rows, as_of, ("2330", "6488"), "frozen-core-id")
    assert receipt["ready_symbols"] == 2
    assert receipt["owner_fields_exposed"] is False
    assert all(x["feature_count"] == 8 for x in receipt["rows"])
    removed = next(r["trade_date"] for r in rows[-15:] if r["symbol"] == "6488")
    missing = [r for r in rows if not (r["symbol"] == "6488" and r["trade_date"] == removed)]
    receipt = risk_quality_report(missing, as_of, ("2330", "6488"), "frozen-core-id")
    assert receipt["ready_symbols"] == 1
    missing_symbol = next(r for r in receipt["rows"] if r["symbol"] == "6488")
    assert removed in missing_symbol["observed_recent_missing_dates"]
    assert missing_symbol["status"] == "WINDOW_INCOMPLETE"
    assert "vol60" in missing_symbol["missing_features"]
    assert not any("held" in item or "watchlisted" in item for item in receipt["rows"])
