"""Application boundary for public Core queries.

The service deliberately depends on a tiny read-only query callable instead of
owning a database connection.  Cloud Run can inject a bounded DuckDB/Iceberg
reader, while tests can use an in-memory callable.  This prevents request code
from opening connections or accidentally receiving Core write capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
                 *, max_limit: int = 200) -> None:
        if not 1 <= max_limit <= 10_000:
            raise ValueError("max_limit must be between 1 and 10000")
        self._query = query
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

    def market_home(self) -> dict[str, Any]:
        """Published Core baseline; each fixed section fails independently."""
        today = datetime.now(ZoneInfo("Asia/Taipei")).date()
        sections: dict[str, dict[str, Any]] = {}
        benchmark_table = self.TABLE_NAMES["benchmark"]
        try:
            rows = self._query(benchmark_table, (
                f"WITH latest AS (SELECT upper(benchmark_id) AS benchmark_id, max(trade_date) AS trade_date "
                f"FROM {benchmark_table} WHERE upper(benchmark_id) = ? GROUP BY upper(benchmark_id)) "
                f"SELECT b.* FROM {benchmark_table} b JOIN latest l "
                "ON upper(b.benchmark_id) = l.benchmark_id AND b.trade_date = l.trade_date"
            ), ("TAIEX",))
            benchmarks = {str(row.get("benchmark_id", "")).upper(): row for row in rows}
        except Exception:
            benchmarks = None
        for benchmark_id in ("TAIEX",):
            row = benchmarks.get(benchmark_id) if benchmarks is not None else None
            sections[benchmark_id.lower()] = self._market_section(
                row, today, 1 if row else 0,
                {"requested_symbols": 1, "received_symbols": 1 if row else 0},
                unavailable=benchmarks is None)
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
