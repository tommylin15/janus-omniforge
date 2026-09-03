import sys
import unittest
from datetime import timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core import CollectionConfig, SQLiteControlPlane, Stock
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

    def test_collection_config_edit_preserves_symbols_and_writes_audit(self):
        payload = {**self.admin.collection_configs()[0], "source_ids": ["twse"], "cadence": "weekly"}
        saved = self.admin.save_collection_config(payload, actor="operator@example.com")

        self.assertEqual(saved["cadence"], "weekly")
        self.assertEqual(self.control.config_symbols("ohlcv", only_enabled=False), ("2330",))
        self.assertEqual(self.admin.audit()[0]["resource"], "collection_config")

    def test_analysis_is_rejected_without_creating_an_execution(self):
        before = self.admin.executions()
        with self.assertRaisesRegex(AdminValidationError, "persisted consumer"):
            self.admin.enqueue_analysis("ohlcv", ("2330",))
        self.assertEqual(self.admin.executions(), before)

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
