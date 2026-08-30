"""Application boundary for public Core queries.

The service deliberately depends on a tiny read-only query callable instead of
owning a database connection.  Cloud Run can inject a bounded DuckDB/Iceberg
reader, while tests can use an in-memory callable.  This prevents request code
from opening connections or accidentally receiving Core write capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Mapping, Sequence


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
        sql = (
            f"SELECT * FROM {self.TABLE_NAMES[dataset]} "
            f"WHERE {self.FILTER_FIELDS[dataset]} = ? ORDER BY {self.ORDER_FIELDS[dataset]} DESC "
            "LIMIT ? OFFSET ?"
        )
        try:
            rows = self._query(self.TABLE_NAMES[dataset], sql, (normalized_symbol, limit, offset))
        except Exception as error:
            raise RuntimeError("Core query unavailable") from error
        return QueryPage(dataset, normalized_symbol, tuple(dict(row) for row in rows), limit, offset)

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
            result["datasets"][dataset] = {
                "row_count": len(rows),
                "coverage": {"received_symbols": 1 if rows else 0, "requested_symbols": 1},
                "latest_date": self._latest_date(rows),
                "null_profile": self._null_profile(rows),
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
