"""PostgreSQL control-plane adapter.

The adapter intentionally accepts an injected DB-API connection factory.  This
keeps imports and tests lightweight while allowing production to use psycopg3
or a small external pool.  One connection is held per repository instance;
callers should create bounded instances according to the connection budget.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Callable, Iterator
from uuid import uuid4

from .control import (
    CacheMetadata, CollectionConfig, ControlPlaneError, Cursor, DataState,
    Execution, ExecutionItem, ExecutionStatus, InvalidTransitionError, Stock,
    StockInUseError, TriggerType, _iso, _parse_time, _symbol, utc_now,
)


class PostgreSQLControlPlane:
    """Transactional PostgreSQL repository for control metadata only."""

    def __init__(self, connection_factory: Callable[[], Any], *, statement_timeout_ms: int = 5000,
                 idle_in_transaction_timeout_ms: int = 10000) -> None:
        self.connection = connection_factory()
        self._closed = False
        with self.connection.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (statement_timeout_ms,))
            cur.execute("SET idle_in_transaction_session_timeout = %s", (idle_in_transaction_timeout_ms,))
        self.connection.commit()

    def close(self) -> None:
        if not self._closed:
            self.connection.close()
            self._closed = True

    @contextmanager
    def _tx(self) -> Iterator[Any]:
        try:
            with self.connection.cursor() as cur:
                yield cur
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def upsert_stock(self, stock: Stock) -> Stock:
        symbol = _symbol(stock.symbol)
        if not stock.name.strip() or stock.market not in {"TWSE", "TPEX"}:
            raise ValueError("stock name and market are invalid")
        timestamp = stock.updated_at or utc_now()
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.stock_master(symbol,name,market,enabled,updated_at)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT(symbol) DO UPDATE SET name=EXCLUDED.name,
                market=EXCLUDED.market,enabled=EXCLUDED.enabled,updated_at=EXCLUDED.updated_at""",
                (symbol, stock.name.strip(), stock.market, stock.enabled, timestamp))
        return Stock(symbol, stock.name.strip(), stock.market, stock.enabled, timestamp)

    def set_stock_enabled(self, symbol: str, enabled: bool) -> None:
        with self._tx() as cur:
            cur.execute("UPDATE control.stock_master SET enabled=%s,updated_at=now() WHERE symbol=%s", (enabled, _symbol(symbol)))
            if cur.rowcount != 1:
                raise KeyError("stock not found")

    def delete_stock(self, symbol: str) -> None:
        symbol = _symbol(symbol)
        with self._tx() as cur:
            cur.execute("SELECT EXISTS(SELECT 1 FROM control.collection_symbols WHERE symbol=%s UNION ALL SELECT 1 FROM control.execution_symbols WHERE symbol=%s)", (symbol, symbol))
            if cur.fetchone()[0]:
                raise StockInUseError("stock is referenced by a collection configuration or execution")
            cur.execute("DELETE FROM control.stock_master WHERE symbol=%s", (symbol,))
            if cur.rowcount != 1:
                raise KeyError("stock not found")

    def search_stocks(self, query: str = "", *, enabled: bool | None = None, limit: int = 50, offset: int = 0) -> tuple[Stock, ...]:
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("limit must be 1..500 and offset cannot be negative")
        clauses = ["(symbol ILIKE %s OR name ILIKE %s)"]
        args: list[Any] = [f"%{query}%", f"%{query}%"]
        if enabled is not None:
            clauses.append("enabled=%s"); args.append(enabled)
        args.extend([limit, offset])
        with self.connection.cursor() as cur:
            cur.execute(f"SELECT symbol,name,market,enabled,updated_at FROM control.stock_master WHERE {' AND '.join(clauses)} ORDER BY symbol LIMIT %s OFFSET %s", args)
            return tuple(Stock(r[0], r[1], r[2], r[3], r[4]) for r in cur.fetchall())

    def put_collection_config(self, config: CollectionConfig, symbols: tuple[str, ...] | list[str] = ()) -> None:
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.collection_configs(config_id,dataset_id,source_ids,expected_fields,market,enabled,collection_enabled,analysis_enabled,lookback_days,overlap_days,full_refresh_interval_days,batch_scope)
                VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(config_id) DO UPDATE SET dataset_id=EXCLUDED.dataset_id,source_ids=EXCLUDED.source_ids,expected_fields=EXCLUDED.expected_fields,market=EXCLUDED.market,enabled=EXCLUDED.enabled,collection_enabled=EXCLUDED.collection_enabled,analysis_enabled=EXCLUDED.analysis_enabled,lookback_days=EXCLUDED.lookback_days,overlap_days=EXCLUDED.overlap_days,full_refresh_interval_days=EXCLUDED.full_refresh_interval_days,batch_scope=EXCLUDED.batch_scope""",
                (config.config_id, config.dataset_id, json.dumps(config.source_ids), json.dumps(sorted(config.expected_fields)), config.market, config.enabled, config.collection_enabled, config.analysis_enabled, config.lookback_days, config.overlap_days, config.full_refresh_interval_days, config.batch_scope))
            cur.execute("DELETE FROM control.collection_symbols WHERE config_id=%s", (config.config_id,))
            for symbol in symbols:
                cur.execute("INSERT INTO control.collection_symbols(config_id,symbol) VALUES (%s,%s)", (config.config_id, _symbol(symbol)))

    def get_collection_config(self, config_id: str) -> CollectionConfig:
        with self.connection.cursor() as cur:
            cur.execute("SELECT config_id,dataset_id,source_ids,expected_fields,market,enabled,collection_enabled,analysis_enabled,lookback_days,overlap_days,full_refresh_interval_days,batch_scope FROM control.collection_configs WHERE config_id=%s", (config_id,))
            r = cur.fetchone()
        if not r: raise KeyError("collection config not found")
        return CollectionConfig(r[0], r[1], tuple(r[2]), frozenset(r[3]), r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11])

    def config_symbols(self, config_id: str, *, only_enabled: bool = True) -> tuple[str, ...]:
        condition = " AND s.enabled" if only_enabled else ""
        with self.connection.cursor() as cur:
            cur.execute(f"SELECT cs.symbol FROM control.collection_symbols cs JOIN control.stock_master s USING(symbol) WHERE cs.config_id=%s{condition} ORDER BY cs.symbol", (config_id,))
            return tuple(r[0] for r in cur.fetchall())

    def _enqueue(self, config_id: str, trigger: TriggerType, symbols: tuple[str, ...] | None, trace_id: str | None) -> Execution:
        config = self.get_collection_config(config_id)
        if not config.enabled or not getattr(config, f"{trigger.value}_enabled"):
            raise ControlPlaneError(f"{trigger.value} trigger is disabled")
        requested = tuple(sorted({_symbol(s) for s in (symbols if symbols is not None else self.config_symbols(config_id))}))
        if not requested: raise ControlPlaneError("no enabled stocks are selected")
        execution_id, correlation = uuid4(), trace_id or str(uuid4())
        with self._tx() as cur:
            cur.execute("SELECT symbol FROM control.stock_master WHERE symbol=ANY(%s)", (list(requested),))
            if {r[0] for r in cur.fetchall()} != set(requested): raise KeyError("stock not found")
            cur.execute("INSERT INTO control.executions(execution_id,trace_id,config_id,trigger_type,status,requested_symbols) VALUES (%s,%s,%s,%s,'queued',%s::jsonb)", (execution_id, correlation, config_id, trigger.value, json.dumps(requested)))
            cur.executemany("INSERT INTO control.execution_symbols(execution_id,symbol) VALUES (%s,%s)", [(execution_id, s) for s in requested])
        return self.get_execution(str(execution_id))

    def enqueue_collection(self, config_id: str, symbols: tuple[str, ...] | None = None, *, trace_id: str | None = None) -> Execution: return self._enqueue(config_id, TriggerType.COLLECTION, symbols, trace_id)
    def enqueue_analysis(self, config_id: str, symbols: tuple[str, ...] | None = None, *, trace_id: str | None = None) -> Execution: return self._enqueue(config_id, TriggerType.ANALYSIS, symbols, trace_id)

    def get_execution(self, execution_id: str) -> Execution:
        with self.connection.cursor() as cur:
            cur.execute("SELECT execution_id,trace_id,config_id,trigger_type,status,requested_symbols,requested_at,started_at,finished_at,retry_count,error_code FROM control.executions WHERE execution_id=%s", (execution_id,)); r = cur.fetchone()
        if not r: raise KeyError("execution not found")
        return Execution(str(r[0]), str(r[1]), r[2], TriggerType(r[3]), ExecutionStatus(r[4]), tuple(r[5]), r[6], r[7], r[8], r[9], r[10])

    def list_executions(self, *, limit: int = 50) -> tuple[Execution, ...]:
        if not 1 <= limit <= 50: raise ValueError("limit must be 1..50")
        with self.connection.cursor() as cur:
            cur.execute("SELECT execution_id FROM control.executions ORDER BY requested_at DESC LIMIT %s", (limit,)); ids = [str(r[0]) for r in cur.fetchall()]
        return tuple(self.get_execution(i) for i in ids)

    def claim_execution(self, worker_id: str, *, lease: timedelta = timedelta(minutes=5)) -> Execution | None:
        with self._tx() as cur:
            cur.execute("""WITH candidate AS (SELECT execution_id FROM control.executions WHERE status IN ('queued','retrying') AND (claimed_until IS NULL OR claimed_until < now()) ORDER BY requested_at FOR UPDATE SKIP LOCKED LIMIT 1)
                UPDATE control.executions e SET status='running',claimed_by=%s,claimed_until=now()+%s::interval,started_at=COALESCE(started_at,now()) FROM candidate WHERE e.execution_id=candidate.execution_id RETURNING e.execution_id""", (worker_id, f"{int(lease.total_seconds())} seconds"))
            row = cur.fetchone()
        return self.get_execution(str(row[0])) if row else None

    def transition_execution(self, execution_id: str, status: ExecutionStatus, *, error_code: str | None = None, retry_count: int | None = None) -> Execution:
        current = self.get_execution(execution_id)
        allowed = {ExecutionStatus.QUEUED:{ExecutionStatus.RUNNING,ExecutionStatus.RETRYING,ExecutionStatus.FAILED},ExecutionStatus.RETRYING:{ExecutionStatus.RUNNING,ExecutionStatus.RETRYING,ExecutionStatus.FAILED},ExecutionStatus.RUNNING:{ExecutionStatus.SUCCEEDED,ExecutionStatus.PARTIAL,ExecutionStatus.FAILED,ExecutionStatus.RETRYING}}
        if status not in allowed.get(current.status, set()): raise InvalidTransitionError(f"cannot transition execution from {current.status} to {status}")
        with self._tx() as cur:
            cur.execute("UPDATE control.executions SET status=%s,started_at=COALESCE(started_at,CASE WHEN %s IN ('running','retrying') THEN now() END),finished_at=CASE WHEN %s IN ('succeeded','partial','failed') THEN now() END,retry_count=COALESCE(%s,retry_count),error_code=%s,claimed_by=NULL,claimed_until=NULL WHERE execution_id=%s", (status.value,status.value,status.value,retry_count,error_code,execution_id))
        return self.get_execution(execution_id)

    def save_item(self, item: ExecutionItem) -> None:
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.execution_items(execution_id,item_key,source_id,dataset_id,state,rows_received,retry_count,cache_hit,is_fallback,error_code,safe_message)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(execution_id,item_key) DO UPDATE SET source_id=EXCLUDED.source_id,dataset_id=EXCLUDED.dataset_id,state=EXCLUDED.state,rows_received=EXCLUDED.rows_received,retry_count=EXCLUDED.retry_count,cache_hit=EXCLUDED.cache_hit,is_fallback=EXCLUDED.is_fallback,error_code=EXCLUDED.error_code,safe_message=EXCLUDED.safe_message""",
                (item.execution_id,item.item_key,item.source_id,item.dataset_id,item.state.value,item.rows_received,item.retry_count,item.cache_hit,item.is_fallback,item.error_code,item.safe_message))

    def list_items(self, execution_id: str) -> tuple[ExecutionItem, ...]:
        with self.connection.cursor() as cur:
            cur.execute("SELECT execution_id,item_key,source_id,dataset_id,state,rows_received,retry_count,cache_hit,is_fallback,error_code,safe_message FROM control.execution_items WHERE execution_id=%s ORDER BY item_key", (execution_id,))
            return tuple(ExecutionItem(str(r[0]),r[1],r[2],r[3],DataState(r[4]),r[5],r[6],r[7],r[8],r[9],r[10]) for r in cur.fetchall())

    def get_cursor(self, cursor_key: str) -> Cursor:
        with self.connection.cursor() as cur:
            cur.execute("SELECT last_observed_at,last_success_at FROM control.collection_cursors WHERE cursor_key=%s", (cursor_key,)); r = cur.fetchone()
        return Cursor(cursor_key, r[0] if r else None, r[1] if r else None)

    def advance_cursor(self, cursor_key: str, observed_at: datetime, *, successful: bool) -> None:
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.collection_cursors(cursor_key,last_observed_at,last_success_at) VALUES (%s,%s,%s)
                ON CONFLICT(cursor_key) DO UPDATE SET last_observed_at=GREATEST(control.collection_cursors.last_observed_at,EXCLUDED.last_observed_at),last_success_at=CASE WHEN EXCLUDED.last_success_at IS NOT NULL THEN EXCLUDED.last_success_at ELSE control.collection_cursors.last_success_at END""", (cursor_key, observed_at, observed_at if successful else None))

    def record_health(self, source_id: str, dataset_id: str, *, state: DataState, latency_ms: float, fetched_at: datetime, latest_observation_at: datetime | None = None) -> None:
        success = state in {DataState.SUCCESS, DataState.FALLBACK, DataState.PARTIAL}
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.source_health(source_id,dataset_id,success_count,failure_count,total_latency_ms,last_fetched_at,latest_observation_at,last_state) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(source_id,dataset_id) DO UPDATE SET success_count=control.source_health.success_count+EXCLUDED.success_count,failure_count=control.source_health.failure_count+EXCLUDED.failure_count,total_latency_ms=control.source_health.total_latency_ms+EXCLUDED.total_latency_ms,last_fetched_at=EXCLUDED.last_fetched_at,latest_observation_at=COALESCE(EXCLUDED.latest_observation_at,control.source_health.latest_observation_at),last_state=EXCLUDED.last_state""", (source_id,dataset_id,int(success),int(not success),latency_ms,fetched_at,latest_observation_at,state.value))

    def source_health(self, source_id: str, dataset_id: str) -> dict[str, Any] | None:
        with self.connection.cursor() as cur:
            cur.execute("SELECT success_count,failure_count,total_latency_ms,last_fetched_at,latest_observation_at,last_state FROM control.source_health WHERE source_id=%s AND dataset_id=%s", (source_id,dataset_id)); r = cur.fetchone()
        if not r: return None
        total = r[0] + r[1]
        return {"source_id":source_id,"dataset_id":dataset_id,"success_rate":r[0]/total if total else 0.0,"average_latency_ms":r[2]/total if total else 0.0,"last_fetched_at":r[3],"latest_observation_at":r[4],"last_state":r[5]}

    def put_cache(self, *_: Any, **__: Any) -> None:
        raise ControlPlaneError("PostgreSQL stores cache metadata only; write the response to GCS and call put_cache_metadata")

    def get_cache(self, *_: Any, **__: Any) -> None:
        raise ControlPlaneError("PostgreSQL stores cache metadata only; read the response from GCS using get_cache_metadata")

    def put_cache_metadata(self, metadata: CacheMetadata) -> None:
        if not metadata.payload_uri.startswith("gs://"): raise ValueError("payload_uri must be a gs:// URI")
        with self._tx() as cur:
            cur.execute("""INSERT INTO control.response_cache(cache_key,source_id,dataset_id,payload_uri,content_hash,fetched_at,expires_at,observed_at,state) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(cache_key) DO UPDATE SET payload_uri=EXCLUDED.payload_uri,content_hash=EXCLUDED.content_hash,fetched_at=EXCLUDED.fetched_at,expires_at=EXCLUDED.expires_at,observed_at=EXCLUDED.observed_at,state=EXCLUDED.state""", (metadata.cache_key,metadata.source_id,metadata.dataset_id,metadata.payload_uri,metadata.content_hash,metadata.fetched_at,metadata.expires_at,metadata.observed_at,metadata.state.value))

    def get_cache_metadata(self, cache_key: str, *, now: datetime | None = None) -> CacheMetadata | None:
        with self.connection.cursor() as cur:
            cur.execute("SELECT cache_key,source_id,dataset_id,payload_uri,content_hash,fetched_at,expires_at,observed_at,state FROM control.response_cache WHERE cache_key=%s AND expires_at>%s", (cache_key, now or utc_now())); r = cur.fetchone()
        return CacheMetadata(*r[:7], r[7], DataState(r[8])) if r else None

    def prune(self, *, before: datetime, batch_size: int = 500) -> dict[str, int]:
        counts = {}
        with self._tx() as cur:
            for table, column in (("response_cache","expires_at"),("executions","requested_at"),("source_health","last_fetched_at")):
                cur.execute(f"DELETE FROM control.{table} WHERE {column} < %s", (before,)); counts[table] = cur.rowcount
        return counts

    def __enter__(self) -> "PostgreSQLControlPlane": return self
    def __exit__(self, *_: object) -> None: self.close()
