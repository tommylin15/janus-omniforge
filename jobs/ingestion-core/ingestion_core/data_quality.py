"""Independent deterministic supplement checks; only safe results reach Admin."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import os
from urllib.parse import urlencode
from uuid import uuid4

from packages.provenance import Provenance
from .data_supplement import _fetch, _rows, coverage_summary, normalise_monthly_archive, supplement_symbols
from .financial_publication import normalise_xbrl_financials
from .dq import ALLOWED_COLUMNS, validate_ohlcv
from .stage import GcsObjectStore, StageWriter


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
    from .__main__ import _control_plane, _iceberg_core, TAIPEI
    today = datetime.now(TAIPEI).date()
    control, core = _control_plane(), None
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "status": "execution_failed",
              "needs_daily_schedule_adjustment": True, "issues": [], "source_checks": 0,
              "runbook_path": "doc/runbook-data-supplement.md", "model_calls": 0,
              "execution": os.environ.get("CLOUD_RUN_EXECUTION", "")}
    try:
        core = _iceberg_core(os.environ["CORE_BUCKET"])
        symbols = supplement_symbols(control)
        if not symbols or len(symbols) > 50:
            raise ValueError("quality check requires 1..50 targets")
        with control.connection.cursor() as cursor:
            cursor.execute("SELECT symbol,name,market FROM control.stock_master WHERE enabled AND symbol=ANY(%s)", (list(symbols),))
            names = {row[0]: row[1] for row in cursor.fetchall() if row[2] == "TWSE"}
        if set(names) != set(symbols) or not control.source_is_approved("mops"):
            raise ValueError("quality targets or source approval unavailable")
        financial = _rows(core, "financials", symbols)
        result["coverage"], result["issues"] = assess_rows(financial, _rows(core, "ohlcv", symbols), symbols, today-timedelta(days=1))
        writer = StageWriter(GcsObjectStore(os.environ["STAGE_BUCKET"]))
        execution = os.environ.get("CLOUD_RUN_EXECUTION") or str(uuid4())
        latest = {}
        for row in financial:
            if row.get("source_id") == "mops" and row.get("source_document_sha256"):
                key = (row["symbol"], row["fiscal_year"], row["fiscal_quarter"], row["statement_type"], row["metric"])
                if key not in latest or str(row.get("availability_at")) > str(latest[key].get("availability_at")):
                    latest[key] = row
        archives = {}
        for symbol in symbols:
            rows = [row for row in latest.values() if row["symbol"] == symbol]
            quarters = sorted({(r["fiscal_year"], r["fiscal_quarter"]) for r in rows if r["statement_type"] != "monthly_revenue"})[-1:]
            months = sorted({(r["fiscal_year"], r["fiscal_month"]) for r in rows if r.get("fiscal_month")})[-12:]
            for dataset, periods in (("financials", quarters), ("monthly-revenue", months)):
                for year, part in periods:
                    period = f"{year}Q{part}" if dataset == "financials" else f"{year}-{part:02d}"
                    try:
                        if dataset == "financials":
                            url = "https://mopsov.twse.com.tw/server-java/t164sb01?"+urlencode({"step": "1", "CO_ID": symbol, "SYEAR": year, "SSEASON": part, "REPORT_ID": "C"})
                            raw, _ = _fetch(url)
                            extension = "html"
                        else:
                            category = int("-KY" in names[symbol].upper())
                            url = f"https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{year-1911}_{part}_{category}.html"
                            if (year, part, category) not in archives:
                                archives[year, part, category] = _fetch(url)[0]
                            raw = archives[year, part, category]
                            extension = "html"
                        received = datetime.now(timezone.utc)
                        provenance = Provenance(str(uuid4()), "mops", url, "financials", received, None, received,
                                                "sha256:"+sha256(raw).hexdigest(), False,
                                                quality_details={"request_identity": {"symbol": symbol, "period": period, "kind": "quality_check"}})
                        writer.write_raw(payload=raw, media_type="text/html" if extension == "html" else "application/json",
                                         extension=extension, execution_id=execution, provenance=provenance)
                        checked = normalise_xbrl_financials(raw.decode("latin-1"), symbol, year, part, received_at=received.isoformat()) if dataset == "financials" else normalise_monthly_archive(raw, symbol, year, part, received_at=received.isoformat(), expected_name=names[symbol])
                        stored = {r["metric"]: r for r in rows if r["fiscal_year"] == year and
                                  (r.get("fiscal_month") == part if dataset == "monthly-revenue" else r["fiscal_quarter"] == part and r["statement_type"] != "monthly_revenue")}
                        for row in checked:
                            old = stored.get(row["metric"])
                            if old is None or Decimal(str(old.get("value"))) != Decimal(str(row.get("value"))) or any(old.get(k) != row.get(k) for k in ("unit", "period_basis", "report_scope")):
                                result["issues"].append({"symbol": symbol, "dataset": dataset, "period": period,
                                                         "field": row["metric"], "reason": "source_value_changed"})
                        result["source_checks"] += 1
                    except Exception as error:
                        result["issues"].append({"symbol": symbol, "dataset": dataset, "period": period,
                                                 "field": "source", "reason": "source_check_failed", "error_code": type(error).__name__})
        result.update(status="attention_required" if result["issues"] else "passed",
                      needs_daily_schedule_adjustment=bool(result["issues"]),
                      historical_publication_status="unknown", original_numeric_revision_status="unknown")
        control.put_admin_setting("data_supplement_quality", result, actor="data-quality", audit_resource="data_supplement")
        return result
    except Exception as error:
        result["error_code"] = type(error).__name__
        control.put_admin_setting("data_supplement_quality", result, actor="data-quality", audit_resource="data_supplement")
        raise
    finally:
        if core is not None:
            core.close()
        control.close()
