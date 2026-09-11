import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core import (
    AuthorizationStatus, CollectionConfig, ControlPlaneError, CoverageTier, ExecutionStatus, PostgreSQLControlPlane,
    SQLiteControlPlane, Stock, StockInUseError, TriggerType,
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


class _RecordingTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.transactions += 1

    def __exit__(self, *_):
        return None


class _AutocommitRecordingConnection(_RecordingConnection):
    def __init__(self):
        super().__init__()
        self.autocommit = False
        self.transactions = 0

    def transaction(self):
        return _RecordingTransaction(self)


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

    def test_queue_claim_filters_worker_type_and_releases_lease_on_completion(self):
        collection = self.control.enqueue_collection("twse-ohlcv", ("2330",))
        analysis = self.control.enqueue_analysis("twse-ohlcv", ("2330",))
        claimed = self.control.claim_execution("ingestion-1", trigger_type=TriggerType.COLLECTION)
        self.assertEqual(claimed.execution_id, collection.execution_id)
        self.assertEqual(claimed.status, ExecutionStatus.RUNNING)
        self.assertIsNone(self.control.claim_execution("ingestion-2", trigger_type=TriggerType.COLLECTION))
        self.control.transition_execution(claimed.execution_id, ExecutionStatus.SUCCEEDED)
        claimed_analysis = self.control.claim_execution("mart-1", trigger_type=TriggerType.ANALYSIS)
        self.assertEqual(claimed_analysis.execution_id, analysis.execution_id)

    def test_expired_queue_lease_can_be_reclaimed(self):
        execution = self.control.enqueue_collection("twse-ohlcv", ("2330",))
        first = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.control.claim_execution("worker-1", trigger_type=TriggerType.COLLECTION, lease=timedelta(seconds=1), now=first)
        reclaimed = self.control.claim_execution("worker-2", trigger_type=TriggerType.COLLECTION, now=first + timedelta(seconds=2))
        self.assertEqual(reclaimed.execution_id, execution.execution_id)

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

    def test_market_membership_and_external_domains_protect_stock_reference(self):
        self.control.put_collection_config(self.config, ())
        self.control.set_coverage_membership("core_focus", ("2330",), effective_from=datetime(2026, 8, 1, tzinfo=timezone.utc), reason="tracked", owner="test")
        with self.assertRaises(StockInUseError) as blocked:
            self.control.delete_stock("2330", external_references={"market": 2, "report": 3, "fundamental": 4})
        self.assertEqual(blocked.exception.references, {
            "collection_config": 0, "execution": 0, "market": 3, "report": 3, "fundamental": 4,
        })

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
        self.assertEqual(self.control.coverage_membership_revision("core_focus"), (2, second))
        audit = self.control.admin_audit()[0]
        self.assertEqual((audit["resource"], audit["actor"], audit["detail"]["version"]), ("coverage_membership", "research", 2))
        self.assertEqual(audit["detail"]["removed"], ["2317"])
        with self.assertRaisesRegex(ControlPlaneError, "version conflict"):
            self.control.set_coverage_membership("core_focus", ("2330",), effective_from=second + timedelta(days=1), reason="stale edit", owner="research", expected_version=1)

    def test_core_worker_uses_only_latest_effective_membership(self):
        now = datetime.now(timezone.utc)
        config = CollectionConfig("core-deep", "financials", ("mops",), frozenset({"symbol"}), coverage_tier="core_focus")
        self.control.put_collection_config(config, ())
        self.control.set_coverage_membership("core_focus", ("2317", "2330"), effective_from=now - timedelta(hours=2), reason="initial", owner="operator", expected_version=0)
        self.control.set_coverage_membership("core_focus", ("2330",), effective_from=now - timedelta(hours=1), reason="remove 2317", owner="operator", expected_version=1)
        self.control.set_coverage_membership("core_focus", ("2317",), effective_from=now + timedelta(hours=1), reason="future rotation", owner="operator", expected_version=2)
        self.assertEqual(self.control.config_symbols("core-deep"), ("2330",))
        self.assertEqual(self.control.enqueue_collection("core-deep").requested_symbols, ("2330",))

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

    def test_audited_source_review_can_approve_a_candidate_adapter(self):
        config = CollectionConfig("candidate-feed", "ohlcv", ("fugle",), frozenset({"symbol"}), authorization_status=AuthorizationStatus.APPROVED_FALLBACK.value)
        self.control.put_collection_config(config, ("2330",))
        checks = {key: True for key in ("license", "terms", "robots", "rate_limit", "stability", "duplication", "retention", "deletion", "republishing", "cost", "security")}
        self.control.put_admin_setting("source_review:fugle", {"status": "approved_fallback", "checks": checks, "evidence_url": "https://example.com/review", "reviewer": "reviewer", "reason": "reviewed", "decided_at": "2026-08-31T00:00:00+00:00"}, actor="reviewer")
        self.assertEqual(self.control.enqueue_collection("candidate-feed", ("2330",)).status, ExecutionStatus.QUEUED)

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
    def test_autocommit_reads_keep_explicit_write_transactions(self):
        connection = _AutocommitRecordingConnection()
        control = PostgreSQLControlPlane(lambda: connection)

        with control._tx() as cursor:
            cursor.execute("UPDATE control.test SET value=1")

        self.assertTrue(connection.autocommit)
        self.assertEqual(connection.transactions, 1)
        control.close()

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
