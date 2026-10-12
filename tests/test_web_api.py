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
            if "count(COLUMNS(*))" in sql:
                fields = self.rows[0].keys()
                return [{"__row_count": len(self.rows), **{field: sum(row.get(field) is not None for row in self.rows) for field in fields}}]
            return self.rows

        self.service = CoreQueryService(query)

    def test_page_uses_allowlisted_identifier_and_parameter_values(self):
        page = self.service.page("ohlcv", "2330", limit=10)
        self.assertEqual(page.rows[0]["symbol"], "2330")
        self.assertEqual(self.calls[0][0], "core.ohlcv_v1")
        self.assertNotIn("2330", self.calls[0][1])
        self.assertEqual(self.calls[0][2], ("2330", 10, 0))

    def test_page_removes_storage_and_secret_fields_recursively(self):
        self.rows[0].update({
            "gcs_uri": "gs://private/object",
            "raw_payload": {"token": "secret", "safe": "visible"},
            "evidence": [{"object_path": "private/path", "source_id": "twse"}],
        })
        row = self.service.page("ohlcv", "2330").rows[0]
        self.assertNotIn("gcs_uri", row)
        self.assertNotIn("raw_payload", row)
        self.assertEqual(row["evidence"], [{"source_id": "twse"}])

    def test_dataset_specific_filter_and_order_fields_are_allowlisted(self):
        self.service.page("valuation", "2330")
        self.assertIn("WHERE symbol = ? ORDER BY observed_date DESC", self.calls[-1][1])
        self.service.page("benchmark", "TAIEX")
        self.assertIn("WHERE upper(benchmark_id) = ? ORDER BY trade_date DESC", self.calls[-1][1])

    def test_summary_has_bounded_data_quality_metadata(self):
        summary = self.service.summary("2330", datasets=("ohlcv",))
        self.assertEqual(summary["datasets"]["ohlcv"]["row_count"], 2)
        self.assertIn("count(COLUMNS(*))", self.calls[-1][1])

    def test_stock_summary_does_not_treat_symbol_as_benchmark_id(self):
        summary = self.service.summary("2330")
        self.assertNotIn("benchmark", summary["datasets"])
        self.assertEqual(summary["datasets"]["ohlcv"]["latest_date"], "2026-08-27")
        self.assertEqual(summary["datasets"]["ohlcv"]["null_profile"], {"close": 1})

    def test_published_visual_series_preserves_explicit_missing_dates_without_core_scan(self):
        def no_core_query(*_args):
            self.fail("an interactive chart must not scan Core/Iceberg")
        serving = [
            {"observed_date": "2026-10-08", "pe_ratio": "22.5",
             "source_id": "twse", "provenance_id": "a"},
            {"observed_date": "2026-10-07", "pe_ratio": None,
             "source_id": "twse", "provenance_id": "b"},
            {"observed_date": "2026-10-06", "pe_ratio": "20",
             "source_id": "twse", "provenance_id": "c"},
        ]
        service = CoreQueryService(no_core_query, serving_series=lambda *_: serving)
        result = service.visual_series("2330", "pe", limit=10)
        self.assertEqual(result["data_status"], "partial")
        self.assertEqual(result["usable_points"], 2)
        self.assertEqual([p["value"] for p in result["points"]], ["20", None, "22.5"])
        self.assertEqual(result["points"][1]["provenance_id"], "b")
        self.assertEqual(result["data_as_of"], "2026-10-08")
        self.assertEqual(result["source_ids"], ["twse"])

    def test_published_series_invalid_pe_stays_null_but_zero_yield_is_real(self):
        def serving(_dataset, _symbol, _limit):
            return [
                {"observed_date": "2026-10-08", "pe_ratio": "20", "dividend_yield_percent": "0"},
                {"observed_date": "2026-10-07", "pe_ratio": "-3", "dividend_yield_percent": "1.2"},
            ]
        service = CoreQueryService(lambda *_: self.fail("no Core scan"), serving_series=serving)
        pe = service.visual_series("2330", "pe", limit=10)
        self.assertEqual([x["value"] for x in pe["points"]], [None, "20"])
        self.assertEqual(pe["usable_points"], 1)
        yield_series = service.visual_series("2330", "yield", limit=10)
        self.assertEqual([x["value"] for x in yield_series["points"]], ["1.2", "0"])
        self.assertEqual(yield_series["data_status"], "available")

    def test_duplicate_published_day_prefers_real_value_over_null_marker(self):
        def serving(*_):
            return [
                {"observed_date": "2026-10-08", "pe_ratio": None, "source_id": "twse"},
                {"observed_date": "2026-10-08", "pe_ratio": "23", "source_id": "twse"},
                {"observed_date": "2026-10-07", "pe_ratio": "22", "source_id": "twse"},
            ]
        service = CoreQueryService(lambda *_: self.fail("no Core scan"), serving_series=serving)
        result = service.visual_series("2330", "pe", limit=10)
        self.assertEqual([x["value"] for x in result["points"]], ["22", "23"])
        self.assertEqual(result["usable_points"], 2)
        self.assertEqual(result["data_status"], "partial")  # Duplicate/coverage is not full.

    def test_invalid_dataset_and_symbol_are_rejected(self):
        with self.assertRaises(QueryValidationError):
            self.service.page("raw", "2330")
        with self.assertRaises(QueryValidationError):
            self.service.page("ohlcv", "2330; DROP TABLE core")


if __name__ == "__main__":
    unittest.main()
