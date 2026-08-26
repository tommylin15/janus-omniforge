import asyncio
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core import (
    CallableAdapter, CollectionConfig, DataState, ErrorCode, IngestionError, IngestionFramework,
    RetryPolicy, SourceResponse, SQLiteControlPlane, Stock,
)


UTC = timezone.utc


def row(symbol="2330"):
    return {"symbol": symbol, "trade_date": "2026-08-25", "close": "100"}


class FrameworkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.control = SQLiteControlPlane()
        self.control.upsert_stock(Stock("2330", "台積電", "TWSE"))
        self.control.upsert_stock(Stock("2317", "鴻海", "TWSE"))

    async def asyncTearDown(self):
        self.control.close()

    def config(self, *, sources=("twse",), scope="market"):
        config = CollectionConfig("ohlcv-config", "ohlcv", sources, frozenset({"symbol", "trade_date", "close"}), batch_scope=scope, lookback_days=30, overlap_days=2)
        self.control.put_collection_config(config, ("2330", "2317"))
        return config

    async def execute(self, config, adapters, *, symbols=("2330", "2317")):
        execution = self.control.enqueue_collection(config.config_id, symbols)
        framework = IngestionFramework(self.control, rate_limit_per_second=1000, retry_policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0, max_backoff_seconds=0), sleep=lambda _: asyncio.sleep(0))
        return await framework.collect(execution.execution_id, adapters, as_of=date(2026, 8, 25))

    async def test_market_response_is_cached_as_one_batch(self):
        config = self.config()
        calls = 0

        def fetch(request):
            nonlocal calls
            calls += 1
            return SourceResponse((row("2330"), row("2317")), observed_at=datetime(2026, 8, 25, 6, tzinfo=UTC))

        adapters = {"twse": CallableAdapter("twse", fetch)}
        first = await self.execute(config, adapters)
        second = await self.execute(config, adapters)
        self.assertEqual(calls, 1)
        self.assertEqual(first.status.value, "succeeded")
        self.assertTrue(self.control.list_items(second.execution_id)[0].cache_hit)
        self.assertEqual(len(second.rows), 2)

    async def test_retry_is_bounded_and_persisted(self):
        config = self.config()
        calls = 0

        async def fetch(_request):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise IngestionError(ErrorCode.RATE_LIMITED, "upstream rate limit", True, retry_after_seconds=0)
            return SourceResponse((row(),), observed_at=datetime(2026, 8, 25, 6, tzinfo=UTC))

        result = await self.execute(config, {"twse": CallableAdapter("twse", fetch)}, symbols=("2330",))
        self.assertEqual(calls, 3)
        self.assertEqual(result.status.value, "succeeded")
        self.assertEqual(self.control.source_health("twse", "ohlcv")["success_rate"], 1.0)

    async def test_schema_drift_is_safe_and_persisted(self):
        config = self.config()
        result = await self.execute(config, {"twse": CallableAdapter("twse", lambda _request: SourceResponse((row(),), fields=frozenset({"unexpected"})))}, symbols=("2330",))
        item = self.control.list_items(result.execution_id)[0]
        self.assertEqual(item.state, DataState.SCHEMA_DRIFT)
        self.assertEqual(item.error_code, "schema_drift")
        self.assertEqual(item.safe_message, "source response schema changed")
        self.assertNotIn("traceback", item.safe_message.lower())

    async def test_primary_failure_falls_back_and_empty_is_retained(self):
        config = self.config(sources=("twse", "finmind"))
        adapters = {
            "twse": CallableAdapter("twse", lambda _request: (_ for _ in ()).throw(IngestionError(ErrorCode.UNAVAILABLE, "primary unavailable", False))),
            "finmind": CallableAdapter("finmind", lambda _request: SourceResponse((row(),), is_fallback=True, observed_at=datetime(2026, 8, 25, 6, tzinfo=UTC))),
        }
        result = await self.execute(config, adapters, symbols=("2330",))
        item = self.control.list_items(result.execution_id)[0]
        self.assertEqual(item.state, DataState.FALLBACK)
        self.assertTrue(item.is_fallback)

        empty_config = self.config(sources=("twse",))
        empty = await self.execute(empty_config, {"twse": CallableAdapter("twse", lambda _request: SourceResponse())}, symbols=("2330",))
        self.assertEqual(self.control.list_items(empty.execution_id)[0].state, DataState.EMPTY)

        stale_config = self.config(sources=("twse",))
        stale = await self.execute(stale_config, {"twse": CallableAdapter("twse", lambda _request: SourceResponse((row(),), stale_as_of=datetime(2026, 8, 20, 6, tzinfo=UTC)))}, symbols=("2330",))
        self.assertEqual(self.control.list_items(stale.execution_id)[0].state, DataState.STALE)

    async def test_incremental_cursor_uses_overlap_after_success(self):
        config = self.config()
        first_window = IngestionFramework(self.control, rate_limit_per_second=1000).incremental_window(config, symbol="2330", as_of=date(2026, 8, 25))
        self.assertEqual(first_window.start, date(2026, 7, 26))
        self.control.advance_cursor(first_window.cursor_key, datetime(2026, 8, 24, 6, tzinfo=UTC), successful=True)
        next_window = IngestionFramework(self.control, rate_limit_per_second=1000).incremental_window(config, symbol="2330", as_of=date(2026, 8, 25))
        self.assertEqual(next_window.start, date(2026, 8, 22))

    async def test_timeout_and_partial_states_are_bounded_and_persisted(self):
        config = self.config()
        calls = 0

        class SlowAdapter:
            source_id = "twse"

            async def fetch(self, _request):
                nonlocal calls
                calls += 1
                await asyncio.sleep(0.05)
                return SourceResponse((row(),))

        execution = self.control.enqueue_collection(config.config_id, ("2330",))
        framework = IngestionFramework(self.control, timeout_seconds=0.005, rate_limit_per_second=1000, retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0, max_backoff_seconds=0), sleep=lambda _: asyncio.sleep(0))
        result = await framework.collect(execution.execution_id, {"twse": SlowAdapter()}, as_of=date(2026, 8, 25))
        item = self.control.list_items(result.execution_id)[0]
        self.assertEqual(calls, 2)
        self.assertEqual(item.error_code, "timeout")
        self.assertEqual(item.state, DataState.UNAVAILABLE)

        partial_config = self.config()
        partial = await self.execute(partial_config, {"twse": CallableAdapter("twse", lambda _request: SourceResponse((row(),), is_partial=True))}, symbols=("2330",))
        self.assertEqual(self.control.list_items(partial.execution_id)[0].state, DataState.PARTIAL)
