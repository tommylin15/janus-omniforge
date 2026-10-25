"""MOPS Core XBRL rows to the frozen Valuation v26 five-slot X contract.

Core normalises XBRL money to TWD; research source was MOPS thousands,
so log(total_assets TWD) equals research log(assets * 1000).
No PIT timestamps or accounting values are inferred.
"""
from __future__ import annotations
from datetime import date
import math

FEATURES = ("roe_proxy", "debt_ratio", "log_total_assets", "revenue_yoy", "market_code")
VERSION = "valuation-v26-mops-ytd-v1"
REQUIRED = {
    "total_assets_snapshot": ("balance", "snapshot"),
    "total_liabilities_snapshot": ("balance", "snapshot"),
    "total_equity_snapshot": ("balance", "snapshot"),
    "net_income_year_to_date": ("income", "year_to_date"),
    "revenue_year_to_date": ("income", "year_to_date"),
}


def build_v26_features(rows, *, symbol, market, as_of):
    until = date.fromisoformat(as_of)
    market_code = {"twse": 0.0, "tpex": 1.0}.get(str(market).lower())
    values = {name: None for name in FEATURES}
    values["market_code"] = market_code
    grouped, times = {}, {}
    for row in rows:
        metric = row.get("metric")
        if (str(row.get("symbol")) != symbol or row.get("source_id") != "mops"
                or (row.get("market") or market) != market
                or row.get("report_scope") != "consolidated"
                or row.get("currency", "TWD") != "TWD" or row.get("unit") != "TWD"
                or metric not in REQUIRED
                or (row.get("statement_type"), row.get("period_basis")) != REQUIRED[metric]):
            continue
        try:
            year, quarter = int(row["fiscal_year"]), int(row["fiscal_quarter"])
            if quarter not in (1, 2, 3, 4) or year < 2010:
                continue
            quarter_end = date(year, quarter * 3, (31, 30, 30, 31)[quarter - 1])
            available = str(row.get("availability_at") or row.get("published_at") or "")[:10]
            if quarter_end > until or not available or date.fromisoformat(available) > until:
                continue
            value = float(row["value"])
            if not math.isfinite(value):
                continue
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        period = (year, quarter)
        grouped.setdefault(period, {}).setdefault(metric, set()).add(value)
        times.setdefault(period, set()).add(available)
    input_as_of, reasons = None, ["missing_unambiguous_comparable_mops_quarters"]
    for (year, quarter), part in sorted(grouped.items(), reverse=True):
        last_year = (year - 1, quarter)
        prior = grouped.get(last_year, {}).get("revenue_year_to_date", set())
        if any(len(part.get(k, ())) != 1 for k in REQUIRED) or len(prior) != 1:
            continue
        a = next(iter(part["total_assets_snapshot"]))
        l = next(iter(part["total_liabilities_snapshot"]))
        e = next(iter(part["total_equity_snapshot"]))
        n = next(iter(part["net_income_year_to_date"]))
        revenue = next(iter(part["revenue_year_to_date"]))
        base = next(iter(prior))
        if a <= 0 or e <= 0 or l < 0 or base <= 0:
            continue
        features = {
            "roe_proxy": n / e,
            "debt_ratio": l / a,
            "log_total_assets": math.log(a),
            "revenue_yoy": revenue / base - 1,
            "market_code": market_code,
        }
        if not all(v is not None and math.isfinite(v) for v in features.values()):
            continue
        values, reasons = features, []
        input_as_of = max(times[(year, quarter)] | times[last_year])
        break
    missing = [k for k, v in values.items() if v is None]
    return {
        "feature_order": list(FEATURES), "values": values,
        "missing_features": missing, "input_as_of": input_as_of,
        "feature_version": VERSION, "feature_ready": not missing,
        "model_compatible": "SCHEMA_MAPPED_NOT_LIVE_VALIDATED",
        "reasons": reasons, "publication_authority": False,
        "source_accounting": "MOPS_consolidated_YTD_income_snapshot_balance_TWD",
    }
