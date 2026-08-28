import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core import (
    AuthorizationStatus, CollectionConfig, ControlPlaneError, CoverageTier, ExecutionStatus, PostgreSQLControlPlane,
    SQLiteControlPlane, Stock, StockInUseError,
)


class _RecordingCursor:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, sql, parameters=()):
        self.calls.append((sql, parameters))


class _RecordingConnection:
    def __init__(self):
        self.calls = []
        self.commits = 0
        self.closed = False

    def cursor(self):
        return _RecordingCursor(self.calls)

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.control = SQLiteControlPlane()
        self.control.upsert_stock(Stock("2330", "台積電", "TWSE"))
        self.control.upsert_stock(Stock("2317", "鴻海", "TWSE"))
        self.config = CollectionConfig(
            "twse-ohlcv", "ohlcv", ("twse", "finmind"), frozenset({"symbol", "trade_date", "close"}),
            lookback_days=30, overlap_days=2,
        )
        self.control.put_collection_config(self.config, ("2330", "2317"))

    def tearDown(self):
        self.control.close()

    def test_collection_and_analysis_are_separate_queued_commands(self):
        collection = self.control.enqueue_collection("twse-ohlcv", ("2330",), trace_id="trace-collection")
        analysis = self.control.enqueue_analysis("twse-ohlcv", ("2330",), trace_id="trace-analysis")
        self.assertEqual(collection.status, ExecutionStatus.QUEUED)
        self.assertEqual(collection.trigger_type.value, "collection")
        self.assertEqual(analysis.status, ExecutionStatus.QUEUED)
        self.assertNotEqual(collection.execution_id, analysis.execution_id)
        self.assertEqual({item.trace_id for item in self.control.list_executions(limit=2)}, {"trace-collection", "trace-analysis"})

    def test_stock_delete_is_protected_by_collection_reference(self):
        with self.assertRaises(StockInUseError):
            self.control.delete_stock("2330")
        self.control.put_collection_config(self.config, ("2317",))
        self.control.delete_stock("2330")
        self.assertEqual(self.control.search_stocks("2330"), ())

    def test_execution_selection_also_protects_stock_reference(self):
        self.control.put_collection_config(self.config, ())
        self.control.enqueue_collection("twse-ohlcv", ("2330",))
        with self.assertRaises(StockInUseError):
            self.control.delete_stock("2330")

    def test_enabled_filter_and_config_selection(self):
        self.control.set_stock_enabled("2317", False)
        self.assertEqual(tuple(stock.symbol for stock in self.control.search_stocks(enabled=True)), ("2330",))
        self.assertEqual(self.control.config_symbols("twse-ohlcv"), ("2330",))
        self.assertEqual(self.control.config_symbols("twse-ohlcv", only_enabled=False), ("2317", "2330"))

    def test_execution_transition_is_persisted_and_invalid_transition_rejected(self):
        execution = self.control.enqueue_collection("twse-ohlcv", ("2330",))
        self.control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)
        self.control.transition_execution(execution.execution_id, ExecutionStatus.RETRYING, retry_count=1, error_code="timeout")
        self.control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING, retry_count=1)
        completed = self.control.transition_execution(execution.execution_id, ExecutionStatus.SUCCEEDED)
        self.assertEqual(completed.status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(completed.retry_count, 1)
        with self.assertRaises(Exception):
            self.control.transition_execution(execution.execution_id, ExecutionStatus.RUNNING)

    def test_core_focus_membership_is_capped_and_keeps_history(self):
        first = datetime(2026, 8, 1, tzinfo=timezone.utc)
        second = first + timedelta(days=1)
        self.control.set_coverage_membership("core_focus", ("2330", "2317"), effective_from=first, reason="initial research set", owner="research")
        self.control.set_coverage_membership("core_focus", ("2330",), effective_from=second, reason="narrowed research set", owner="research")
        self.assertEqual(tuple(item.symbol for item in self.control.coverage_membership("core_focus", as_of=first)), ("2317", "2330"))
        self.assertEqual(tuple(item.symbol for item in self.control.coverage_membership("core_focus", as_of=second)), ("2330",))

    def test_core_focus_rejects_more_than_fifty_symbols(self):
        for index in range(51):
            self.control.upsert_stock(Stock(str(6000 + index), f"stock-{index}", "TWSE"))
        with self.assertRaises(ControlPlaneError):
            self.control.set_coverage_membership("core_focus", tuple(str(6000 + index) for index in range(51)), effective_from=datetime(2026, 8, 1, tzinfo=timezone.utc), reason="too many", owner="test")

    def test_candidate_source_cannot_be_enqueued(self):
        config = CollectionConfig("candidate-feed", "ohlcv", ("fugle",), frozenset({"symbol"}), authorization_status=AuthorizationStatus.APPROVED_FALLBACK.value)
        self.control.put_collection_config(config, ("2330",))
        with self.assertRaises(ControlPlaneError):
            self.control.enqueue_collection("candidate-feed", ("2330",))

    def test_config_persists_coverage_metadata(self):
        config = CollectionConfig("core-feed", "events", ("mops",), frozenset({"symbol"}), coverage_tier=CoverageTier.CORE_FOCUS.value, cadence="公告頻率", scope="core_focus", retention_class="deep_research", republish_allowed=True)
        self.control.put_collection_config(config, ("2330",))
        loaded = self.control.get_collection_config("core-feed")
        self.assertEqual(loaded.coverage_tier, "core_focus")
        self.assertEqual(loaded.cadence, "公告頻率")
        self.assertTrue(loaded.republish_allowed)

    def test_stock_master_persists_listing_status_and_market_wide_defaults_to_enabled_master(self):
        effective = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.control.upsert_stock(Stock("2317", "鴻海", "TWSE", listing_status="listed", effective_from=effective))
        config = CollectionConfig("market-feed", "ohlcv", ("twse",), frozenset({"symbol"}), coverage_tier=CoverageTier.MARKET_WIDE.value)
        self.control.put_collection_config(config)
        self.assertEqual(self.control.config_symbols("market-feed"), ("2317", "2330"))
        self.assertEqual(self.control.search_stocks("2317")[0].listing_status, "listed")


class PostgreSQLControlPlaneTests(unittest.TestCase):
    def test_session_timeouts_use_parameterizable_set_config(self):
        connection = _RecordingConnection()

        control = PostgreSQLControlPlane(
            lambda: connection,
            statement_timeout_ms=5000,
            idle_in_transaction_timeout_ms=10000,
        )

        self.assertEqual(connection.calls, [
            ("SELECT set_config('statement_timeout', %s, false)", ("5000ms",)),
            ("SELECT set_config('idle_in_transaction_session_timeout', %s, false)", ("10000ms",)),
        ])
        self.assertEqual(connection.commits, 1)
        control.close()
        self.assertTrue(connection.closed)
