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

    def test_market_home_uses_one_bounded_official_benchmark_history_query(self):
        captured = []
        def query(identifier, sql, parameters):
            captured.append((identifier, sql, parameters))
            if identifier == "core.benchmark_v1":
                return [
                    {"benchmark_id": "TAIEX", "trade_date": "2026-10-08",
                     "close": "49313.44", "source_id": "taiex", "provenance_id": "p3"},
                    {"benchmark_id": "TAIEX", "trade_date": "2026-10-07",
                     "close": "49806.37", "source_id": "taiex", "provenance_id": "p2"},
                    {"benchmark_id": "TAIEX", "trade_date": "2026-10-06",
                     "close": None, "source_id": "taiex", "provenance_id": "p1"},
                    {"benchmark_id": "TAIEX", "trade_date": "2026-10-05",
                     "close": "49712.04", "source_id": "taiex", "provenance_id": "p0"},
                ]
            raise RuntimeError("optional market section unavailable")
        result = CoreQueryService(query).market_home()
        taiex = result["sections"]["taiex"]
        self.assertEqual(taiex["data"]["history_status"], "available")
        self.assertEqual([x["date"] for x in taiex["data"]["history_points"]],
                         ["2026-10-05", "2026-10-07", "2026-10-08"])
        self.assertEqual([x["value"] for x in taiex["data"]["history_points"]],
                         ["49712.04", "49806.37", "49313.44"])
        self.assertEqual(taiex["data"]["history_source_ids"], ["taiex"])
        self.assertEqual(taiex["data"]["history_as_of"], "2026-10-08")
        self.assertEqual(taiex["data"]["close"], "49313.44")
        benchmark_queries = [x for x in captured if x[0] == "core.benchmark_v1"]
        self.assertEqual(len(benchmark_queries), 1)
        self.assertEqual(benchmark_queries[0][2], ("TAIEX", 40))
        self.assertIn("LIMIT ?", benchmark_queries[0][1])

    def test_market_trend_refuses_unsigned_invalid_or_future_points(self):
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=1)).isoformat()
        def query(identifier, sql, params):
            if identifier != "core.benchmark_v1":
                raise RuntimeError("unavailable")
            return [
                {"benchmark_id": "TAIEX", "trade_date": future,
                 "close": "40000", "source_id": "taiex", "provenance_id": "pf"},
                {"benchmark_id": "TAIEX", "trade_date": "2026-10-08",
                 "close": "-1", "source_id": "taiex", "provenance_id": "p0"},
                {"benchmark_id": "TAIEX", "trade_date": "2026-10-07",
                 "close": "49000", "source_id": "taiex"},
                {"benchmark_id": "TAIEX", "trade_date": "2026-10-06",
                 "close": "48000", "source_id": "taiex", "provenance_id": "p1"},
            ]
        result = CoreQueryService(query).market_home()
        data = result["sections"]["taiex"]["data"]
        self.assertEqual(data["history_status"], "missing")
        self.assertEqual(data["history_points"],
                         [{"date": "2026-10-06", "value": "48000",
                           "source_id": "taiex", "provenance_id": "p1"}])
        self.assertEqual(result["sections"]["taiex"]["status"], "stale" if
                         (date.today() - date(2026, 10, 6)).days > 7 else "available")

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
