"""04 Valuation: deterministic PE/PB reference scenarios (RV-02).

Pure research/serving calculation only. No database, registry, LLM or model role.
The caller supplies approved, comparable quarterly financial facts and month-end
multiple observations; this function neither downloads nor publishes facts.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

METHOD_VERSION = "valuation-range-quantiles-v1"
SCHEMA_VERSION = "valuation-range.v1"
MIN_MONTHS = 24
WINDOW_MONTHS = 60


def _positive(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() and result > 0 else None


def _number(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _known_after(row: Mapping[str, Any], as_of: date) -> bool:
    # Unknown historical first-observed is not represented as verified PIT.
    for key in ("source_published_at", "first_observed_at", "available_at"):
        if row.get(key) is not None:
            observed = _day(row[key])
            if observed is None or observed > as_of:
                return True
    return False


def _quarter(row: Mapping[str, Any]) -> int | None:
    try:
        year, quarter = int(row["fiscal_year"]), int(row["fiscal_quarter"])
    except (KeyError, ValueError, TypeError):
        return None
    if not 1 <= quarter <= 4 or year < 1900 or year > 2200:
        return None
    return year * 4 + quarter


def _quantile(ordered: list[Decimal], fraction: Decimal) -> Decimal:
    position = Decimal(len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _basis(
    financial_rows: Sequence[Mapping[str, Any]], *, as_of: date, method: str
) -> tuple[Decimal | None, str | None, str, list[str]]:
    # Never admit a fiscal quarter that has not ended at the requested as-of;
    # even records without explicit availability timestamps cannot travel forward.
    as_of_quarter = as_of.year * 4 + (as_of.month - 1) // 3 + 1
    valid = [
        r for r in financial_rows
        if not _known_after(r, as_of)
        and (q := _quarter(r)) is not None
        and q <= as_of_quarter
        and (_day(r.get("fiscal_period_end") or r.get("period_end")) is None
             or _day(r.get("fiscal_period_end") or r.get("period_end")) <= as_of)
    ]
    if method == "pe":
        # Exactly four successive *single-quarter* EPS, not cumulative/YTD.
        rows = [r for r in valid if r.get("metric") in ("eps_single_quarter", "eps")]
        by_period: dict[int, list[Mapping[str, Any]]] = {}
        for row in rows:
            q = _quarter(row)
            if q is not None:
                by_period.setdefault(q, []).append(row)
        if len(by_period) < 4:
            return None, None, "missing", ["four_quarter_eps_missing"]
        quarters = sorted(by_period)[-4:]
        if quarters != list(range(quarters[-1] - 3, quarters[-1] + 1)):
            return None, None, "missing", ["eps_quarters_not_consecutive"]
        chosen = []
        for q in quarters:
            if len(by_period[q]) != 1:
                return None, None, "blocked_basis", ["ambiguous_eps_revision"]
            chosen.append(by_period[q][0])
        if any(r.get("unit") != "TWD_per_share"
               or r.get("period_basis") != "single_quarter"
               or _number(r.get("value")) is None for r in chosen):
            return None, None, "blocked_basis", ["eps_unit_or_period_incomparable"]
        share = {str(r.get("share_basis") or "") for r in chosen}
        scopes = {str(r.get("report_scope") or "") for r in chosen}
        if len(share) != 1 or "" in share or len(scopes) != 1 or "" in scopes:
            return None, None, "blocked_basis", ["eps_share_or_scope_incomparable"]
        total = sum((_number(r["value"]) for r in chosen), Decimal(0))
        if total <= 0:
            return None, f"{chosen[-1]['fiscal_year']}Q{chosen[-1]['fiscal_quarter']}", "missing", ["nonpositive_ttm_eps"]
        last = chosen[-1]
        return total, f"{last['fiscal_year']}Q{last['fiscal_quarter']}", "available", []
    # Financial companies: the latest known same-share-basis reported BVPS.
    rows = [r for r in valid if r.get("metric") in ("bvps", "book_value_per_share")]
    by_period = {}
    for row in rows:
        q = _quarter(row)
        if q is not None:
            by_period.setdefault(q, []).append(row)
    if not by_period:
        return None, None, "missing", ["bvps_missing"]
    q = max(by_period)
    if len(by_period[q]) != 1:
        return None, None, "blocked_basis", ["ambiguous_bvps_revision"]
    row = by_period[q][0]
    value = _positive(row.get("value"))
    if row.get("unit") != "TWD_per_share" or not row.get("share_basis"):
        return None, None, "blocked_basis", ["bvps_unit_or_share_basis_unknown"]
    if value is None:
        return None, None, "missing", ["nonpositive_bvps"]
    return value, f"{row['fiscal_year']}Q{row['fiscal_quarter']}", "available", []


def calculate_reference_range(
    *, symbol: str, market: str, security_type: str, is_financial: bool,
    as_of: str, financial_rows: Sequence[Mapping[str, Any]],
    multiple_rows: Sequence[Mapping[str, Any]],
    rights_status: str, price: Any = None, price_as_of: str | None = None,
) -> dict[str, Any]:
    """Return one reference range; all numbers are Decimal-serialized strings.

    multiple_rows must contain actual month-end PE/PB observations with
    `observed_date`, `metric`, `value`; missing months are never filled.
    This function is RV-02 only; RV-01/03 must connect true serving readers.
    """
    cutoff = _day(as_of)
    if cutoff is None or cutoff.isoformat() != as_of:
        raise ValueError("invalid_valuation_as_of")
    if not symbol or market not in ("twse", "tpex"):
        raise ValueError("invalid_valuation_identity")
    method = "pb" if is_financial else "pe"
    metric = "pb_ratio" if is_financial else "pe_ratio"
    record = {
        "schema_version": SCHEMA_VERSION, "method_version": METHOD_VERSION,
        "method": "historical_month_end_quantile_scenario",
        "symbol": symbol, "market": market, "security_type": security_type,
        "as_of": as_of, "basis_type": "bvps" if is_financial else "ttm_eps",
        "financial_period": None, "window_months": WINDOW_MONTHS,
        "valid_month_count": 0, "historical_pit_status": "not_verified",
        "rights_status": rights_status, "status": "missing",
        "excluded_reasons": [], "basis": None,
        "lower": None, "mid": None, "upper": None,
        "price_gap_to_reference_mid_pct": None,
        "price_as_of": price_as_of,
        "input_hash": sha256(json.dumps(
            {"symbol": symbol, "market": market, "as_of": as_of,
             "financial_rows": list(financial_rows),
             "multiple_rows": list(multiple_rows), "price": str(price),
             "price_as_of": price_as_of},
            sort_keys=True, ensure_ascii=False, default=str,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
    }
    if security_type in ("etf", "etn", "fund"):
        record.update(status="not_applicable", excluded_reasons=["security_not_equity"])
        return record
    if security_type != "ordinary_stock":
        record.update(status="not_applicable", excluded_reasons=["security_type_not_supported"])
        return record
    if rights_status not in ("approved", "allowed"):
        record.update(status="blocked_rights", excluded_reasons=["source_rights_not_approved"])
        return record

    basis, financial_period, basis_status, reasons = _basis(
        financial_rows, as_of=cutoff, method=method)
    record["financial_period"] = financial_period
    if basis_status != "available":
        record.update(status=basis_status, excluded_reasons=reasons)
        return record
    record["basis"] = str(basis)

    # 60 calendar months including the as-of month; only exact month-end rows.
    cutoff_month = cutoff.year * 12 + cutoff.month
    monthly: dict[int, list[Decimal]] = {}
    for row in multiple_rows:
        if row.get("metric") != metric or _known_after(row, cutoff):
            continue
        day = _day(row.get("observed_date"))
        val = _positive(row.get("value"))
        if day is None or val is None or day > cutoff:
            continue
        month = day.year * 12 + day.month
        if not cutoff_month - WINDOW_MONTHS + 1 <= month <= cutoff_month:
            continue
        end = date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
        if row.get("month_end_observation") is True:
            # RV-03 stores the actual final trading date, not a fictitious
            # calendar-end quote. The adapter proves source + proximity.
            if (row.get("month_end_date") != end.isoformat()
                    or not 0 <= (end - day).days <= 7):
                continue
        elif day != end:
            continue
        monthly.setdefault(month, []).append(val)
    # Conflicting same-month values are ambiguous and excluded, never averaged.
    values = sorted(series[0] for series in monthly.values()
                    if len(series) == 1)
    record["valid_month_count"] = len(values)
    if len(values) < MIN_MONTHS:
        record.update(status="limited", excluded_reasons=["insufficient_month_end_multiples"])
        return record
    lower, mid, upper = (
        basis * _quantile(values, Decimal("0.25")),
        basis * _quantile(values, Decimal("0.50")),
        basis * _quantile(values, Decimal("0.75")),
    )
    if not 0 < lower <= mid <= upper:
        record.update(status="error", excluded_reasons=["range_invariant_failed"])
        return record
    record.update(status="available", lower=str(lower), mid=str(mid),
                  upper=str(upper), excluded_reasons=[])
    observed_price = _positive(price)
    observed_day = _day(price_as_of) if price_as_of else None
    if observed_price is not None and observed_day is not None and observed_day <= cutoff:
        record["price_gap_to_reference_mid_pct"] = str(observed_price / mid - 1)
    return record
