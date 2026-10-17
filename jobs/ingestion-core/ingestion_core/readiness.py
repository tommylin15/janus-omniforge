"""DRL-01 bounded read-only readiness counters from existing official Core.

No canonical mutation, new upstream provider, owner identifiers in receipts,
scheduler, or separate database. Published only to existing Admin settings.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from pyiceberg.expressions import And, GreaterThanOrEqual, In


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _positive(value):
    try:
        number = Decimal(str(value))
        return number.is_finite() and number > 0
    except (TypeError, ValueError, InvalidOperation):
        return False


def _scan(core, dataset, columns, *, row_filter=None, limit=150000):
    if not core.table_exists(dataset):
        return [], None
    table = core.catalog.load_table(core.table_identifier(dataset))
    available = {field.name for field in table.schema().fields}
    if not set(columns).issubset(available):
        return [], None
    snapshot = table.current_snapshot()
    if snapshot is None:
        return [], None
    scan = table.scan(snapshot_id=snapshot.snapshot_id, selected_fields=tuple(columns),
                      row_filter=row_filter)
    rows = scan.to_arrow().to_pylist()
    if len(rows) > limit:
        raise ValueError("readiness_bounded_scan_exceeded")
    return rows, str(snapshot.snapshot_id)


def _published_rows(core, dataset, columns, **kwargs):
    return _scan(core, dataset, columns, **kwargs)


def summarize_readiness(members, benchmark, prices, financials, focused_prices, focus,
                        *, snapshot_ids, as_of, market_version):
    """Aggregate without exposing owner symbols, fabricated coverage or raw numbers."""
    universe = {"TWSE": set(), "TPEX": set()}
    for item in members:
        market = item.get("market")
        if market in universe and item.get("symbol"):
            universe[market].add(str(item["symbol"]))
    sessions = sorted({
        d for row in benchmark
        if row.get("benchmark_id") == "TAIEX"
        and row.get("source_id") == "taiex" and row.get("provenance_id")
        and (d := _day(row.get("trade_date"))) is not None and d <= as_of
    })[-21:]
    last_sessions = set(sessions)
    actual = {market: defaultdict(set) for market in universe}
    for row in prices:
        market = row.get("market")
        symbol = str(row.get("symbol") or "")
        day = _day(row.get("trade_date"))
        if (market in universe and symbol in universe[market] and day in last_sessions
                and row.get("source_id") == market.lower()
                and row.get("provenance_id") and _positive(row.get("close"))):
            actual[market][symbol].add(day)
    summary = {}
    for market, names in universe.items():
        eligible = sum(len(dates) >= 20 for dates in actual[market].values())
        denominator = len(names)
        ratio = eligible / denominator if denominator else None
        threshold = .90 if market == "TWSE" else .70
        summary[market] = {
            "expected": denominator, "symbols_with_20_of_21_sessions": eligible,
            "required_sessions": 21, "observed_sessions": len(sessions),
            "minimum_coverage": threshold,
            "coverage": round(ratio, 6) if ratio is not None else None,
            "status": "PASS" if len(sessions) == 21 and ratio is not None
                              and ratio >= threshold else "PARTIAL",
        }

    relevant = {str(symbol) for symbol in focus}
    focused = defaultdict(set)
    for row in focused_prices:
        day = _day(row.get("trade_date"))
        symbol = str(row.get("symbol") or "")
        if (symbol in relevant and day and day <= as_of
                and row.get("source_id") in ("twse", "tpex")
                and row.get("provenance_id") and _positive(row.get("close"))):
            focused[symbol].add(day)
    focused_count = sum(len(days) >= 120 for days in focused.values())

    monthly = defaultdict(set)
    eps = defaultdict(set)
    for row in financials:
        symbol = str(row.get("symbol") or "")
        if symbol not in universe["TWSE"] | universe["TPEX"]:
            continue
        if (row.get("source_id") != "mops" or not row.get("provenance_id")
                or not row.get("availability_at")):
            continue
        try:
            amount = Decimal(str(row.get("value")))
            if not amount.is_finite():
                continue
        except (TypeError, ValueError, InvalidOperation):
            continue
        end = _day(row.get("fiscal_period_end"))
        if end is None or end > as_of:
            continue
        metric = str(row.get("metric") or "")
        if (row.get("statement_type") == "monthly_revenue"
                and metric == "monthly_revenue"
                and row.get("period_basis") == "monthly"
                and row.get("fiscal_month") == end.month
                and row.get("unit") == "TWD_thousands"):
            monthly[symbol].add((end.year, end.month))
        if (row.get("unit") == "TWD_per_share" and
                ((metric == "eps_single_quarter" and row.get("period_basis") == "single_quarter")
                or (end.month == 3 and
                    ("每股盈餘" in metric or metric == "eps_year_to_date")
                    and row.get("period_basis") in (None, "year_to_date")))):
            eps[symbol].add((end.year, (end.month - 1) // 3 + 1))
    all_names = universe["TWSE"] | universe["TPEX"]
    last_due = as_of.replace(day=1)-timedelta(days=1)
    if as_of.day <= 10:
        last_due = last_due.replace(day=1)-timedelta(days=1)
    last_index = last_due.year * 12 + last_due.month - 1
    expected_months = {(index // 12, index % 12 + 1)
                       for index in range(last_index-12, last_index+1)}
    ready_months = sum(expected_months.issubset(monthly[s]) for s in all_names)
    def four_consecutive_quarters(periods):
        if not periods:
            return False
        indices = {year * 4 + quarter - 1 for year, quarter in periods}
        return any({i, i-1, i-2, i-3}.issubset(indices) for i in indices)
    ready_eps = sum(four_consecutive_quarters(eps[s]) for s in all_names)
    monthly_by_market = {}
    eps_by_market = {}
    for market, names in universe.items():
        denominator = len(names)
        monthly_count = sum(expected_months.issubset(monthly[s]) for s in names)
        eps_count = sum(four_consecutive_quarters(eps[s]) for s in names)
        monthly_threshold = .90 if market == "TWSE" else .70
        monthly_coverage = monthly_count / denominator if denominator else None
        eps_coverage = eps_count / denominator if denominator else None
        monthly_by_market[market] = {
            "expected": denominator, "qualified": monthly_count,
            "coverage": round(monthly_coverage, 6) if monthly_coverage is not None else None,
            "minimum_coverage": monthly_threshold,
            "status": "PASS" if monthly_coverage is not None
                              and monthly_coverage >= monthly_threshold else "PARTIAL",
        }
        eps_by_market[market] = {
            "expected": denominator, "qualified": eps_count,
            "coverage": round(eps_coverage, 6) if eps_coverage is not None else None,
            "status": "MEASURED" if denominator else "UNKNOWN",
        }
    return {
        "schema_version": "data-readiness-ledger.v1",
        "as_of": as_of.isoformat(), "checked_at": datetime.now(timezone.utc).isoformat(),
        "market_membership_version": market_version,
        "snapshot_ids": snapshot_ids,
        "market_price_window": summary,
        "focus_120d": {"expected": len(relevant), "qualified": focused_count,
                       "status": "PASS" if relevant and focused_count == len(relevant) else "PARTIAL"},
        "monthly_revenue_13": {"expected": len(all_names),
                               "qualified": ready_months,
                               "markets": monthly_by_market,
                               "status": "PASS" if all(
                                   m["status"] == "PASS" for m in monthly_by_market.values()
                               ) else "PARTIAL"},
        "eps_4_comparable": {"expected": len(all_names),
                             "qualified": ready_eps,
                             "markets": eps_by_market,
                             "status": "MEASURED"},
        "status": "PARTIAL" if (not all(x["status"] == "PASS" for x in summary.values())
                               or focused_count < len(relevant)) else "PRICE_AND_FOCUS_READY_ONLY",
        "historical_pit_certified": False,
        "canonical_mutation": False,
    }


def publish_data_readiness(core, control, *, as_of, actor="data-supplement"):
    """Reuse existing controller's daily/weekly Jobs and Admin metadata store."""
    market = control.full_market_snapshot()
    members = market.get("items") or []
    if not members:
        raise ValueError("missing_official_universe")
    focus = set(control.config_symbols("first-batch")) | set(control.portfolio_coverage_symbols())
    # Two bounded price reads avoid loading full-market 120-day history into RAM.
    prices, price_snapshot = _scan(core, "ohlcv",
        ("symbol", "market", "trade_date", "close", "source_id", "provenance_id"),
        row_filter=GreaterThanOrEqual("trade_date", as_of-timedelta(days=45)))
    focus_rows, focus_snapshot = _scan(core, "ohlcv",
        ("symbol", "trade_date", "close", "source_id", "provenance_id"),
        row_filter=And(GreaterThanOrEqual("trade_date", as_of-timedelta(days=220)),
                       In("symbol", sorted(focus))), limit=30000) if focus else ([], price_snapshot)
    benchmark, benchmark_snapshot = _scan(core, "benchmark",
        ("benchmark_id", "trade_date", "source_id", "provenance_id"),
        row_filter=GreaterThanOrEqual("trade_date", as_of-timedelta(days=45)))
    financial, financial_snapshot = _scan(core, "financials",
        ("symbol", "source_id", "provenance_id", "fiscal_period_end",
         "fiscal_month", "fiscal_quarter", "statement_type",
         "metric", "period_basis", "unit", "value", "availability_at"), limit=150000)
    proof = {"ohlcv": price_snapshot, "ohlcv_focus": focus_snapshot,
             "benchmark": benchmark_snapshot, "financials": financial_snapshot}
    result = summarize_readiness(members, benchmark, prices, financial, focus_rows, focus,
                                 snapshot_ids=proof, as_of=as_of, market_version=market.get("version"))
    if any(value is None for value in proof.values()):
        result["status"] = "PARTIAL_MISSING_CORE_TABLE"
    control.put_admin_setting("data_readiness_ledger", result,
                              actor=actor, audit_resource="data_supplement")
    return result
