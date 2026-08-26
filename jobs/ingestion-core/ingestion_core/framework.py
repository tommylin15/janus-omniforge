"""Bounded, retrying ingestion orchestration with durable execution evidence."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import inspect
import json
import time
from typing import Any, Mapping

from .adapters import CollectionRequest, ErrorCode, IngestionError, SourceAdapter, SourceResponse, classify_exception
from .control import CollectionConfig, DataState, ExecutionItem, ExecutionStatus, SQLiteControlPlane


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.initial_backoff_seconds < 0 or self.max_backoff_seconds < 0:
            raise ValueError("invalid retry policy")

    def delay(self, attempt: int) -> float:
        return min(self.max_backoff_seconds, self.initial_backoff_seconds * (2 ** max(0, attempt - 1)))


class FetchFailure(IngestionError):
    """Safe source error carrying the actual number of attempts made."""

    def __init__(self, error: IngestionError, attempts: int) -> None:
        super().__init__(error.code, error.safe_message, error.retryable, error.retry_after_seconds)
        self.attempts = attempts


class RateLimiter:
    """Per-process leaky-bucket limiter; a distributed limiter belongs in the queue layer."""

    def __init__(self, requests_per_second: float = 2.0) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.interval = 1.0 / requests_per_second
        self._next_allowed = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait_for = max(0.0, self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + self.interval
        if wait_for:
            await asyncio.sleep(wait_for)


@dataclass(frozen=True)
class IncrementalWindow:
    start: date | None
    end: date
    cursor_key: str


@dataclass(frozen=True)
class IngestionResult:
    execution_id: str
    trace_id: str
    status: ExecutionStatus
    rows: tuple[Mapping[str, Any], ...]
    item_states: tuple[DataState, ...]


class IngestionFramework:
    def __init__(self, control: SQLiteControlPlane, *, timeout_seconds: float = 30.0, retry_policy: RetryPolicy | None = None, rate_limit_per_second: float = 2.0, cache_ttl: timedelta = timedelta(minutes=15), sleep=asyncio.sleep) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 300:
            raise ValueError("timeout_seconds must be between 0 and 300")
        if cache_ttl.total_seconds() <= 0:
            raise ValueError("cache_ttl must be positive")
        self.control = control
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.cache_ttl = cache_ttl
        self.rate_limit_per_second = rate_limit_per_second
        if rate_limit_per_second <= 0:
            raise ValueError("rate_limit_per_second must be positive")
        self.limiters: dict[str, RateLimiter] = {}
        self.sleep = sleep

    def incremental_window(self, config: CollectionConfig, *, symbol: str, as_of: date) -> IncrementalWindow:
        cursor_key = f"{config.config_id}:{config.dataset_id}:{config.market}:{symbol if config.batch_scope == 'symbol' else '*'}"
        cursor = self.control.get_cursor(cursor_key)
        if cursor.last_success_at is None:
            start = as_of - timedelta(days=config.lookback_days) if config.lookback_days else None
        else:
            last = cursor.last_success_at.astimezone(timezone.utc).date()
            start = last - timedelta(days=config.overlap_days)
            if config.full_refresh_interval_days:
                age = (as_of - last).days
                if age >= config.full_refresh_interval_days:
                    start = as_of - timedelta(days=config.lookback_days) if config.lookback_days else None
        return IncrementalWindow(start, as_of, cursor_key)

    def cache_key(self, config: CollectionConfig, source_id: str, window: IncrementalWindow, symbols: tuple[str, ...]) -> str:
        selected = symbols if config.batch_scope == "symbol" else (config.market,)
        # A full-market endpoint returns one response for the market/day.  Its
        # cached payload covers later overlap windows on that same day.  Symbol
        # endpoints retain the exact start boundary to avoid missing history.
        start = window.start.isoformat() if window.start and config.batch_scope == "symbol" else None
        material = json.dumps({"source_id": source_id, "dataset_id": config.dataset_id, "expected_fields": sorted(config.expected_fields), "market": config.market, "symbols": selected, "start": start, "end": window.end.isoformat()}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(material.encode()).hexdigest()

    async def collect(self, execution_id: str, adapters: Mapping[str, SourceAdapter], *, as_of: date | None = None) -> IngestionResult:
        execution = self.control.get_execution(execution_id)
        config = self.control.get_collection_config(execution.config_id)
        if execution.trigger_type.value != "collection":
            raise ValueError("ingestion framework only processes collection executions")
        if execution.status not in {ExecutionStatus.QUEUED, ExecutionStatus.RETRYING}:
            raise ValueError("execution is not runnable")
        self.control.transition_execution(execution_id, ExecutionStatus.RUNNING)
        analysis_date = as_of or datetime.now(timezone.utc).date()
        all_rows: list[Mapping[str, Any]] = []
        states: list[DataState] = []
        for symbol in execution.requested_symbols if config.batch_scope == "symbol" else (execution.requested_symbols[0],):
            window = self.incremental_window(config, symbol=symbol, as_of=analysis_date)
            symbols = (symbol,) if config.batch_scope == "symbol" else execution.requested_symbols
            state, source_id, rows, attempts, cache_hit, fallback, code, message, observed = await self._collect_batch(execution.execution_id, execution.trace_id, config, symbols, window, adapters)
            item_key = f"{config.dataset_id}:{config.market}:{symbol if config.batch_scope == 'symbol' else 'market'}"
            self.control.save_item(ExecutionItem(execution_id, item_key, source_id, config.dataset_id, state, len(rows), attempts, cache_hit, fallback, code, message))
            states.append(state)
            all_rows.extend(rows)
            if observed is not None and state in {DataState.SUCCESS, DataState.FALLBACK}:
                self.control.advance_cursor(window.cursor_key, observed, successful=True)
        if states and all(state in {DataState.SUCCESS, DataState.FALLBACK} for state in states):
            final = ExecutionStatus.SUCCEEDED
        elif any(state in {DataState.SUCCESS, DataState.PARTIAL, DataState.FALLBACK} for state in states):
            final = ExecutionStatus.PARTIAL
        else:
            final = ExecutionStatus.FAILED
        error_code = next((item.error_code for item in self.control.list_items(execution_id) if item.error_code), None)
        self.control.transition_execution(execution_id, final, error_code=error_code if final == ExecutionStatus.FAILED else None)
        return IngestionResult(execution_id, execution.trace_id, final, tuple(all_rows), tuple(states))

    async def _collect_batch(self, execution_id: str, trace_id: str, config: CollectionConfig, symbols: tuple[str, ...], window: IncrementalWindow, adapters: Mapping[str, SourceAdapter]):
        last_code = None
        last_message = None
        last_state = DataState.UNAVAILABLE
        total_attempts = 0
        for source_position, source_id in enumerate(config.source_ids):
            adapter = adapters.get(source_id)
            if adapter is None:
                last_code, last_message = ErrorCode.UNAVAILABLE.value, "source adapter is unavailable"
                continue
            key = self.cache_key(config, source_id, window, symbols)
            cached = self.control.get_cache(key)
            if cached is not None:
                payload, _, observed = cached
                return DataState.SUCCESS, source_id, self._select_rows(payload, symbols), total_attempts, True, source_position > 0, None, None, observed
            limiter = self.limiters.setdefault(source_id, RateLimiter(self.rate_limit_per_second))
            request = CollectionRequest(execution_id, trace_id, source_id, config.dataset_id, config.market, symbols, window.start, window.end, self.timeout_seconds)
            started = time.monotonic()
            try:
                response, attempts = await self._fetch(adapter, request, limiter, execution_id)
                total_attempts += attempts
                state = self._validate_response(response, config)
                if state == DataState.SCHEMA_DRIFT:
                    last_state = state
                    last_code, last_message = ErrorCode.SCHEMA_DRIFT.value, "source response schema changed"
                    self.control.record_health(source_id, config.dataset_id, state=state, latency_ms=(time.monotonic() - started) * 1000, fetched_at=datetime.now(timezone.utc), latest_observation_at=response.observed_at)
                    continue
                if not response.rows:
                    last_state = DataState.EMPTY
                    last_code, last_message = ErrorCode.EMPTY_RESPONSE.value, "source returned no rows"
                    self.control.record_health(source_id, config.dataset_id, state=DataState.EMPTY, latency_ms=(time.monotonic() - started) * 1000, fetched_at=datetime.now(timezone.utc), latest_observation_at=response.observed_at)
                    continue
                state = DataState.STALE if response.stale_as_of else (DataState.PARTIAL if response.is_partial else (DataState.FALLBACK if response.is_fallback or source_position > 0 else DataState.SUCCESS))
                if state == DataState.STALE and source_position + 1 < len(config.source_ids):
                    last_state = state
                    last_code, last_message = DataState.STALE.value, "source data is stale"
                    continue
                payload = [dict(row) for row in response.rows]
                digest = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
                # Only a fresh, primary, complete response is reusable.  A
                # partial/fallback/stale payload must remain visible as such on
                # the next execution and must not be promoted by the cache.
                if state == DataState.SUCCESS:
                    self.control.put_cache(key, source_id, config.dataset_id, payload, digest, datetime.now(timezone.utc), self.cache_ttl, response.observed_at)
                self.control.record_health(source_id, config.dataset_id, state=state, latency_ms=(time.monotonic() - started) * 1000, fetched_at=datetime.now(timezone.utc), latest_observation_at=response.observed_at)
                return state, source_id, self._select_rows(payload, symbols), total_attempts, False, source_position > 0 or response.is_fallback, None, None, response.observed_at
            except FetchFailure as error:
                last_state = DataState.UNAVAILABLE
                total_attempts += error.attempts
                last_code, last_message = error.code.value, error.safe_message
                self.control.record_health(source_id, config.dataset_id, state=DataState.UNAVAILABLE, latency_ms=(time.monotonic() - started) * 1000, fetched_at=datetime.now(timezone.utc))
            except IngestionError as error:
                last_state = DataState.UNAVAILABLE
                total_attempts += self.retry_policy.max_attempts
                last_code, last_message = error.code.value, error.safe_message
                self.control.record_health(source_id, config.dataset_id, state=DataState.UNAVAILABLE, latency_ms=(time.monotonic() - started) * 1000, fetched_at=datetime.now(timezone.utc))
        return last_state, config.source_ids[-1], (), total_attempts, False, False, last_code, last_message, None

    async def _fetch(self, adapter: SourceAdapter, request: CollectionRequest, limiter: RateLimiter, execution_id: str) -> tuple[SourceResponse, int]:
        last: IngestionError | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            await limiter.acquire()
            try:
                fetch = adapter.fetch
                async def invoke() -> SourceResponse:
                    result = fetch(request) if inspect.iscoroutinefunction(fetch) else await asyncio.to_thread(fetch, request)
                    return await result if inspect.isawaitable(result) else result

                response = await asyncio.wait_for(invoke(), timeout=request.timeout_seconds)
                if not isinstance(response, SourceResponse):
                    raise IngestionError(ErrorCode.INVALID_RESPONSE, "source returned an invalid response")
                return response, attempt
            except asyncio.TimeoutError:
                last = IngestionError(ErrorCode.TIMEOUT, "source request timed out", True)
            except Exception as error:
                last = classify_exception(error)
            if not last.retryable or attempt == self.retry_policy.max_attempts:
                raise FetchFailure(last, attempt)
            self.control.transition_execution(execution_id, ExecutionStatus.RETRYING, retry_count=attempt)
            await self.sleep(last.retry_after_seconds if last.retry_after_seconds is not None else self.retry_policy.delay(attempt))
            self.control.transition_execution(execution_id, ExecutionStatus.RUNNING, retry_count=attempt)
        raise last or IngestionError(ErrorCode.UNAVAILABLE, "source is unavailable", True)

    @staticmethod
    def _select_rows(rows: list[dict[str, Any]], symbols: tuple[str, ...]) -> tuple[Mapping[str, Any], ...]:
        selected = set(symbols)
        if not rows or "symbol" not in rows[0]:
            return tuple(rows)
        return tuple(row for row in rows if str(row.get("symbol")) in selected)

    @staticmethod
    def _validate_response(response: SourceResponse, config: CollectionConfig) -> DataState:
        if not response.rows:
            return DataState.EMPTY
        if config.expected_fields and config.expected_fields != response.fields:
            return DataState.SCHEMA_DRIFT
        return DataState.SUCCESS
