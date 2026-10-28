import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.web_api import CoreQueryService, QueryValidationError


def _rows(days: int):
    start = date(2024, 1, 1)
    rows = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        price = 100 + offset
        rows.append({"symbol": "2327", "trade_date": day.isoformat(), "open": price, "high": price + 2,
                     "low": price - 1, "close": price + 1, "volume_shares": 1000, "source_id": "twse"})
    return list(reversed(rows))


class PriceSeriesTest(unittest.TestCase):
    def service(self, rows):
        return CoreQueryService(lambda *_: self.fail("no Core scan"), serving_series=lambda *_: rows)

    def test_daily_moving_average_null_until_window(self):
        result = self.service(_rows(60)).price_series("2327", "day", limit=300)
        bars = result["bars"]
        self.assertEqual(result["data_status"], "available")
        self.assertIsNone(bars[3]["ma5"])
        self.assertIsNotNone(bars[4]["ma5"])
        self.assertTrue(all(bar["ma240"] is None for bar in bars))
        self.assertFalse(result["adjusted"])

    def test_week_and_month_aggregate_ohlcv(self):
        rows = _rows(70)
        week = self.service(rows).price_series("2327", "week", limit=300)["bars"]
        first = week[0]
        self.assertEqual(first["period_start"], "2024-01-01")
        self.assertEqual(first["open"], "100")
        self.assertEqual(first["close"], "105")
        self.assertEqual(first["high"], "106")
        self.assertEqual(first["volume_shares"], "5000")
        month = self.service(rows).price_series("2327", "month", limit=300)["bars"]
        self.assertEqual([bar["period_start"] for bar in month], ["2024-01-01", "2024-02-01", "2024-03-01"])

    def test_unavailable_and_invalid(self):
        service = CoreQueryService(lambda *_: [], serving_series=lambda *_: None)
        self.assertEqual(service.price_series("2327")["data_status"], "unavailable")
        with self.assertRaises(QueryValidationError):
            service.price_series("2327", "year")


if __name__ == "__main__":
    unittest.main()
