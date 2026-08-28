import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core import DataState, SQLiteControlPlane


class SourceHealthSummaryTests(unittest.TestCase):
    def test_summary_is_aggregate_only(self):
        control = SQLiteControlPlane()
        now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        control.record_health("twse", "ohlcv", state=DataState.SUCCESS, latency_ms=100, fetched_at=now)
        control.record_health("twse", "ohlcv", state=DataState.FAILED, latency_ms=300, fetched_at=now)
        summary = control.source_health_summary()
        self.assertEqual(summary[0]["success_rate"], 0.5)
        self.assertEqual(summary[0]["average_latency_ms"], 200)
        self.assertNotIn("payload", summary[0])
        control.close()


if __name__ == "__main__":
    unittest.main()
