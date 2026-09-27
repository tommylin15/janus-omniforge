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
        for benchmark_id in ("TAIEX", "TPEx"):
            key = benchmark_id.lower()
            try:
                rows = self.page("benchmark", benchmark_id, limit=1).rows
                row = rows[0] if rows else None
                sections[key] = self._market_section(row, today, 1 if row else 0,
                                                      {"requested_symbols": 1, "received_symbols": 1 if row else 0})
            except RuntimeError:
                sections[key] = self._market_section(None, today, 0, {}, unavailable=True)
        for dataset in ("market-activity", "institutional"):
            table = self.TABLE_NAMES[dataset]
            try:
                latest = self._query(table, f"SELECT max(trade_date) AS trade_date FROM {table}", ())
                day = latest[0]["trade_date"] if latest else None
                if day:
                    counts = self._query(table, (
                        f"SELECT count(*) AS row_count, count(DISTINCT symbol) AS covered_symbols "
                        f"FROM {table} WHERE trade_date = ?"
                    ), (day,))[0]
                    sample = self._query(table, (
                        f"SELECT source_id, provenance_id, execution_id FROM {table} "
                        "WHERE trade_date = ? LIMIT 1"
                    ), (day,))
                    if dataset == "market-activity":
                        values = self._query(table, (
                            f"SELECT metric, sum(try_cast(value AS DOUBLE)) AS total_value "
                            f"FROM {table} WHERE trade_date = ? AND metric IN "
                            "('day_trade_shares', 'day_trade_buy_twd', 'day_trade_sell_twd') GROUP BY metric"
                        ), (day,))
                        data = {str(value["metric"]): value["total_value"] for value in values}
                    else:
                        values = self._query(table, (
                            f"SELECT investor_type, sum(try_cast(net_shares AS DOUBLE)) AS net_shares "
                            f"FROM {table} WHERE trade_date = ? AND investor_type IN "
                            "('foreign', 'investment_trust', 'dealer') GROUP BY investor_type"
                        ), (day,))
                        data = {f"{value['investor_type']}_net_shares": value["net_shares"] for value in values}
                    row = {"trade_date": day, **(dict(sample[0]) if sample else {})}
                    sections[dataset] = self._market_section(
                        row, today, int(counts["row_count"]),
                        {"received_symbols": int(counts["covered_symbols"]), "expected_symbols": None}, data)
                else:
                    sections[dataset] = self._market_section(None, today, 0, {})
            except Exception:
                sections[dataset] = self._market_section(None, today, 0, {}, unavailable=True)
        dates = [part["as_of"] for part in sections.values() if part["as_of"]]
        available = [part for part in sections.values() if part["status"] in {"available", "stale"}]
        return {"schema_version": "market-home.v1", "as_of": max(dates) if dates else None,
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
        return {"status": "unavailable" if unavailable else "missing" if not row else
                "stale" if age is not None and age > 7 else "available",
                "as_of": as_of, "freshness_days": age, "row_count": row_count,
                "coverage": dict(coverage),
                "provenance": {key: str(row[key]) for key in ("source_id", "provenance_id", "execution_id")
                               if row and row.get(key) is not None},
                "data": dict(data) if data is not None else {
                    key: row[key] for key in ("benchmark_id", "close", "return_percent", "index_kind")
                    if row and row.get(key) is not None}}

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
