import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))
sys.path.insert(0, str(ROOT))

from ingestion_core.adapters import CollectionRequest
from ingestion_core.first_batch import (
    JsonDatasetAdapter,
    dataset_adapters,
    normalise_benchmark,
    normalise_financials,
    normalise_institutional,
)


class DataCleaningRegressionTests(unittest.TestCase):
    def test_dealer_uses_total_buy_sell_and_official_total_net(self):
        rows = normalise_institutional([
            {
                "證券代號": "2330",
                "Date": "20260917",
                "自營商買賣超股數": "509,161",
                "自營商買進股數(自行買賣)": "459,100",
                "自營商賣出股數(自行買賣)": "102,200",
                "自營商買賣超股數(自行買賣)": "356,900",
                "自營商買進股數(避險)": "303,061",
                "自營商賣出股數(避險)": "150,800",
                "自營商買賣超股數(避險)": "152,261",
                "外陸資買進股數(不含外資自營商)": "1",
                "外陸資賣出股數(不含外資自營商)": "1",
                "外陸資買賣超股數(不含外資自營商)": "0",
                "投信買進股數": "1",
                "投信賣出股數": "1",
                "投信買賣超股數": "0",
            }
        ])
        dealer = next(row for row in rows if row["investor_type"] == "dealer")
        self.assertEqual(dealer["buy_shares"], "762161")
        self.assertEqual(dealer["sell_shares"], "253000")
        self.assertEqual(dealer["net_shares"], "509161")
        self.assertEqual(int(dealer["buy_shares"]) - int(dealer["sell_shares"]), int(dealer["net_shares"]))

    def test_mops_eps_is_twd_per_share_not_thousands(self):
        row = normalise_financials([
            {
                "出表日期": "1150925",
                "年度": "115",
                "季別": "2",
                "公司代號": "1102",
                "公司名稱": "亞泥",
                "基本每股盈餘（元）": "2.13",
            }
        ])[0]
        self.assertEqual(row["metric"], "基本每股盈餘（元）")
        self.assertEqual(row["value"], "2.13")
        self.assertEqual(row["unit"], "TWD_per_share")
        self.assertEqual(row["currency"], "TWD")
        self.assertEqual(row["source_report_date"], "2026-09-25")

    def test_finmind_date_is_fiscal_period_end_not_publication_time_contract(self):
        row = normalise_financials([
            {"date": "2026-06-30", "stock_id": "2330", "type": "EPS", "value": 22.08}
        ])[0]
        self.assertEqual(row["fiscal_period_end"], "2026-06-30")
        self.assertEqual((row["fiscal_year"], row["fiscal_quarter"]), (2026, 2))

    def test_explicit_financial_unit_is_preserved(self):
        row = normalise_financials([
            {
                "symbol": "2330",
                "year": 2026,
                "quarter": 2,
                "statement": "income",
                "published": "2026-08-13T00:00:00Z",
                "name": "gross_margin",
                "amount": "58.6",
                "unit": "percent",
                "currency": "TWD",
            }
        ])[0]
        self.assertEqual(row["unit"], "percent")

    def test_snapshot_source_uses_fetch_time_as_explicit_availability(self):
        fetched = datetime(2026, 9, 25, 2, 30, tzinfo=timezone.utc)
        raw = json.dumps([{
            "出表日期": "1150925", "年度": "115", "季別": "2",
            "公司代號": "2330", "營業收入": "100",
        }], ensure_ascii=False).encode()
        adapter = JsonDatasetAdapter(
            "mops", "financials", "https://example.test/current", normalise_financials,
            lambda _: raw, observation_mode="fetch_time", max_replay_age_days=7,
            availability_field="availability_at", publication_time_authoritative=False,
            clock=lambda: fetched,
        )
        request = CollectionRequest(
            "e1", "t1", "mops", "financials", "TWSE", ("2330",),
            date(2025, 8, 21), date(2026, 9, 24), 5,
        )
        response = adapter.fetch(request)
        self.assertEqual(response.observed_at, fetched)
        self.assertEqual(response.rows[0]["observed_at"], "2026-09-25T02:30:00Z")
        self.assertEqual(response.rows[0]["availability_at"], "2026-09-25T02:30:00Z")
        self.assertIs(response.rows[0]["publication_time_authoritative"], False)
        self.assertEqual(response.rows[0]["source_report_date"], "2026-09-25")

    def test_snapshot_source_rejects_deep_historical_replay_before_transport(self):
        fetched = datetime(2026, 9, 25, 2, 30, tzinfo=timezone.utc)
        calls = []
        adapter = JsonDatasetAdapter(
            "mops", "financials", "https://example.test/current", normalise_financials,
            lambda url: calls.append(url) or b"[]", observation_mode="fetch_time",
            max_replay_age_days=7, clock=lambda: fetched,
        )
        request = CollectionRequest(
            "e1", "t1", "mops", "financials", "TWSE", ("2330",),
            date(2024, 1, 1), date(2026, 8, 31), 5,
        )
        with self.assertRaisesRegex(ValueError, "historical replay"):
            adapter.fetch(request)
        self.assertEqual(calls, [])

    def test_historical_list_source_filters_rows_after_requested_as_of(self):
        fetched = datetime(2026, 9, 25, 2, 30, tzinfo=timezone.utc)
        raw = json.dumps([
            {"Date": "20260923", "Close": "48000"},
            {"Date": "20260925", "Close": "49000"},
        ]).encode()
        adapter = JsonDatasetAdapter(
            "tpex-benchmark", "benchmark", "https://example.test/history",
            lambda rows: normalise_benchmark(rows, "TPEx"), lambda _: raw,
            row_date_field="trade_date", clock=lambda: fetched,
        )
        request = CollectionRequest(
            "e1", "t1", "tpex-benchmark", "benchmark", "TPEX", (),
            date(2026, 9, 24), date(2026, 9, 24), 5,
        )
        response = adapter.fetch(request)
        self.assertEqual([row["trade_date"] for row in response.rows], ["2026-09-23"])
        self.assertEqual(response.observed_at, datetime(2026, 9, 24, tzinfo=timezone.utc))

    def test_snapshot_financial_and_event_sources_are_replay_fenced(self):
        adapters = dataset_adapters(lambda _: b"[]")
        for key in ("mops", "finmind", "twse-events"):
            adapter = adapters[key]
            self.assertEqual(adapter.observation_mode, "fetch_time")
            self.assertEqual(adapter.max_replay_age_days, 7)
        for key in ("mops", "finmind"):
            adapter = adapters[key]
            self.assertEqual(adapter.availability_field, "availability_at")
            self.assertIs(adapter.publication_time_authoritative, False)
        self.assertEqual(adapters["tpex-benchmark"].row_date_field, "trade_date")


if __name__ == "__main__":
    unittest.main()
