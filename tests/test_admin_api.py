import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core import CollectionConfig, DataState, SQLiteControlPlane, Stock
from packages.admin_api import AdminService, AdminValidationError


class AdminServiceTests(unittest.TestCase):
    def setUp(self):
        self.control = SQLiteControlPlane()
        self.control.upsert_stock(Stock("2330", "台積電", "TWSE"))
        self.control.put_collection_config(CollectionConfig("ohlcv", "ohlcv", ("twse",), frozenset({"symbol"})), ("2330",))
        self.scheduler_values = []
        self.admin = AdminService(self.control, schedule_sync=self.scheduler_values.append)

    def tearDown(self):
        self.control.close()

    def test_stock_and_execution_responses_are_safe_and_bounded(self):
        self.assertEqual(self.admin.stocks()[0]["symbol"], "2330")
        execution = self.admin.enqueue_collection("ohlcv", ("2330",), trace_id="trace-1")
        self.assertEqual(execution["status"], "queued")
        details = self.admin.execution_details(execution["execution_id"])
        self.assertEqual(details["trace_id"], "trace-1")
        self.assertEqual(details["lineage"]["executions"][0]["execution_id"], execution["execution_id"])
        self.assertNotIn("payload", details)

    def test_invalid_page_is_rejected(self):
        with self.assertRaises(AdminValidationError):
            self.admin.stocks(limit=102)
        with self.assertRaises(AdminValidationError):
            self.admin.stocks(cursor="invalid cursor")

    def test_stock_cursor_uses_unique_symbol_key(self):
        self.control.upsert_stock(Stock("2454", "聯發科", "TWSE"))
        first = self.admin.stocks(limit=1)
        second = self.admin.stocks(limit=1, cursor=first[-1]["symbol"])
        self.assertEqual(first[0]["symbol"], "2330")
        self.assertEqual(second[0]["symbol"], "2454")

    def test_execution_cursor_has_stable_id_tiebreaker(self):
        first = self.admin.enqueue_collection("ohlcv", ("2330",))
        second = self.admin.enqueue_collection("ohlcv", ("2330",))
        page = self.admin.executions(limit=1)
        cursor = f'{page[0]["requested_at"]},{page[0]["execution_id"]}'
        following = self.admin.executions(limit=1, cursor=cursor)
        self.assertEqual({page[0]["execution_id"], following[0]["execution_id"]}, {first["execution_id"], second["execution_id"]})
        with self.assertRaises(AdminValidationError):
            self.admin.executions(cursor="bad")

    def test_source_health_is_persisted_and_datetime_is_normalized(self):
        self.assertEqual(self.admin.source_health(), ())
        parsed = self.admin.parse_datetime("2026-08-28T10:30:00")
        self.assertEqual(parsed.tzinfo, timezone.utc)
        with self.assertRaises(AdminValidationError):
            self.admin.parse_datetime("not-a-date")

    def test_source_health_and_configs_use_repository_cursors(self):
        now = datetime(2026, 9, 10, tzinfo=timezone.utc)
        self.control.record_health("twse", "ohlcv", state=DataState.SUCCESS, latency_ms=1, fetched_at=now)
        self.control.record_health("tpex", "ohlcv", state=DataState.SUCCESS, latency_ms=1, fetched_at=now)
        first = self.admin.source_health(limit=1)
        cursor = f'{first[0]["source_id"]},{first[0]["dataset_id"]}'
        self.assertNotEqual(first, self.admin.source_health(limit=1, cursor=cursor))
        self.control.put_collection_config(CollectionConfig("valuation", "valuation", ("twse",), frozenset({"symbol"})))
        first_config = self.admin.collection_configs(limit=1)
        self.assertNotEqual(first_config, self.admin.collection_configs(limit=1, cursor=first_config[0]["config_id"]))
        with self.assertRaises(AdminValidationError):
            self.admin.source_health(cursor="bad")

    def test_settings_are_validated_versioned_and_audited(self):
        saved = self.admin.save_setting("schedule", {"time": "08:00", "enabled": True, "holiday_overrides": ["2026-09-28"]}, actor="operator")
        self.assertEqual(saved["version"], 1)
        self.assertEqual(self.scheduler_values[0]["time"], "08:00")
        self.assertEqual(self.admin.setting("schedule")["value"]["time"], "08:00")
        with self.assertRaises(Exception):
            self.admin.save_setting("schedule", {"time": "09:00", "enabled": True}, actor="operator", expected_version=0)
        self.assertEqual(self.admin.audit()[0]["resource_key"], "schedule")

    def test_collection_backfill_options_are_validated_and_persisted(self):
        execution = self.admin.enqueue_collection("ohlcv", ("2330",), request_options={"start_date": "2026-08-24", "end_date": "2026-08-28", "source_ids": ["twse"]})
        self.assertEqual(execution["request_options"]["start_date"], "2026-08-24")
        with self.assertRaises(AdminValidationError):
            self.admin.enqueue_collection("ohlcv", ("2330",), request_options={"start_date": "2026-08-24"})

    def test_membership_snapshot_is_versioned_and_audited(self):
        saved = self.admin.set_membership("core_focus", ("2330",), effective_from=self.admin.parse_datetime("2026-09-03T00:00:00Z"), reason="initial", owner="operator@example.com", expected_version=0)
        self.assertEqual((saved["version"], saved["items"][0]["symbol"]), (1, "2330"))
        self.assertEqual(saved["effective_from"], "2026-09-03T00:00:00+00:00")
        self.assertEqual(self.admin.audit()[0]["resource"], "coverage_membership")

    def test_collection_config_edit_preserves_symbols_and_writes_audit(self):
        payload = {**self.admin.collection_configs()[0], "source_ids": ["twse"], "cadence": "weekly"}
        saved = self.admin.save_collection_config(payload, actor="operator@example.com")

        self.assertEqual(saved["cadence"], "weekly")
        self.assertEqual(self.control.config_symbols("ohlcv", only_enabled=False), ("2330",))
        self.assertEqual(self.admin.audit()[0]["resource"], "collection_config")

    def test_analysis_uses_latest_successful_core_snapshot(self):
        collection = self.control.enqueue_collection("ohlcv", ("2330",))
        from ingestion_core import ExecutionStatus
        self.control.transition_execution(collection.execution_id, ExecutionStatus.RUNNING)
        _, automatic = self.control.complete_collection(collection.execution_id, {
            "eventType":"core.dataset.ready.v1","executionId":collection.execution_id,"configId":"ohlcv",
            "datasetId":"core","schemaVersion":"1.0.0","rowCount":1,"analysisAsOf":"2026-09-12",
            "coreSnapshotId":"snapshot-1","coreSnapshotUri":"gs://core/snapshot.json",
            "coreSnapshotHash":"sha256:" + "1" * 64,
        })
        analysis = self.admin.enqueue_analysis("ohlcv", ("2330",))
        self.assertEqual((analysis["status"], analysis["request_options"]["core_snapshot_id"]), ("queued", "snapshot-1"))
        self.assertEqual(analysis["request_options"]["scopes"], [{"type":"symbol","id":"2330","symbols":["2330"]}])
        lineage = self.admin.execution_details(collection.execution_id)["lineage"]["executions"]
        self.assertEqual({item["execution_id"] for item in lineage}, {collection.execution_id, automatic.execution_id})

    def test_mart_reports_filter_metadata_and_build_immutable_navigation(self):
        values = ("11111111-1111-1111-1111-111111111111","2026-09-12","symbol","2330","core-1",
                  "gs://mart/warehouse/metadata.json","sha256:"+"1"*64,"sha256:"+"2"*64,
                  "mart.mart_scoped_analysis_v1",42,"1","1","deterministic-v1","gov-1","v1","sha256:"+"3"*64,
                  .8,.7,"good","complete","publishable","2026-09-12T00:00:00+00:00","2026-09-12T00:01:00+00:00")
        self.control.connection.execute("INSERT INTO mart_report_index VALUES(" + ",".join("?" for _ in values) + ")", values)
        report = self.admin.mart_reports(scope_type="symbol", scope_id="2330", role="quant")[0]
        self.assertEqual((report["selected_role"], report["iceberg_snapshot_id"]), ("quant", 42))
        self.assertTrue(report["artifact_console_url"].startswith("https://console.cloud.google.com/storage/browser/_details/mart/"))

    def test_mart_publication_review_mutates_status_and_audits_reason(self):
        values = ("11111111-1111-1111-1111-111111111111", "2026-09-12", "symbol", "2330", "core-1",
                  "gs://mart/report.json", "sha256:" + "1" * 64, "sha256:" + "2" * 64,
                  "mart.mart_scoped_analysis_v1", 42, "1", "1", "deterministic-v1", "gov-1", "v1",
                  "sha256:" + "3" * 64, .8, .7, "good", "complete", "publishable",
                  "2026-09-12T00:00:00+00:00", "2026-09-12T00:01:00+00:00")
        self.control.connection.execute(
            "INSERT INTO mart_report_index VALUES(" + ",".join("?" for _ in values) + ")", values,
        )
        blocked = self.admin.review_mart_report(values[0], values[2], values[3], "block", "policy hold", "reviewer")
        self.assertEqual(blocked["publication_status"], "blocked")
        self.assertEqual(self.control.list_mart_reports(filters={"publication_status": "blocked"})[0]["publication_status"], "blocked")
        unblocked = self.admin.review_mart_report(values[0], values[2], values[3], "unblock", "evidence cleared", "reviewer")
        self.assertEqual(unblocked["publication_status"], "publishable")
        self.assertEqual(self.admin.audit(limit=2)[0]["detail"]["reason"], "evidence cleared")

    def test_retention_bounds(self):
        with self.assertRaises(AdminValidationError):
            self.admin.save_setting("retention", {"days": 0, "cleanup_enabled": True}, actor="operator")
        with self.assertRaises(AdminValidationError):
            self.admin.save_setting("source_review:anue", {"status": "approved_fallback"}, actor="operator")

    def test_stock_status_is_flattened_for_table_rendering(self):
        class Core:
            @staticmethod
            def summary(symbol):
                return {"symbol": symbol, "datasets": {"ohlcv": {"row_count": 2, "latest_date": "2026-08-28", "coverage": {"received_symbols": 1, "requested_symbols": 1}, "null_profile": {"close": 1}, "quality_flags": ["warning"], "warning_count": 2, "quarantined_count": 1, "associations": {"source_id": ["twse"], "execution_id": ["exec-1"], "provenance_id": ["prov-1"], "snapshot_id": ["snap-1"]}}}}

        status = AdminService(self.control, core=Core()).stock_status("2330")
        self.assertEqual(status["items"][0]["dataset_id"], "ohlcv")
        self.assertEqual(status["items"][0]["null_count"], 1)
        self.assertEqual(status["items"][0]["null_profile"], ({"field": "close", "count": 1, "ratio": 0.5},))
        self.assertEqual(status["items"][0]["coverage_ratio"], 1.0)
        self.assertEqual(status["items"][0]["dq_warning_count"], 2)
        self.assertEqual(status["items"][0]["quarantine_count"], 1)
        self.assertEqual(status["items"][0]["execution_ids"], ("exec-1",))
        self.assertEqual(status["items"][0]["provenance_ids"], ("prov-1",))
        self.assertNotIn("summary", status)

    def test_stock_delete_guard_combines_control_market_report_and_fundamental_references(self):
        class Core:
            @staticmethod
            def summary(symbol):
                return {"symbol": symbol, "datasets": {
                    "ohlcv": {"row_count": 2}, "financials": {"row_count": 3}, "mart-report": {"row_count": 4},
                }}

        admin = AdminService(self.control, core=Core())
        summary = admin.stock_references("2330")
        self.assertEqual(summary["references"], {
            "collection_config": 1, "execution": 0, "market": 2, "report": 4, "fundamental": 3,
        })
        self.assertFalse(summary["can_delete"])
        with self.assertRaisesRegex(Exception, "stock cannot be deleted"):
            admin.delete_stock("2330")
        self.assertEqual(self.control.search_stocks("2330")[0].symbol, "2330")

    def test_source_review_requires_all_checks_before_approval(self):
        checks = {key: True for key in ("license", "terms", "robots", "rate_limit", "stability", "duplication", "retention", "deletion", "republishing", "cost", "security")}
        with self.assertRaises(AdminValidationError):
            self.admin.save_source_review("anue", {"status": "approved_fallback", "checks": {**checks, "license": False}, "evidence_url": "https://example.com/review", "reason": "review"}, actor="reviewer", expected_version=0)
        saved = self.admin.save_source_review("anue", {"status": "approved_fallback", "checks": checks, "evidence_url": "https://example.com/review", "reason": "reviewed"}, actor="reviewer", expected_version=0)
        self.assertEqual(saved["value"]["status"], "approved_fallback")
        self.assertEqual(saved["value"]["reviewer"], "reviewer")
        self.assertEqual(self.admin.source_review("anue")["version"], 1)
        with self.assertRaises(AdminValidationError):
            self.admin.save_source_review("anue", {"status": "blocked", "checks": checks, "evidence_url": "", "reason": "blocked"}, actor="reviewer")


if __name__ == "__main__":
    unittest.main()
