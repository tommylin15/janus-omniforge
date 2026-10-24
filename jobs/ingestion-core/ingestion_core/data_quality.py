"""Independent deterministic supplement checks; only safe results reach Admin."""
from decimal import Decimal, InvalidOperation
from .data_supplement import coverage_summary
from .dq import ALLOWED_COLUMNS, validate_ohlcv


def assess_rows(financial, prices, symbols, target):
    coverage = coverage_summary(financial, prices, symbols, target)
    issues, versions = [], {}
    checked_prices = validate_ohlcv(({k: v for k, v in row.items() if k in ALLOWED_COLUMNS} for row in prices), analysis_as_of=target)
    for row, violations in checked_prices.quarantined:
        for violation in violations:
            issues.append({"symbol": row["symbol"], "dataset": "ohlcv", "period": str(row.get("trade_date", "")),
                           "field": violation.field, "reason": violation.code})
    for symbol, item in coverage.items():
        for dataset, field, minimum in (("financials", "financial_quarters", 12),
                                         ("monthly-revenue", "revenue_months", 12),
                                         ("ohlcv", "price_trading_dates", 121)):
            if item[field] < minimum:
                issues.append({"symbol": symbol, "dataset": dataset, "field": field,
                               "reason": "history_incomplete", "period": ""})
    for row in financial:
        if not row.get("source_document_sha256") or row.get("source_id") != "mops":
            continue
        identity = (row["symbol"], row["fiscal_year"], row["fiscal_quarter"], row["statement_type"], row["metric"], str(row.get("version_at")))
        expected = "percent" if row["metric"].endswith("_yoy_percent_same_filing") else "TWD_per_share" if row["metric"].startswith("eps_") else "TWD"
        reason = None
        try:
            if not Decimal(str(row.get("value"))).is_finite():
                reason = "invalid_numeric_value"
        except (InvalidOperation, ValueError):
            reason = "invalid_numeric_value"
        if row.get("unit") != expected or row.get("currency") != "TWD":
            reason = "unit_mismatch"
        if not row.get("availability_at"):
            reason = "missing_receipt_time"
        value = (str(row.get("value")), row.get("unit"), row.get("period_basis"), row.get("report_scope"))
        if identity in versions and versions[identity] != value:
            reason = "conflicting_version"
        versions[identity] = value
        if reason:
            period = f'{row["fiscal_year"]}-{row["fiscal_month"]:02d}' if row.get("fiscal_month") else f'{row["fiscal_year"]}Q{row["fiscal_quarter"]}'
            issues.append({"symbol": row["symbol"], "dataset": "monthly-revenue" if row.get("fiscal_month") else "financials",
                           "field": row["metric"], "period": period, "reason": reason})
    return coverage, issues


def run_quality():
    """Retired research audit: no database, HTTP, model or GCS operations."""
    return {"status": "skipped", "reason": "research_audit_retired_20261024",
            "source_checks": 0, "model_calls": 0,
            "needs_daily_schedule_adjustment": False}
