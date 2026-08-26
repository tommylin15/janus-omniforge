"""Durable control-plane models and repository implementations.

SQLite remains the fast, isolated unit-test reference.  PostgreSQLControlPlane
uses the same domain objects and transition rules for production persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from uuid import uuid4


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    RETRYING = "retrying"


class TriggerType(StrEnum):
    COLLECTION = "collection"
    ANALYSIS = "analysis"


class DataState(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    PARTIAL = "partial"
    FALLBACK = "fallback"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    SCHEMA_DRIFT = "schema_drift"
    FAILED = "failed"


class ControlPlaneError(RuntimeError):
    """Base class for safe, user-facing control-plane errors."""


class StockInUseError(ControlPlaneError):
    """Raised when a stock is still referenced by control records."""


class InvalidTransitionError(ControlPlaneError):
    """Raised when an execution state transition is not allowed."""


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    market: str
    enabled: bool = True
    updated_at: datetime | None = None


@dataclass(frozen=True)
class CollectionConfig:
    config_id: str
    dataset_id: str
    source_ids: tuple[str, ...]
    expected_fields: frozenset[str]
    market: str = "TWSE"
    enabled: bool = True
    collection_enabled: bool = True
    analysis_enabled: bool = True
    lookback_days: int = 30
    overlap_days: int = 2
    full_refresh_interval_days: int = 0
    batch_scope: str = "market"

    def __post_init__(self) -> None:
        if not self.config_id or not self.dataset_id or not self.source_ids:
            raise ValueError("config_id, dataset_id, and source_ids are required")
        if any(not source_id.strip() for source_id in self.source_ids):
            raise ValueError("source_ids cannot contain empty values")
        if self.batch_scope not in {"market", "symbol"}:
            raise ValueError("batch_scope must be market or symbol")
        if self.lookback_days < 0 or self.overlap_days < 0 or self.full_refresh_interval_days < 0:
            raise ValueError("collection windows cannot be negative")


@dataclass(frozen=True)
class Execution:
    execution_id: str
    trace_id: str
    config_id: str
    trigger_type: TriggerType
    status: ExecutionStatus
    requested_symbols: tuple[str, ...]
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    retry_count: int
    error_code: str | None


@dataclass(frozen=True)
class ExecutionItem:
    execution_id: str
    item_key: str
    source_id: str
    dataset_id: str
    state: DataState
    rows_received: int
    retry_count: int
    cache_hit: bool
    is_fallback: bool
    error_code: str | None
    safe_message: str | None


@dataclass(frozen=True)
class Cursor:
    cursor_key: str
    last_observed_at: datetime | None
    last_success_at: datetime | None


@dataclass(frozen=True)
class CacheMetadata:
    cache_key: str
    source_id: str
    dataset_id: str
    payload_uri: str
    content_hash: str
    fetched_at: datetime
    expires_at: datetime
    observed_at: datetime | None
    state: DataState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS stock_master (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('TWSE', 'TPEX')),
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collection_configs (
    config_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    source_ids TEXT NOT NULL,
    expected_fields TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('TWSE', 'TPEX')),
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    collection_enabled INTEGER NOT NULL CHECK (collection_enabled IN (0, 1)),
    analysis_enabled INTEGER NOT NULL CHECK (analysis_enabled IN (0, 1)),
    lookback_days INTEGER NOT NULL CHECK (lookback_days >= 0),
    overlap_days INTEGER NOT NULL CHECK (overlap_days >= 0),
    full_refresh_interval_days INTEGER NOT NULL CHECK (full_refresh_interval_days >= 0),
    batch_scope TEXT NOT NULL CHECK (batch_scope IN ('market', 'symbol'))
);
CREATE TABLE IF NOT EXISTS collection_symbols (
    config_id TEXT NOT NULL REFERENCES collection_configs(config_id) ON DELETE RESTRICT,
    symbol TEXT NOT NULL REFERENCES stock_master(symbol) ON DELETE RESTRICT,
    PRIMARY KEY (config_id, symbol)
);
CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    config_id TEXT NOT NULL REFERENCES collection_configs(config_id) ON DELETE RESTRICT,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('collection', 'analysis')),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'partial', 'failed', 'retrying')),
    requested_symbols TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT
);
CREATE INDEX IF NOT EXISTS executions_recent_idx ON executions(requested_at DESC);
CREATE TABLE IF NOT EXISTS execution_symbols (
    execution_id TEXT NOT NULL REFERENCES executions(execution_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL REFERENCES stock_master(symbol) ON DELETE RESTRICT,
    PRIMARY KEY (execution_id, symbol)
);
CREATE TABLE IF NOT EXISTS execution_items (
    execution_id TEXT NOT NULL REFERENCES executions(execution_id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    source_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    state TEXT NOT NULL,
    rows_received INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    is_fallback INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    safe_message TEXT,
    PRIMARY KEY (execution_id, item_key)
);
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    observed_at TEXT
);
CREATE TABLE IF NOT EXISTS collection_cursors (
    cursor_key TEXT PRIMARY KEY,
    last_observed_at TEXT,
    last_success_at TEXT
);
CREATE TABLE IF NOT EXISTS source_health (
    source_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    total_latency_ms REAL NOT NULL DEFAULT 0,
    last_fetched_at TEXT,
    latest_observation_at TEXT,
    last_state TEXT,
    PRIMARY KEY (source_id, dataset_id)
);
"""


class SQLiteControlPlane:
    """Small durable control repository with explicit transition enforcement."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(database), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def upsert_stock(self, stock: Stock) -> Stock:
        symbol = _symbol(stock.symbol)
        if not stock.name.strip():
            raise ValueError("stock name is required")
        if stock.market not in {"TWSE", "TPEX"}:
            raise ValueError("market must be TWSE or TPEX")
        timestamp = _iso(stock.updated_at or utc_now())
        self.connection.execute(
            """INSERT INTO stock_master(symbol, name, market, enabled, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, market=excluded.market,
               enabled=excluded.enabled, updated_at=excluded.updated_at""",
            (symbol, stock.name.strip(), stock.market, int(stock.enabled), timestamp),
        )
        self.connection.commit()
        return Stock(symbol, stock.name.strip(), stock.market, stock.enabled, _parse_time(timestamp))

    def set_stock_enabled(self, symbol: str, enabled: bool) -> None:
        cursor = self.connection.execute("UPDATE stock_master SET enabled=?, updated_at=? WHERE symbol=?", (int(enabled), _iso(utc_now()), _symbol(symbol)))
        if cursor.rowcount != 1:
            raise KeyError("stock not found")
        self.connection.commit()

    def delete_stock(self, symbol: str) -> None:
        symbol = _symbol(symbol)
        references = self.connection.execute("SELECT COUNT(*) FROM collection_symbols WHERE symbol=?", (symbol,)).fetchone()[0]
        references += self.connection.execute("SELECT COUNT(*) FROM execution_symbols WHERE symbol=?", (symbol,)).fetchone()[0]
        if references:
            raise StockInUseError("stock is referenced by a collection configuration or execution")
        cursor = self.connection.execute("DELETE FROM stock_master WHERE symbol=?", (symbol,))
        if cursor.rowcount != 1:
            raise KeyError("stock not found")
        self.connection.commit()

    def search_stocks(self, query: str = "", *, enabled: bool | None = None, limit: int = 50, offset: int = 0) -> tuple[Stock, ...]:
        if limit < 1 or limit > 500 or offset < 0:
            raise ValueError("limit must be 1..500 and offset cannot be negative")
        clauses = ["(symbol LIKE ? OR name LIKE ?)"]
        args: list[Any] = [f"%{query}%", f"%{query}%"]
        if enabled is not None:
            clauses.append("enabled=?")
            args.append(int(enabled))
        args.extend([limit, offset])
        rows = self.connection.execute(
            f"SELECT * FROM stock_master WHERE {' AND '.join(clauses)} ORDER BY symbol LIMIT ? OFFSET ?", args
        ).fetchall()
        return tuple(Stock(row["symbol"], row["name"], row["market"], bool(row["enabled"]), _parse_time(row["updated_at"])) for row in rows)

    def put_collection_config(self, config: CollectionConfig, symbols: Iterable[str] = ()) -> None:
        self.connection.execute(
            """INSERT INTO collection_configs(config_id, dataset_id, source_ids, expected_fields, market,
               enabled, collection_enabled, analysis_enabled, lookback_days, overlap_days,
               full_refresh_interval_days, batch_scope) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(config_id) DO UPDATE SET dataset_id=excluded.dataset_id,
               source_ids=excluded.source_ids, expected_fields=excluded.expected_fields,
               market=excluded.market, enabled=excluded.enabled, collection_enabled=excluded.collection_enabled,
               analysis_enabled=excluded.analysis_enabled, lookback_days=excluded.lookback_days,
               overlap_days=excluded.overlap_days, full_refresh_interval_days=excluded.full_refresh_interval_days,
               batch_scope=excluded.batch_scope""",
            (config.config_id, config.dataset_id, json.dumps(config.source_ids), json.dumps(sorted(config.expected_fields)), config.market,
             int(config.enabled), int(config.collection_enabled), int(config.analysis_enabled), config.lookback_days,
             config.overlap_days, config.full_refresh_interval_days, config.batch_scope),
        )
        self.connection.execute("DELETE FROM collection_symbols WHERE config_id=?", (config.config_id,))
        for symbol in symbols:
            symbol = _symbol(symbol)
            exists = self.connection.execute("SELECT 1 FROM stock_master WHERE symbol=?", (symbol,)).fetchone()
            if exists is None:
                raise KeyError(f"stock not found: {symbol}")
            self.connection.execute("INSERT INTO collection_symbols(config_id, symbol) VALUES (?, ?)", (config.config_id, symbol))
        self.connection.commit()

    def get_collection_config(self, config_id: str) -> CollectionConfig:
        row = self.connection.execute("SELECT * FROM collection_configs WHERE config_id=?", (config_id,)).fetchone()
        if row is None:
            raise KeyError("collection config not found")
        return CollectionConfig(row["config_id"], row["dataset_id"], tuple(json.loads(row["source_ids"])), frozenset(json.loads(row["expected_fields"])), row["market"], bool(row["enabled"]), bool(row["collection_enabled"]), bool(row["analysis_enabled"]), row["lookback_days"], row["overlap_days"], row["full_refresh_interval_days"], row["batch_scope"])

    def config_symbols(self, config_id: str, *, only_enabled: bool = True) -> tuple[str, ...]:
        condition = " AND s.enabled=1" if only_enabled else ""
        rows = self.connection.execute(f"SELECT cs.symbol FROM collection_symbols cs JOIN stock_master s ON s.symbol=cs.symbol WHERE cs.config_id=?{condition} ORDER BY cs.symbol", (config_id,)).fetchall()
        return tuple(row["symbol"] for row in rows)

    def enqueue_collection(self, config_id: str, symbols: Iterable[str] | None = None, *, trace_id: str | None = None) -> Execution:
        return self._enqueue(config_id, TriggerType.COLLECTION, symbols, trace_id)

    def enqueue_analysis(self, config_id: str, symbols: Iterable[str] | None = None, *, trace_id: str | None = None) -> Execution:
        return self._enqueue(config_id, TriggerType.ANALYSIS, symbols, trace_id)

    def _enqueue(self, config_id: str, trigger_type: TriggerType, symbols: Iterable[str] | None, trace_id: str | None) -> Execution:
        config = self.get_collection_config(config_id)
        if not config.enabled or not getattr(config, f"{trigger_type.value}_enabled"):
            raise ControlPlaneError(f"{trigger_type.value} trigger is disabled")
        requested = tuple(sorted({_symbol(value) for value in (symbols if symbols is not None else self.config_symbols(config_id))}))
        if not requested:
            raise ControlPlaneError("no enabled stocks are selected")
        unknown = [value for value in requested if self.connection.execute("SELECT 1 FROM stock_master WHERE symbol=?", (value,)).fetchone() is None]
        if unknown:
            raise KeyError(f"stock not found: {unknown[0]}")
        execution_id = str(uuid4())
        timestamp = _iso(utc_now())
        self.connection.execute("INSERT INTO executions(execution_id, trace_id, config_id, trigger_type, status, requested_symbols, requested_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (execution_id, trace_id or str(uuid4()), config_id, trigger_type.value, ExecutionStatus.QUEUED.value, json.dumps(requested), timestamp))
        self.connection.executemany("INSERT INTO execution_symbols(execution_id, symbol) VALUES (?, ?)", ((execution_id, symbol) for symbol in requested))
        self.connection.commit()
        return self.get_execution(execution_id)

    def get_execution(self, execution_id: str) -> Execution:
        row = self.connection.execute("SELECT * FROM executions WHERE execution_id=?", (execution_id,)).fetchone()
        if row is None:
            raise KeyError("execution not found")
        return Execution(row["execution_id"], row["trace_id"], row["config_id"], TriggerType(row["trigger_type"]), ExecutionStatus(row["status"]), tuple(json.loads(row["requested_symbols"])), _parse_time(row["requested_at"]), _parse_time(row["started_at"]), _parse_time(row["finished_at"]), row["retry_count"], row["error_code"])

    def list_executions(self, *, limit: int = 50) -> tuple[Execution, ...]:
        if limit < 1 or limit > 50:
            raise ValueError("limit must be 1..50")
        rows = self.connection.execute("SELECT execution_id FROM executions ORDER BY requested_at DESC LIMIT ?", (limit,)).fetchall()
        return tuple(self.get_execution(row["execution_id"]) for row in rows)

    def transition_execution(self, execution_id: str, status: ExecutionStatus, *, error_code: str | None = None, retry_count: int | None = None) -> Execution:
        current = self.get_execution(execution_id)
        allowed = {
            ExecutionStatus.QUEUED: {ExecutionStatus.RUNNING, ExecutionStatus.RETRYING, ExecutionStatus.FAILED},
            ExecutionStatus.RETRYING: {ExecutionStatus.RUNNING, ExecutionStatus.RETRYING, ExecutionStatus.FAILED},
            ExecutionStatus.RUNNING: {ExecutionStatus.SUCCEEDED, ExecutionStatus.PARTIAL, ExecutionStatus.FAILED, ExecutionStatus.RETRYING},
            ExecutionStatus.SUCCEEDED: set(), ExecutionStatus.PARTIAL: set(), ExecutionStatus.FAILED: set(),
        }
        if status not in allowed[current.status]:
            raise InvalidTransitionError(f"cannot transition execution from {current.status} to {status}")
        started = current.started_at or (utc_now() if status in {ExecutionStatus.RUNNING, ExecutionStatus.RETRYING} else None)
        finished = utc_now() if status in {ExecutionStatus.SUCCEEDED, ExecutionStatus.PARTIAL, ExecutionStatus.FAILED} else None
        self.connection.execute("UPDATE executions SET status=?, started_at=?, finished_at=?, retry_count=?, error_code=? WHERE execution_id=?", (status.value, _iso(started), _iso(finished), current.retry_count if retry_count is None else retry_count, error_code, execution_id))
        self.connection.commit()
        return self.get_execution(execution_id)

    def save_item(self, item: ExecutionItem) -> None:
        self.connection.execute(
            """INSERT INTO execution_items(execution_id, item_key, source_id, dataset_id, state,
               rows_received, retry_count, cache_hit, is_fallback, error_code, safe_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(execution_id, item_key) DO UPDATE SET source_id=excluded.source_id,
               dataset_id=excluded.dataset_id, state=excluded.state, rows_received=excluded.rows_received,
               retry_count=excluded.retry_count, cache_hit=excluded.cache_hit, is_fallback=excluded.is_fallback,
               error_code=excluded.error_code, safe_message=excluded.safe_message""",
            (item.execution_id, item.item_key, item.source_id, item.dataset_id, item.state.value, item.rows_received, item.retry_count, int(item.cache_hit), int(item.is_fallback), item.error_code, item.safe_message),
        )
        self.connection.commit()

    def list_items(self, execution_id: str) -> tuple[ExecutionItem, ...]:
        rows = self.connection.execute("SELECT * FROM execution_items WHERE execution_id=? ORDER BY item_key", (execution_id,)).fetchall()
        return tuple(ExecutionItem(row["execution_id"], row["item_key"], row["source_id"], row["dataset_id"], DataState(row["state"]), row["rows_received"], row["retry_count"], bool(row["cache_hit"]), bool(row["is_fallback"]), row["error_code"], row["safe_message"]) for row in rows)

    def put_cache(self, cache_key: str, source_id: str, dataset_id: str, payload: list[dict[str, Any]], content_hash_value: str, fetched_at: datetime, ttl: timedelta, observed_at: datetime | None = None) -> None:
        self.connection.execute("INSERT OR REPLACE INTO response_cache(cache_key, source_id, dataset_id, payload_json, content_hash, fetched_at, expires_at, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (cache_key, source_id, dataset_id, json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), content_hash_value, _iso(fetched_at), _iso(fetched_at + ttl), _iso(observed_at)))
        self.connection.commit()

    def get_cache(self, cache_key: str, *, now: datetime | None = None) -> tuple[list[dict[str, Any]], str, datetime | None] | None:
        row = self.connection.execute("SELECT * FROM response_cache WHERE cache_key=?", (cache_key,)).fetchone()
        if row is None or _parse_time(row["expires_at"]) <= (now or utc_now()):
            return None
        return list(json.loads(row["payload_json"])), row["content_hash"], _parse_time(row["observed_at"])

    def get_cursor(self, cursor_key: str) -> Cursor:
        row = self.connection.execute("SELECT * FROM collection_cursors WHERE cursor_key=?", (cursor_key,)).fetchone()
        return Cursor(cursor_key, _parse_time(row["last_observed_at"]) if row else None, _parse_time(row["last_success_at"]) if row else None)

    def advance_cursor(self, cursor_key: str, observed_at: datetime, *, successful: bool) -> None:
        current = self.get_cursor(cursor_key)
        latest = max(filter(None, (current.last_observed_at, observed_at)), default=observed_at)
        success = observed_at if successful else current.last_success_at
        self.connection.execute("INSERT OR REPLACE INTO collection_cursors(cursor_key, last_observed_at, last_success_at) VALUES (?, ?, ?)", (cursor_key, _iso(latest), _iso(success)))
        self.connection.commit()

    def record_health(self, source_id: str, dataset_id: str, *, state: DataState, latency_ms: float, fetched_at: datetime, latest_observation_at: datetime | None = None) -> None:
        success = int(state in {DataState.SUCCESS, DataState.FALLBACK, DataState.PARTIAL})
        self.connection.execute("""INSERT INTO source_health(source_id, dataset_id, success_count, failure_count, total_latency_ms, last_fetched_at, latest_observation_at, last_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(source_id, dataset_id) DO UPDATE SET success_count=source_health.success_count+excluded.success_count, failure_count=source_health.failure_count+excluded.failure_count, total_latency_ms=source_health.total_latency_ms+excluded.total_latency_ms, last_fetched_at=excluded.last_fetched_at, latest_observation_at=COALESCE(excluded.latest_observation_at, source_health.latest_observation_at), last_state=excluded.last_state""", (source_id, dataset_id, success, int(not success), latency_ms, _iso(fetched_at), _iso(latest_observation_at), state.value))
        self.connection.commit()

    def source_health(self, source_id: str, dataset_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM source_health WHERE source_id=? AND dataset_id=?", (source_id, dataset_id)).fetchone()
        if row is None:
            return None
        total = row["success_count"] + row["failure_count"]
        return {"source_id": source_id, "dataset_id": dataset_id, "success_rate": row["success_count"] / total if total else 0.0, "average_latency_ms": row["total_latency_ms"] / total if total else 0.0, "last_fetched_at": row["last_fetched_at"], "latest_observation_at": row["latest_observation_at"], "last_state": row["last_state"]}

    def __enter__(self) -> "SQLiteControlPlane":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _symbol(value: str) -> str:
    normalized = str(value).strip().upper()
    if not normalized or len(normalized) > 20 or not all(character.isalnum() or character in "-_" for character in normalized):
        raise ValueError("invalid stock symbol")
    return normalized
