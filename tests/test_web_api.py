import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from packages.web_api import CoreQueryService, QueryValidationError


class CoreQueryServiceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.rows = [{"symbol": "2330", "trade_date": "2026-08-27", "close": 100, "quality_flag": "ok"},
                     {"symbol": "2330", "trade_date": "2026-08-26", "close": None, "quality_flag": "partial"}]

        def query(identifier, sql, parameters):
            self.calls.append((identifier, sql, parameters))
            return self.rows

        self.service = CoreQueryService(query)

    def test_page_uses_allowlisted_identifier_and_parameter_values(self):
        page = self.service.page("ohlcv", "2330", limit=10)
        self.assertEqual(page.rows[0]["symbol"], "2330")
        self.assertEqual(self.calls[0][0], "core.ohlcv_v1")
        self.assertNotIn("2330", self.calls[0][1])
        self.assertEqual(self.calls[0][2], ("2330", 10, 0))

    def test_dataset_specific_filter_and_order_fields_are_allowlisted(self):
        self.service.page("valuation", "2330")
        self.assertIn("WHERE symbol = ? ORDER BY observed_date DESC", self.calls[-1][1])
        self.service.page("benchmark", "TAIEX")
        self.assertIn("WHERE benchmark_id = ? ORDER BY trade_date DESC", self.calls[-1][1])

    def test_summary_has_bounded_data_quality_metadata(self):
        summary = self.service.summary("2330", datasets=("ohlcv",))
        self.assertEqual(summary["datasets"]["ohlcv"]["row_count"], 2)

    def test_stock_summary_does_not_treat_symbol_as_benchmark_id(self):
        summary = self.service.summary("2330")
        self.assertNotIn("benchmark", summary["datasets"])
        self.assertEqual(summary["datasets"]["ohlcv"]["latest_date"], "2026-08-27")
        self.assertEqual(summary["datasets"]["ohlcv"]["null_profile"], {"close": 1})

    def test_invalid_dataset_and_symbol_are_rejected(self):
        with self.assertRaises(QueryValidationError):
            self.service.page("raw", "2330")
        with self.assertRaises(QueryValidationError):
            self.service.page("ohlcv", "2330; DROP TABLE core")


if __name__ == "__main__":
    unittest.main()
