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
        self.admin = AdminService(self.control)

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
            self.admin.stocks(limit=501)

    def test_source_health_is_persisted_and_datetime_is_normalized(self):
        self.assertEqual(self.admin.source_health(), ())
        parsed = self.admin.parse_datetime("2026-08-28T10:30:00")
        self.assertEqual(parsed.tzinfo, timezone.utc)
        with self.assertRaises(AdminValidationError):
            self.admin.parse_datetime("not-a-date")

    def test_settings_are_validated_versioned_and_audited(self):
        saved = self.admin.save_setting("schedule", {"time": "08:00", "enabled": True}, actor="operator")
        self.assertEqual(saved["version"], 1)
        self.assertEqual(self.admin.setting("schedule")["value"]["time"], "08:00")
        with self.assertRaises(Exception):
            self.admin.save_setting("schedule", {"time": "09:00", "enabled": True}, actor="operator", expected_version=0)
        self.assertEqual(self.admin.audit()[0]["resource_key"], "schedule")

    def test_retention_bounds(self):
        with self.assertRaises(AdminValidationError):
            self.admin.save_setting("retention", {"days": 0, "cleanup_enabled": True}, actor="operator")


if __name__ == "__main__":
    unittest.main()
