"""DRL-01D: verifiable *retrospective* two-year official PE/PB profile.

This is a bounded deterministic research calculation, not a published
investment signal. Source observation time is not automatically the first
public availability time; historical backtests must still apply PIT fences.
"""
from __future__ import annotations

from collections import defaultdict
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping, Any


def two_year_profile(rows: Iterable[Mapping[str, Any]], *, symbol: str,
                      as_of: date, metric: str, max_rows: int = 2000) -> dict[str, Any]:
    if metric not in ("pe_ratio", "pb_ratio"):
        raise ValueError("unsupported_valuation_metric")
    if not isinstance(as_of, date) or not symbol:
        raise ValueError("invalid_valuation_scope")
    if not 1 <= max_rows <= 5000:
        raise ValueError("unbounded_valuation_rows")

    # Explicit leap-day handling: never substitute a 365*2 approximation.
    try:
        start = as_of.replace(year=as_of.year - 2)
    except ValueError:
        start = as_of.replace(year=as_of.year - 2, day=28)
    common = {
        "symbol": symbol, "metric": metric, "window_years": 2,
        "window_start": start.isoformat(), "window_end": as_of.isoformat(),
        "status": "pending", "count": 0, "months_with_valid_observation": 0,
        "earliest": None, "latest": None, "latest_value": None,
        "min": None, "max": None, "percentile_midrank": None,
        "historical_pit_certified": False,
        "calculation_version": "official-two-year-retrospective-v1",
    }
    # Conflicting same-day source revisions cannot be silently selected without
    # a version/publication ordering key: exclude those days.
    observations: dict[date, set[Decimal]] = defaultdict(set)
    seen = 0
    source_ids = set()
    for row in rows:
        seen += 1
        if seen > max_rows:
            raise ValueError("valuation_scan_limit_exceeded")
        if (str(row.get("symbol")) != symbol
                or row.get("source_id") not in {"twse", "tpex", "finmind"} or not row.get("provenance_id")):
            continue
        try:
            day = date.fromisoformat(str(row.get("observed_date"))[:10])
            value = Decimal(str(row[metric]))
        except (ValueError, TypeError, KeyError, InvalidOperation):
            continue
        if not start <= day <= as_of or not value.is_finite() or value <= 0:
            continue
        source_ids.add(row['source_id'])
        observations[day].add(value)
    if 'finmind' in source_ids:
        common['calculation_version'] = 'approved-provider-two-year-retrospective-v1'
    series = sorted((day, next(iter(values))) for day, values in observations.items()
                    if len(values) == 1)
    if not series:
        return common
    dates = [day for day, _ in series]
    values = [value for _, value in series]
    latest_value = values[-1]
    months = len({(day.year, day.month) for day in dates})
    monthly: dict[tuple[int, int], list[Decimal]] = defaultdict(list)
    for day, value in series:
        monthly[day.year, day.month].append(value)

    def median(observations: list[Decimal]) -> Decimal:
        ordered = sorted(observations)
        middle = len(ordered) // 2
        return (ordered[middle] if len(ordered) % 2
                else (ordered[middle - 1] + ordered[middle]) / 2)

    monthly_points = [
        {"date": f"{year}-{month:02d}-01", "value": str(median(group))}
        for (year, month), group in sorted(monthly.items())
    ]
    out = {**common,
           "count": len(series),
           "months_with_valid_observation": months,
           "earliest": dates[0].isoformat(), "latest": dates[-1].isoformat(),
           "latest_value": str(latest_value),
           "min": str(min(values)), "max": str(max(values)),
           "monthly_points": monthly_points}
    # At least 18 distinct calendar months and 150 actual daily observations,
    # with both endpoints, are needed to call this a two-year *distribution*.
    # A single pair of old/new data points does not qualify.
    if not (dates[0] <= start + timedelta(days=31)
            and dates[-1] >= as_of - timedelta(days=30)
            and months >= 18 and len(series) >= 150):
        return {**out, "status": "partial_history"}
    ranks = sorted(values)

    def quartile(fraction: Decimal) -> str:
        index = (Decimal(len(ranks) - 1) * fraction)
        lower = int(index)
        upper = min(lower + 1, len(ranks) - 1)
        return str((ranks[lower] + (ranks[upper] - ranks[lower])
                    * (index - Decimal(lower))).quantize(Decimal("0.0001")))

    below = sum(value < latest_value for value in values)
    equal = sum(value == latest_value for value in values)
    percentile = (Decimal(below) + Decimal(equal) / 2) * 100 / len(values)
    return {**out, "status": "ready",
            "quartile_25": quartile(Decimal("0.25")),
            "median": quartile(Decimal("0.50")),
            "quartile_75": quartile(Decimal("0.75")),
            "percentile_midrank": str(percentile.quantize(Decimal("0.01")))}


def publish_focus_profiles(core: Any, control: Any, *, symbols: list[str],
                           as_of: date) -> dict[str, Any]:
    """Write two tiny, read-only-serving profiles from one pinned Core snapshot.

    Requires versioned 063 migration. Fails closed when unavailable: never
    invent two-year status in the client or promote research rows to Core.
    This is called only for the approved TWSE equity focus cohort.
    """
    from pyiceberg.expressions import And, GreaterThanOrEqual, In

    symbols = sorted(set(symbols))
    if not symbols or len(symbols) > 50 or any(
        not s.isdigit() or len(s) != 4 for s in symbols
    ):
        raise ValueError("invalid_two_year_focus")
    table = core.catalog.load_table(core.table_identifier("valuation"))
    snapshot = table.current_snapshot()
    if snapshot is None:
        raise ValueError("no_current_valuation_snapshot")
    try:
        start = as_of.replace(year=as_of.year - 2)
    except ValueError:
        start = as_of.replace(year=as_of.year - 2, day=28)
    selected = ("symbol", "observed_date", "pe_ratio", "pb_ratio",
                "source_id", "provenance_id")
    rows = table.scan(
        snapshot_id=snapshot.snapshot_id,
        row_filter=And(GreaterThanOrEqual("observed_date", start),
                       In("symbol", symbols)),
        selected_fields=selected, limit=12000,
    ).to_arrow().to_pylist()
    if len(rows) >= 12000:
        raise ValueError("valuation_profile_scan_truncated")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("symbol")) in symbols:
            grouped[str(row["symbol"])].append(row)
    output = []
    for symbol in symbols:
        for metric in ("pe_ratio", "pb_ratio"):
            profile = two_year_profile(grouped[symbol], symbol=symbol,
                                        metric=metric, as_of=as_of)
            profile.update(
                source_id=(next(iter({r['source_id'] for r in grouped[symbol]}))
                           if len({r['source_id'] for r in grouped[symbol]}) == 1 else 'mixed'),
                source_ids=sorted({r['source_id'] for r in grouped[symbol]}),
                core_snapshot_id=str(snapshot.snapshot_id),
                source_coverage="source_observed_date_not_historical_publication",
            )
            if 'finmind' in profile['source_ids']:
                profile['calculation_version'] = 'approved-provider-two-year-retrospective-v1'
            output.append((symbol, metric, as_of, snapshot.snapshot_id,
                           json.dumps(profile, sort_keys=True, ensure_ascii=False)))
    with control.connection.transaction():
        with control.connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO control.stock_valuation_five_year(
                       symbol, metric, as_of_date, core_snapshot_id, payload_json)
                   VALUES (%s,%s,%s,%s,%s::jsonb)
                   ON CONFLICT(symbol,metric) DO UPDATE
                   SET as_of_date=EXCLUDED.as_of_date,
                       core_snapshot_id=EXCLUDED.core_snapshot_id,
                       payload_json=EXCLUDED.payload_json,
                       updated_at=now()
                   WHERE EXCLUDED.as_of_date >= control.stock_valuation_five_year.as_of_date""",
                output,
            )
    return {
        "status":"published", "as_of":as_of.isoformat(), "window_years":2,
        "source_snapshot_id":str(snapshot.snapshot_id),
        "symbols":len(symbols), "profiles":len(output),
        "two_year_ready":sum(json.loads(row[4])["status"] == "ready" for row in output),
        "source_data_scanned":len(rows),
    }
