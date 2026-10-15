"""Application boundary for public Core queries.

The service deliberately depends on a tiny read-only query callable instead of
owning a database connection.  Cloud Run can inject a bounded DuckDB/Iceberg
reader, while tests can use an in-memory callable.  This prevents request code
from opening connections or accidentally receiving Core write capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from typing import Any, Callable, Mapping, Sequence


_HIDDEN_FIELDS = frozenset({
    "artifact_ref", "artifact_uri", "authorization", "credential", "gcs_uri", "object_path",
    "password", "raw_payload", "secret", "storage_uri", "token", "traceback",
})
_HIDDEN_SUFFIXES = ("_credential", "_password", "_secret", "_token", "_uri", "_path")


def _is_hidden_key(key: Any) -> bool:
    normalized = str(key).lower()
    return normalized in _HIDDEN_FIELDS or normalized.endswith(_HIDDEN_SUFFIXES)


def _safe_record(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _safe_record(item)
            for key, item in value.items()
            if not _is_hidden_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_record(item) for item in value]
    return value


class QueryValidationError(ValueError):
    """Safe client-facing validation error."""


@dataclass(frozen=True)
class QueryPage:
    dataset_id: str
    symbol: str
    rows: tuple[dict[str, Any], ...]
    limit: int
    offset: int


class CoreQueryService:
    """Bounded, read-only Core query facade."""

    DATASETS = frozenset({
        "ohlcv", "valuation", "institutional", "financials", "events",
        "market-activity", "benchmark",
    })
    DEFAULT_SUMMARY_DATASETS = tuple(sorted(DATASETS - {"benchmark"}))
    TABLE_NAMES = {dataset: f"core.{dataset.replace('-', '_')}_v1" for dataset in DATASETS}
    FILTER_FIELDS = {dataset: ("benchmark_id" if dataset == "benchmark" else "symbol") for dataset in DATASETS}
    ORDER_FIELDS = {
        "ohlcv": "trade_date",
        "valuation": "observed_date",
        "institutional": "trade_date",
        "financials": "published_at",
        "events": "published_at",
        "market-activity": "trade_date",
        "benchmark": "trade_date",
    }
    DATE_FIELDS = ("trade_date", "observed_date", "published_at", "effective_date", "date")

    def __init__(self, query: Callable[[str, str, Sequence[Any]], Sequence[Mapping[str, Any]]],
                 *, max_limit: int = 200,
                 serving_series: Callable[[str, str, int], Sequence[Mapping[str, Any]] | None] | None = None,
                 serving_home_market_snapshot: Callable[[], Mapping[str, Any] | None] | None = None) -> None:
        if not 1 <= max_limit <= 10_000:
            raise ValueError("max_limit must be between 1 and 10000")
        self._query = query
        self._serving_series = serving_series
        self._serving_home_market_snapshot = serving_home_market_snapshot
        self.max_limit = max_limit

    def page(self, dataset_id: str, symbol: str, *, limit: int = 50, offset: int = 0) -> QueryPage:
        dataset = self._dataset(dataset_id)
        normalized_symbol = self._symbol(symbol)
        if not 1 <= limit <= self.max_limit or offset < 0:
            raise QueryValidationError("limit or offset is invalid")
        # Identifiers are selected only from the fixed allowlist; values remain
        # parameters, so callers cannot inject SQL through symbols.
        field = ("upper(benchmark_id)" if dataset == "benchmark" else self.FILTER_FIELDS[dataset])
        sql = (
            f"SELECT * FROM {self.TABLE_NAMES[dataset]} "
            f"WHERE {field} = ? ORDER BY {self.ORDER_FIELDS[dataset]} DESC "
            "LIMIT ? OFFSET ?"
        )
        try:
            rows = self._query(self.TABLE_NAMES[dataset], sql, (normalized_symbol, limit, offset))
        except Exception as error:
            raise RuntimeError("Core query unavailable") from error
        return QueryPage(dataset, normalized_symbol, tuple(_safe_record(row) for row in rows), limit, offset)

    def visual_series(self, symbol: str, metric: str, *, limit: int = 120) -> dict[str, Any]:
        """Read a small *published serving-only* price/valuation series.

        No Iceberg fallback: slow core scans cannot be triggered by opening a
        chart. Missing projection is visible as unavailable/missing, never 0.
        """
        normalized = self._symbol(symbol)
        mapping = {
            "close": ("ohlcv", "trade_date", "close", "TWD"),
            "pe": ("valuation", "observed_date", "pe_ratio", "times"),
            "pb": ("valuation", "observed_date", "pb_ratio", "times"),
            "yield": ("valuation", "observed_date", "dividend_yield_percent", "percent"),
            "foreign": ("institutional", "trade_date", "net_shares", "shares"),
            "investment_trust": ("institutional", "trade_date", "net_shares", "shares"),
            "dealer": ("institutional", "trade_date", "net_shares", "shares"),
            "revenue": ("financials", "fiscal_period_end", "value", "TWD_thousands"),
            "eps": ("financials", "fiscal_period_end", "value", "TWD_per_share"),
        }
        if metric not in mapping or not 2 <= limit <= min(self.max_limit, 200):
            raise QueryValidationError("invalid visual series metric or limit")
        dataset, date_key, value_key, unit = mapping[metric]
        response: dict[str, Any] = {
            "schema_version": "visual-series.v1", "symbol": normalized,
            "metric": metric, "unit": unit, "data_status": "unavailable",
            "points": [], "usable_points": 0, "requested_rows": limit,
            "data_as_of": None, "source_ids": [], "missing_reason": "serving_unavailable",
            "calculation_version": "published-raw-v1",
        }
        if self._serving_series is None:
            return response
        raw = self._serving_series(dataset, normalized, 600 if dataset == 'financials' else
                                   limit * 3 if dataset == "institutional" else limit)
        if raw is None:
            return response
        response["data_status"] = "missing"
        response["missing_reason"] = "no_published_points"
        if dataset == "institutional":
            raw = [row for row in raw if row.get("investor_type") == metric][:limit]
        elif dataset == 'financials':
            raw = [row for row in raw if row.get('unit') == unit and (
                row.get('metric') in {'monthly_revenue', 'previous_month_revenue'} if metric == 'revenue' else
                row.get('metric') == 'eps_single_quarter' and row.get('period_basis') == 'single_quarter')]
        # Published null/invalid values remain dated gaps so the chart does not
        # silently connect across missing sessions. A valid duplicate wins.
        dated: dict[str, dict[str, str | None]] = {}
        for row in raw if dataset == 'financials' else raw[:limit]:
            day = row.get(date_key) or (row.get('period_end') if dataset == 'financials' else None)
            if day is None:
                continue
            day_string = str(day)[:10]
            try:
                observed_day = date.fromisoformat(day_string)
                if observed_day > datetime.now(ZoneInfo("Asia/Taipei")).date():
                    continue
            except (ValueError, TypeError):
                continue
            number: Decimal | None = None
            try:
                if row.get(value_key) is not None:
                    candidate = Decimal(str(row[value_key]))
                    if candidate.is_finite() and (dataset == "institutional" or metric == 'eps' or
                            candidate >= 0 and (metric in {"yield", "revenue"} or candidate > 0)):
                        number = candidate
            except (InvalidOperation, ValueError, TypeError):
                pass
            if day_string in dated:
                if dated[day_string]["value"] is not None or number is None:
                    continue
            source = str(row.get("source_id") or "").strip()
            if dataset in {"institutional", "financials"} and (source not in {"twse", "tpex", "mops"} or not row.get("provenance_id")):
                number = None
            dated[day_string] = {
                "date": day_string, "value": str(number) if number is not None else None,
                "source_id": source or None,
                "provenance_id": str(row["provenance_id"]) if row.get("provenance_id") else None,
            }
        points = sorted(dated.values(), key=lambda item: str(item["date"]))[-limit:]
        usable = [point for point in points if point["value"] is not None]
        response["points"] = points
        response["usable_points"] = len(usable)
        response["data_as_of"] = usable[-1]["date"] if usable else None
        response["source_ids"] = sorted({str(point["source_id"]) for point in points if point["source_id"]})
        if points:
            complete = len(usable) >= 2 and len(usable) == len(points) and (dataset == 'financials' or len(points) == len(raw))
            response["data_status"] = "available" if complete else "partial"
            response["missing_reason"] = None if complete else "insufficient_or_invalid_points"
        return response

    def market_home(self, *, as_of_date: date | None = None) -> dict[str, Any]:
        """Published Core baseline; each fixed section fails independently."""
        today = as_of_date or datetime.now(ZoneInfo("Asia/Taipei")).date()
        if self._serving_home_market_snapshot is not None:
            try:
                cached = self._serving_home_market_snapshot()
                if (cached and isinstance(cached, Mapping) and cached.get('schema_version') == 'market-home.v1'
                        and set(cached.get('sections', {})) == {'taiex', 'market-activity', 'institutional'}):
                    current = True
                    for part in cached['sections'].values():
                        if part.get('as_of'):
                            age = (today - date.fromisoformat(str(part['as_of']))).days
                            current = current and age >= 0 and part.get('freshness_days') == age
                    if current:
                        return dict(cached)
            except Exception:
                pass
        sections: dict[str, dict[str, Any]] = {}
        benchmark_table = self.TABLE_NAMES["benchmark"]
        # One bounded historical read replaces the old latest-only read.
        # No extra homepage request, no raw payload, no LLM or synthetic trend.
        try:
            rows = self._query(benchmark_table, (
                f"SELECT * FROM {benchmark_table} "
                "WHERE upper(benchmark_id) = ? ORDER BY trade_date DESC LIMIT ?"
            ), ("TAIEX", 40))
            benchmarks = [row for row in rows
                          if str(row.get("benchmark_id", "")).upper() == "TAIEX"]
        except Exception:
            benchmarks = None
        for benchmark_id in ("TAIEX",):
            candidates = benchmarks if benchmarks is not None else []
            # Only points with verifiable observation date and official lineage
            # qualify for the chart. Reject future dates and non-finite closes.
            history_by_day: dict[str, dict[str, str]] = {}
            latest_readable = None
            for candidate in candidates:
                day = str(candidate.get("trade_date") or "")[:10]
                try:
                    trade_day = date.fromisoformat(day)
                    value = Decimal(str(candidate.get("close")))
                except (ValueError, TypeError, InvalidOperation):
                    continue
                if trade_day > today or not value.is_finite() or value <= 0:
                    continue
                # Current single-day index remains independently readable even
                # if this row lacks complete chart lineage. The historical
                # trend itself stays strict: source+provenance required.
                if latest_readable is None:
                    latest_readable = candidate
                source = str(candidate.get("source_id") or "").strip()
                provenance = str(candidate.get("provenance_id") or "").strip()
                if not source or not provenance or day in history_by_day:
                    continue
                history_by_day[day] = {
                    "date": day, "value": str(value),
                    "source_id": source, "provenance_id": provenance,
                }
            history = sorted(history_by_day.values(), key=lambda item: item["date"])[-30:]
            row = latest_readable
            section = self._market_section(
                row, today, 1 if row else 0,
                {"requested_symbols": 1, "received_symbols": 1 if row else 0},
                unavailable=benchmarks is None)
            section["data"]["history_points"] = history
            section["data"]["history_unit"] = "index_points"
            section["data"]["history_as_of"] = history[-1]["date"] if history else None
            section["data"]["history_status"] = ("available" if len(history) >= 2
                                                     else "missing")
            section["data"]["history_source_ids"] = sorted({
                point["source_id"] for point in history
            })
            sections[benchmark_id.lower()] = section
        for dataset in ("market-activity", "institutional"):
            table = self.TABLE_NAMES[dataset]
            try:
                if dataset == "market-activity":
                    aggregates = """sum(try_cast(value AS DOUBLE)) FILTER (WHERE metric = 'day_trade_shares') AS day_trade_shares,
                        sum(try_cast(value AS DOUBLE)) FILTER (WHERE metric = 'day_trade_buy_twd') AS day_trade_buy_twd,
                        sum(try_cast(value AS DOUBLE)) FILTER (WHERE metric = 'day_trade_sell_twd') AS day_trade_sell_twd"""
                else:
                    aggregates = """sum(try_cast(net_shares AS DOUBLE)) FILTER (WHERE investor_type = 'foreign') AS foreign_net_shares,
                        sum(try_cast(net_shares AS DOUBLE)) FILTER (WHERE investor_type = 'investment_trust') AS investment_trust_net_shares,
                        sum(try_cast(net_shares AS DOUBLE)) FILTER (WHERE investor_type = 'dealer') AS dealer_net_shares"""
                rows = self._query(table, (
                    f"SELECT trade_date, count(*) AS row_count, count(DISTINCT symbol) AS covered_symbols, "
                    "list_sort(list(DISTINCT source_id)) AS source_ids, "
                    "list_sort(list(DISTINCT provenance_id)) AS provenance_ids, "
                    f"list_sort(list(DISTINCT execution_id)) AS execution_ids, {aggregates} FROM {table} "
                    f"WHERE trade_date = (SELECT max(trade_date) FROM {table}) GROUP BY trade_date"
                ), ())
                row = rows[0] if rows else None
                data_fields = ("day_trade_shares", "day_trade_buy_twd", "day_trade_sell_twd") if dataset == "market-activity" else (
                    "foreign_net_shares", "investment_trust_net_shares", "dealer_net_shares")
                data = {key: row[key] for key in data_fields if row and row.get(key) is not None}
                sections[dataset] = self._market_section(
                    row, today, int(row["row_count"]) if row else 0,
                    {"received_symbols": int(row["covered_symbols"]) if row else 0, "expected_symbols": None}, data)
            except Exception:
                sections[dataset] = self._market_section(None, today, 0, {}, unavailable=True)
        dates = [part["as_of"] for part in sections.values()]
        available = [part for part in sections.values() if part["status"] in {"available", "partial", "stale"}]
        return {"schema_version": "market-home.v1", "as_of": dates[0] if dates[0] and len(set(dates)) == 1 else None,
                "status": "missing" if not available else "available" if len(available) == len(sections)
                and all(part["status"] == "available" for part in sections.values()) else "partial",
                "sections": sections}

    @staticmethod
    def _market_section(row: Mapping[str, Any] | None, today: date, row_count: int,
                        coverage: Mapping[str, Any], data: Mapping[str, Any] | None = None,
                        *, unavailable: bool = False) -> dict[str, Any]:
        as_of = str(row.get("trade_date")) if row and row.get("trade_date") else None
        try:
            age = (today - date.fromisoformat(as_of)).days if as_of else None
        except ValueError:
            age = -1
        if row and (age is None or age < 0):
            return {"status": "unavailable", "as_of": None, "freshness_days": None,
                    "row_count": 0, "coverage": {}, "provenance": {}, "data": {}}
        values = dict(data) if data is not None else {
            key: row[key] for key in ("benchmark_id", "close", "return_percent", "index_kind")
            if row and row.get(key) is not None}
        metric_count = len(data) if data is not None else int("close" in values)
        expected_metrics = 3 if data is not None else 1
        return {"status": "unavailable" if unavailable else "missing" if not row or not metric_count else
                "stale" if age is not None and age > 7 else "partial" if metric_count < expected_metrics else "available",
                "as_of": as_of, "freshness_days": age, "row_count": row_count,
                "coverage": dict(coverage),
                "provenance": {key: [str(item) for item in row[key] if item is not None]
                               for key in ("source_ids", "provenance_ids", "execution_ids")
                               if row and row.get(key) is not None} if data is not None else {
                    key: str(row[key]) for key in ("source_id", "provenance_id", "execution_id")
                    if row and row.get(key) is not None},
                "data": values}

    def summary(self, symbol: str, *, datasets: Sequence[str] | None = None) -> dict[str, Any]:
        normalized_symbol = self._symbol(symbol)
        # A stock symbol cannot be used as a benchmark_id. Benchmark remains
        # queryable explicitly (for example TAIEX), but is not mixed into a
        # stock summary without an explicit market-to-benchmark mapping.
        selected = tuple(datasets or self.DEFAULT_SUMMARY_DATASETS)
        result: dict[str, Any] = {"symbol": normalized_symbol, "datasets": {}}
        for dataset in selected:
            page = self.page(dataset, normalized_symbol, limit=self.max_limit)
            rows = page.rows
            profile_rows = self._query(
                self.TABLE_NAMES[dataset],
                f"SELECT count(*) AS __row_count, count(COLUMNS(*)) FROM {self.TABLE_NAMES[dataset]} "
                f"WHERE {self.FILTER_FIELDS[dataset]} = ?",
                (normalized_symbol,),
            )
            profile = dict(profile_rows[0]) if profile_rows else {}
            row_count = int(profile.pop("__row_count", 0))
            result["datasets"][dataset] = {
                "row_count": row_count,
                "coverage": {"received_symbols": 1 if row_count else 0, "requested_symbols": 1},
                "latest_date": self._latest_date(rows),
                "null_profile": {
                    field: row_count - int(non_null_count)
                    for field, non_null_count in sorted(profile.items())
                    if not _is_hidden_key(field) and row_count - int(non_null_count)
                },
                "quality_flags": sorted({
                    str(row["quality_flag"]) for row in rows
                    if row.get("quality_flag") not in (None, "")
                }),
                "associations": self._associations(rows),
            }
        return result

    @classmethod
    def _dataset(cls, dataset_id: str) -> str:
        if dataset_id not in cls.DATASETS:
            raise QueryValidationError("dataset is not available")
        return dataset_id

    @staticmethod
    def _symbol(symbol: str) -> str:
        value = str(symbol).strip().upper()
        if not value or len(value) > 20 or not all(c.isalnum() or c in "-_" for c in value):
            raise QueryValidationError("symbol is invalid")
        return value

    @classmethod
    def _latest_date(cls, rows: Sequence[Mapping[str, Any]]) -> str | None:
        values = []
        for row in rows:
            for field in cls.DATE_FIELDS:
                value = row.get(field)
                if value is not None:
                    values.append(value.isoformat() if hasattr(value, "isoformat") else str(value))
                    break
        return max(values) if values else None

    @staticmethod
    def _null_profile(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            for key, value in row.items():
                if value is None:
                    counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _associations(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
        """Expose only correlation metadata, never raw payload or credentials."""
        fields = ("source_id", "dataset_id", "provenance_id", "execution_id", "snapshot_id")
        return {field: sorted({str(row[field]) for row in rows if row.get(field) not in (None, "")}) for field in fields}
