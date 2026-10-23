"""Snapshot-fenced, target-only 8-feature OHLCV input and per-stock quality.

This is a separate bounded scan, not the general Specialist/multi-dataset scan.
No read of owner positions, no market-wide materialization, and no forward-fill.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from .analytics_reader import IcebergSnapshotReader
from .risk_shadow import _eligible_price_rows
from research.colab.risk_pilot import make_risk_panel
from research.colab.risk_v1 import V1_FEATURES, add_v1_features

TABLE = "core.ohlcv_v1"
LOOKBACK_CALENDAR_DAYS = 220  # >90 trading days even with ordinary closures
MAX_ROWS_PER_SYMBOL = 230  # hard fail instead of silently truncating input
FIELDS = (
    "symbol", "market", "trade_date", "open", "high", "low", "close",
    "volume_shares", "turnover_twd", "source_id", "provenance_id",
    "quality_flag", "source_authorization", "published_at",
    "availability_at", "is_corporate_action",
)


def risk_read_plan(core, as_of, symbols):
    """Exact 1-table pinned snapshot; reject empty/unscoped market reads."""
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("Risk requires unique nonempty target ordinary symbols")
    if len(symbols) > 50:
        raise ValueError("Risk target-only read exceeds selected-union budget")
    if core.get("analysis_as_of") != as_of:
        raise ValueError("Risk read date does not match pinned Core date")
    tables = core.get("iceberg_tables", {})
    if TABLE not in tables or tables[TABLE].get("snapshot_id") is None:
        raise ValueError("Risk pinned OHLCV snapshot missing")
    first = (date.fromisoformat(as_of) - timedelta(days=LOOKBACK_CALENDAR_DAYS)).isoformat()
    plan = {**core, "iceberg_tables": {TABLE: tables[TABLE]}}
    if "datasets" in core:
        plan["datasets"] = {"ohlcv": core["datasets"].get("ohlcv", [])}
    return plan, (TABLE, "trade_date", first, as_of)


def read_risk_ohlcv(core, as_of, symbols, snapshot_id, *, catalog_factory):
    plan, (table, date_field, start, end) = risk_read_plan(core, as_of, symbols)
    reader = IcebergSnapshotReader(
        catalog_factory(),
        date_bounds={table: (date_field, start, end)},
        selected_fields={table: FIELDS},
    )
    try:
        result = reader.read(plan, tuple(sorted(symbols)), core_snapshot_id=snapshot_id,
                             row_limit=len(symbols) * MAX_ROWS_PER_SYMBOL)
    finally:
        reader.close()
    rows = result.datasets.get("ohlcv", [])
    # Embedded fixture manifests and some PyIceberg backends may omit filter
    # pushdown. Enforce the same immutable scope and period after reading.
    if any(row.get("symbol") not in symbols or not start <= str(row.get("trade_date", ""))[:10] <= end
           for row in rows):
        raise ValueError("Risk read returned out-of-scope stock or date")
    return rows, {
        "core_snapshot_id": snapshot_id, "table": TABLE,
        "iceberg_snapshot_id": plan["iceberg_tables"][TABLE]["snapshot_id"],
        "period_start": start, "period_end": end,
        "selected_ordinary_target_count": len(symbols),
        "rows_read": len(rows), "bound_rows_per_symbol": MAX_ROWS_PER_SYMBOL,
        "row_filter_evidence": result.telemetry.get("scan_evidence", {}).get("ohlcv", {}),
    }


def risk_quality_report(rows, as_of, symbols, snapshot_id):
    """Private audit of exact per-symbol gaps; no owner held/watchlist flags."""
    expected = sorted(set(symbols))
    if len(expected) != len(symbols):
        raise ValueError("duplicate Risk quality target")
    prices, rejected = _eligible_price_rows(rows, as_of)
    observed = sorted(str(x)[:10] for x in prices["trade_date"].unique()) if not prices.empty else []
    report = []
    if not prices.empty:
        frames = add_v1_features(make_risk_panel(
            prices, market_sessions={m: observed for m in sorted(prices.market.unique())}))
    else:
        frames = None
    for symbol in expected:
        scoped = prices[prices.symbol == symbol] if not prices.empty else None
        dates = sorted(str(v)[:10] for v in scoped.trade_date.unique()) if scoped is not None and len(scoped) else []
        latest = dates[-1] if dates else None
        missing_evidenced = sorted(set(observed[-61:]) - set(dates))
        valid = None
        if frames is not None:
            at = frames.loc[frames.symbol.eq(symbol) & frames.trade_date.eq(as_of)]
            if len(at) == 1:
                valid = at.iloc[0]
        missing_features = [name for name in V1_FEATURES
                            if valid is None or pd.isna(valid[name])]
        state = "READY" if not missing_features and latest == as_of else "WINDOW_INCOMPLETE"
        report.append({
            "symbol": symbol, "latest_accepted_trade_date": latest,
            "accepted_trading_dates": len(dates),
            "required_recent_sessions": 61,
            "observed_recent_missing_dates": missing_evidenced,
            "missing_features": missing_features,
            "feature_count": len(V1_FEATURES) - len(missing_features),
            "rejected_input_row_count": sum(1 for item in rejected if item == symbol),
            "status": state,
        })
    return {
        "artifact_kind": "mart_risk_8factor_quality_v1",
        "analysis_as_of": as_of, "core_snapshot_id": snapshot_id,
        "session_calendar_provenance": "SAME_PINNED_CORE_OBSERVED_COHORT_NOT_OFFICIAL",
        "ordinary_targets": len(expected),
        "ready_symbols": sum(x["status"] == "READY" for x in report),
        "rows": report,
        "owner_fields_exposed": False,
    }
