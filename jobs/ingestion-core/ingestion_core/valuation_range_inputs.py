"""RV-03: bounded, read-only connection of existing Core/Serving facts to 04 Valuation.

No collection, historical refill, mutation, daily scheduler or public API route.
The caller supplies *verified* instrument class/financial classification.  A
missing share-basis or insufficient true month-end coverage never becomes a price.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from calendar import monthrange
from typing import Any, Mapping, Sequence

from packages.valuation_range import calculate_reference_range, is_verified_month_final_session

MAX_CORE_ROWS = 4000
MAX_FINANCIAL_ROWS = 300
MAX_MONTH_END_GAP_DAYS = 7
AUTHORIZED_MULTIPLE_SOURCES = frozenset({"twse", "tpex", "finmind"})
AUTHORIZED_EPS_SOURCES = frozenset({"mops", "yahoo-finance", "finmind"})


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _positive(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _window_start(as_of: date) -> date:
    last = as_of.year * 12 + as_of.month - 60 + 1
    return date((last - 1) // 12, (last - 1) % 12 + 1, 1)


def monthly_last_trading_observations(
    rows: Sequence[Mapping[str, Any]], *, as_of: date, metric: str,
    market: str = "unknown"
) -> list[dict[str, Any]]:
    """Extract observed, month-final trading quotes without inventing dates.

    Only a completed calendar month qualifies. The last observed trading day
    must be within 7 calendar days of its end; missing or conflicting rows are
    not interpolated. Source observed_date is preserved as the actual date.
    """
    if metric not in {"pe_ratio", "pb_ratio"} or len(rows) > MAX_CORE_ROWS:
        raise ValueError("valuation_monthly_input_outside_bound")
    start = _window_start(as_of)
    grouped: dict[tuple[int, int], dict[date, set[Decimal]]] = defaultdict(lambda: defaultdict(set))
    for row in rows:
        day = _date(row.get("observed_date"))
        value = _positive(row.get(metric))
        if (day is None or value is None or not start <= day <= as_of
                or row.get("source_id") not in AUTHORIZED_MULTIPLE_SOURCES
                or not row.get("provenance_id")):
            continue
        if any(
            (t := _date(row[key])) is None or t > as_of
            for key in ("first_observed_at", "source_published_at")
            if row.get(key) is not None
        ):
            continue
        grouped[(day.year, day.month)][day].add(value)

    result = []
    for (year, month), per_day in sorted(grouped.items()):
        month_end = date(year, month, monthrange(year, month)[1])
        if month_end > as_of:
            continue
        observed = max(per_day)
        if not is_verified_month_final_session(observed, month_end, market=market):
            continue
        values = per_day[observed]
        if len(values) != 1:
            # The latest trading day is disputed; do not fall back to an
            # earlier observation and pretend it was the month close.
            continue
        result.append({
            "metric": metric, "observed_date": observed.isoformat(),
            "value": str(next(iter(values))), "month_end_observation": True,
            "month_end_date": month_end.isoformat(),
        })
    return result


def comparable_financial_facts(rows: Sequence[Mapping[str, Any]], *, as_of: date) -> list[dict[str, Any]]:
    """Allow only already published real quarter EPS/BVPS values.

    Do not derive BVPS from total equity or Q2-Q4 single-quarter EPS from YTD.
    Retain a missing/unknown share basis, so the RV-02 gate blocks pricing.
    """
    if len(rows) > MAX_FINANCIAL_ROWS:
        raise ValueError("valuation_financial_input_outside_bound")
    result = []
    for row in rows:
        source = row.get("source_id")
        if not row.get("provenance_id") or source not in AUTHORIZED_EPS_SOURCES:
            continue
        metric = row.get("metric")
        if metric not in {"eps_single_quarter", "bvps", "book_value_per_share"}:
            continue
        if metric == "eps_single_quarter" and row.get("period_basis") != "single_quarter":
            continue
        if metric in {"bvps", "book_value_per_share"} and row.get("period_basis") not in {"snapshot", None}:
            continue
        if row.get("unit") != "TWD_per_share":
            continue
        if any(
            (t := _date(row.get(key))) is None or t > as_of
            for key in ("availability_at", "published_at", "first_observed_at", "source_published_at")
            if row.get(key) not in (None, "")
        ):
            continue
        if _date(row.get("fiscal_period_end") or row.get("period_end")) is None:
            continue
        result.append({
            "metric": metric, "fiscal_year": row.get("fiscal_year"),
            "fiscal_quarter": row.get("fiscal_quarter"),
            "fiscal_period_end": row.get("fiscal_period_end") or row.get("period_end"),
            "value": row.get("value"), "unit": row.get("unit"),
            "period_basis": row.get("period_basis"),
            "report_scope": row.get("report_scope"),
            "share_basis": row.get("share_basis"),
            "availability_at": row.get("availability_at"),
            "source_published_at": row.get("source_published_at"),
            "first_observed_at": row.get("first_observed_at"),
        })
    return result


def from_existing_rows(
    *, symbol: str, market: str, security_type: str, is_financial: bool,
    as_of: date, valuation_rows: Sequence[Mapping[str, Any]],
    financial_rows: Sequence[Mapping[str, Any]],
    rights_status: str, price: Any = None, price_as_of: str | None = None,
) -> dict[str, Any]:
    """Adapter for validated existing Core valuation and PG serving rows."""
    metric = "pb_ratio" if is_financial else "pe_ratio"
    # Explicit symbol isolation even for the pure adapter, independent of
    # the Core/PG SQL predicates used by the live reader.
    own_valuation = [r for r in valuation_rows if str(r.get("symbol")) == symbol]
    own_financial = [r for r in financial_rows if str(r.get("symbol")) == symbol]
    observed = monthly_last_trading_observations(
        own_valuation, as_of=as_of, metric=metric, market=market)
    financial = comparable_financial_facts(own_financial, as_of=as_of)
    result = calculate_reference_range(
        symbol=symbol, market=market, security_type=security_type,
        is_financial=is_financial, as_of=as_of.isoformat(),
        financial_rows=financial, multiple_rows=observed,
        rights_status=rights_status, price=price, price_as_of=price_as_of,
    )
    result["input_refs"] = {
        "multiple_source": "core.valuation_v1/current",
        "financial_source": "control.market_serving_recent",
        "price_source": "control.stock_serving_recent" if price is not None else None,
    }
    result["month_end_observation_dates"] = [r["observed_date"] for r in observed]
    return result


def read_existing_inputs(
    core: Any, control: Any, *, symbol: str, as_of: date,
    security_type: str, is_financial: bool, rights_status: str,
    max_core_rows: int = MAX_CORE_ROWS,
    max_financial_rows: int = MAX_FINANCIAL_ROWS,
) -> dict[str, Any]:
    """Bounded Dev/worker read-only path; intentionally not a public API.

    Market comes from the enabled real stock_master row. Instrument kind and
    financial classification must be verified by the invoking business reader.
    Never infer these facts from the 4-digit symbol.
    """
    if (not symbol.isdigit() or len(symbol) != 4 or
            not 1 <= max_core_rows <= MAX_CORE_ROWS or
            not 1 <= max_financial_rows <= MAX_FINANCIAL_ROWS):
        raise ValueError("valuation_input_scope_invalid")
    from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, LessThanOrEqual

    with control.connection.cursor() as cursor:
        cursor.execute(
            "SELECT market FROM control.stock_master WHERE symbol=%s AND enabled=true LIMIT 1",
            (symbol,),
        )
        identity = cursor.fetchone()
        if not identity or str(identity[0]).upper() not in ("TWSE", "TPEX"):
            raise ValueError("valuation_identity_unavailable")
        market = str(identity[0]).lower()
        cursor.execute(
            """SELECT payload_json,source_id,provenance_id
               FROM control.market_serving_recent
               WHERE dataset_id='financials' AND symbol=%s AND sort_at < %s
               ORDER BY sort_at DESC LIMIT %s""",
            (symbol, as_of.isoformat() + "T23:59:59+00:00", max_financial_rows + 1),
        )
        financial = []
        for payload, source, provenance in cursor.fetchall():
            if not isinstance(payload, dict):
                raise ValueError("valuation_financial_payload_unreadable")
            financial.append({**payload, "source_id": source, "provenance_id": provenance})
        if len(financial) > max_financial_rows:
            raise ValueError("valuation_financial_scan_truncated")
        cursor.execute(
            """SELECT payload_json,source_id,provenance_id
               FROM control.stock_serving_recent
               WHERE dataset_id='ohlcv' AND symbol=%s AND sort_at < %s
               ORDER BY sort_at DESC LIMIT 1""",
            (symbol, as_of.isoformat() + "T23:59:59+00:00"),
        )
        current = cursor.fetchone()
    price, price_as_of = None, None
    if current and isinstance(current[0], dict) and current[1] in {"twse", "tpex"} and current[2]:
        price, price_as_of = current[0].get("close"), current[0].get("trade_date")

    table = core.catalog.load_table(core.table_identifier("valuation"))
    snapshot = table.current_snapshot()
    if snapshot is None:
        raise ValueError("valuation_core_current_snapshot_missing")
    selected = ("symbol", "observed_date", "pe_ratio", "pb_ratio", "source_id", "provenance_id")
    scan = table.scan(
        snapshot_id=snapshot.snapshot_id,
        row_filter=And(
            EqualTo("symbol", symbol),
            GreaterThanOrEqual("observed_date", _window_start(as_of)),
            LessThanOrEqual("observed_date", as_of),
        ),
        selected_fields=selected,
        limit=max_core_rows + 1,
    )
    observations = scan.to_arrow().to_pylist()
    if len(observations) > max_core_rows:
        raise ValueError("valuation_core_scan_truncated")
    # Authorization is checked against the existing control-plane registry;
    # merely being an allowlisted adapter is not publication permission.
    if rights_status in {"approved", "allowed"}:
        used = {
            str(row["source_id"]) for row in (observations + financial)
            if row.get("source_id") and row.get("provenance_id")
        }
        if not used or not all(control.source_is_approved(source) for source in used):
            rights_status = "unknown"
    result = from_existing_rows(
        symbol=symbol, market=market, security_type=security_type,
        is_financial=is_financial, as_of=as_of, valuation_rows=observations,
        financial_rows=financial, rights_status=rights_status,
        price=price, price_as_of=price_as_of,
    )
    result["input_refs"]["core_snapshot_id"] = str(snapshot.snapshot_id)
    result["source_rows_scanned"] = {
        "valuation": len(observations), "financials": len(financial),
        "price": 1 if price is not None else 0,
    }
    return result
