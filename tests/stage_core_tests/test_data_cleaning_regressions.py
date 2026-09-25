import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))
sys.path.insert(0, str(ROOT))

from ingestion_core.first_batch import normalise_financials, normalise_institutional


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


if __name__ == "__main__":
    unittest.main()
