import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core import CollectionConfig, ExecutionStatus, SQLiteControlPlane, Stock, StockInUseError


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
