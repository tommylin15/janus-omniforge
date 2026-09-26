import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core import first_batch


class PilotTradingCalendarTests(unittest.TestCase):
    def test_official_twse_holidays_drive_previous_trading_day(self):
        self.assertTrue(
            hasattr(first_batch, "twse_market_holidays"),
            "ingestion must load the official TWSE trading calendar",
        )
        payload = json.dumps([
            {"Name": "市場無交易，僅辦理結算交割作業", "Date": "1150212", "Weekday": "四", "Description": ""},
            {"Name": "農曆春節後開始交易日", "Date": "1150223", "Weekday": "一", "Description": "農曆春節後開始交易。"},
            {"Name": "中秋節", "Date": "1150925", "Weekday": "五", "Description": "依規定放假1日。"},
            {"Name": "孔子誕辰紀念日/ 教師節", "Date": "1150928", "Weekday": "一", "Description": "依規定放假1日。"},
        ], ensure_ascii=False).encode()

        holidays = first_batch.twse_market_holidays(transport=lambda _: payload)

        self.assertIn(date(2026, 2, 12), holidays)
        self.assertIn(date(2026, 9, 25), holidays)
        self.assertIn(date(2026, 9, 28), holidays)
        self.assertNotIn(date(2026, 2, 23), holidays)
        self.assertEqual(
            first_batch.effective_trading_day(date(2026, 9, 28), holidays=holidays),
            date(2026, 9, 24),
        )


if __name__ == "__main__":
    unittest.main()
