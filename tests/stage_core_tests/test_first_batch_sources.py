import asyncio
import json
import tempfile
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from ingestion_core.adapters import CollectionRequest
from ingestion_core.control import CollectionConfig, SQLiteControlPlane, Stock
from ingestion_core.stage import LocalObjectStore
from ingestion_core.core import IncrementalCoreWriter
from packages.duckdb_query import DuckDBIcebergCore
from ingestion_core.first_batch import (JsonDatasetAdapter, effective_trading_day,
    dataset_adapters,
    normalise_benchmark, normalise_events, normalise_financials,
    normalise_institutional, normalise_market_activity, normalise_valuation,
    stage_raw_response)


class FirstBatchSourceTests(unittest.TestCase):
    def request(self, dataset="benchmark"):
        return CollectionRequest("e1", "t1", "taiex", dataset, "TWSE", ("2330",), None, date(2026, 8, 25), 5)

    def test_all_first_batch_normalisers_are_typed_and_unit_preserving(self):
        self.assertEqual(normalise_benchmark([{"date": "115/08/25", "close": "23,000", "change": "1.2"}], "TAIEX")[0]["trade_date"], "2026-08-25")
        valuation = normalise_valuation([{"code": "2330", "date": "2026-08-25", "pe": 20, "pb": 5}])[0]
        self.assertEqual((valuation["symbol"], valuation["pe_ratio"], valuation["pb_ratio"]), ("2330", "20", "5"))
        institutional = normalise_institutional([{"code": "2330", "date": "2026-08-25", "investor": "foreign", "buy": "1,000", "sell": "200"}])[0]
        self.assertEqual(institutional["net_shares"], None)
        financial = normalise_financials([{"code": "2330", "year": 2025, "quarter": 4, "statement": "income", "published": "2026-02-10T00:00:00Z", "name": "revenue", "amount": 1}])[0]
        self.assertEqual((financial["fiscal_year"], financial["fiscal_quarter"]), (2025, 4))
        event = normalise_events([{"id": "x1", "code": "2330", "type": "dividend", "published": "2026-08-25T00:00:00Z", "effective": "2026-09-01"}])[0]
        self.assertEqual(event["effective_date"], "2026-09-01")
        activity = normalise_market_activity([{"code": "2330", "date": "2026-08-25", "name": "turnover_ratio", "amount": "12.5", "unit": "%"}])[0]
        self.assertEqual(activity["unit"], "%")

    def test_json_adapter_preserves_raw_payload_and_lineage_fields(self):
        raw = json.dumps({"data": [{"date": "2026-08-25", "close": "23000"}]}).encode()
        adapter = JsonDatasetAdapter("taiex", "benchmark", "https://example.test/data", normalise_benchmark, lambda _: raw)
        response = adapter.fetch(self.request())
        self.assertEqual(response.raw_payload, raw)
        self.assertEqual(response.rows[0]["source_id"], "taiex")
        self.assertEqual(response.rows[0]["observed_at"], "2026-08-25T00:00:00Z")

    def test_ohlcv_adapters_are_registered_for_symbol_scoped_runtime(self):
        raw = json.dumps({"data": [["115/08/25", "1,234", "100,000", "80", "82", "79", "81", "+1", "456"]]}).encode()
        adapters = dataset_adapters(lambda _: raw)
        response = adapters["twse-ohlcv"].fetch(self.request("ohlcv"))
        self.assertEqual((response.rows[0]["volume_shares"], response.rows[0]["change_percent"]), (1234, None))
        self.assertEqual((adapters["twse-ohlcv"].dataset_id, adapters["twse-ohlcv"].batch_scope), ("ohlcv", "symbol"))
        self.assertIn("tpex-ohlcv", adapters)
        self.assertEqual(DuckDBIcebergCore.IDENTIFIERS["ohlcv"], ("symbol", "market", "trade_date"))

    def test_benchmark_updates_independently_of_stock_rows_and_calendar_looks_back(self):
        self.assertEqual(effective_trading_day(date(2026, 8, 30)), date(2026, 8, 28))
        self.assertEqual(effective_trading_day(date(2026, 8, 31), holidays={date(2026, 8, 31)}), date(2026, 8, 28))

    def test_raw_payload_is_staged_and_cache_record_is_uri_only(self):
        raw = json.dumps({"data": [{"date": "2026-08-25", "close": "23000"}]}).encode()
        response = JsonDatasetAdapter("taiex", "benchmark", "https://example.test/data", normalise_benchmark, lambda _: raw).fetch(self.request())
        with tempfile.TemporaryDirectory() as directory:
            staged, metadata = stage_raw_response(
                response, self.request(), bucket="janus-stage", store=LocalObjectStore(Path(directory)),
                quarantine_violations=[{"code": "DQ", "field": "close", "message": "test", "severity": "critical"}],
            )
            self.assertTrue((Path(directory) / staged.object_name).exists())
            self.assertTrue(tuple(Path(directory).rglob("violations.json")))
            self.assertEqual(metadata.payload_uri, f"gs://janus-stage/{staged.object_name}")
            self.assertTrue(metadata.content_hash.startswith("sha256:"))

    def test_official_provider_shapes_are_parsed(self):
        payloads = {
            "tpex_index": [{"Date": "20260825", "Close": "362.89", "Change": "15.04"}],
            "BWIBBU_d": [{"Date": "1150825", "Code": "2330", "PEratio": "20", "PBratio": "5", "DividendYield": "2"}],
            "T86": {"date": "20260825", "fields": ["證券代號", "外陸資買進股數(不含外資自營商)", "外陸資賣出股數(不含外資自營商)", "外陸資買賣超股數(不含外資自營商)", "投信買進股數", "投信賣出股數", "投信買賣超股數", "自營商買進股數(自行買賣)", "自營商賣出股數(自行買賣)", "自營商買賣超股數"], "data": [["2330", "10", "2", "8", "3", "1", "2", "4", "1", "3"]]},
            "t187ap06": [{"出表日期": "1150826", "年度": "115", "季別": "2", "公司代號": "2330", "營業收入": "100"}],
            "finmind": {"data": [{"date": "2026-03-31", "stock_id": "2330", "type": "EPS", "value": 22.08}]},
            "t187ap04": [{"出表日期": "1150826", "發言日期": "1150825", "發言時間": "070003", "公司代號": "2330", "符合條款": "第1款", "事實發生日": "1150825", "說明": "event"}],
        }
        def transport(url):
            key = next(key for key in payloads if key in url)
            return json.dumps(payloads[key], ensure_ascii=False).encode()
        adapters = dataset_adapters(transport)
        fixture_now = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)
        for key in ("mops", "finmind", "twse-events"):
            adapters[key].clock = lambda now=fixture_now: now
        self.assertEqual(adapters["tpex-benchmark"].fetch(self.request()).rows[0]["trade_date"], "2026-08-25")
        self.assertEqual(adapters["twse-valuation"].fetch(self.request("valuation")).rows[0]["symbol"], "2330")
        self.assertEqual(len(adapters["twse-institutional"].fetch(self.request("institutional")).rows), 3)
        self.assertEqual(adapters["mops"].fetch(self.request("financials")).rows[0]["metric"], "營業收入")
        self.assertEqual(adapters["finmind"].fetch(self.request("financials")).rows[0]["metric"], "EPS")
        self.assertEqual(adapters["twse-events"].fetch(self.request("events")).rows[0]["effective_date"], "2026-08-25")

    def test_incremental_core_reuses_natural_key(self):
        row = {"benchmark_id": "TAIEX", "trade_date": "2026-08-25", "close": "23000"}
        with tempfile.TemporaryDirectory() as directory:
            writer = IncrementalCoreWriter(LocalObjectStore(Path(directory)))
            first = writer.write(dataset_id="benchmark", rows=[row], execution_id="e1", provenance_id="p1", source_id="taiex", partition_date=date(2026, 8, 25))
            replay = writer.write(dataset_id="benchmark", rows=[row], execution_id="e2", provenance_id="p2", source_id="taiex", partition_date=date(2026, 8, 25))
            self.assertEqual((first.created, first.reused), (1, 0))
            self.assertEqual((replay.created, replay.reused), (0, 1))

    def test_cache_metadata_and_execution_retention_are_prunable(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteControlPlane(Path(directory) / "control.db") as control:
                control.upsert_stock(Stock("2330", "台積電", "TWSE"))
                control.put_collection_config(CollectionConfig("c", "benchmark", ("taiex",), frozenset(), batch_scope="market"), ["2330"])
                execution = control.enqueue_collection("c", ["2330"])
                control.advance_cursor("c", datetime.now(timezone.utc), successful=True)
                removed = control.prune(before=datetime.now(timezone.utc) + timedelta(seconds=1))
                self.assertGreaterEqual(removed["executions"], 1)


if __name__ == "__main__":
    unittest.main()
