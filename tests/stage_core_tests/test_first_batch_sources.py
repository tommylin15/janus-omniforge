import asyncio
import json
import tempfile
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from ingestion_core.adapters import CollectionRequest
from ingestion_core.control import CollectionConfig, SQLiteControlPlane, Stock
from ingestion_core.stage import LocalObjectStore
from ingestion_core.first_batch import (JsonDatasetAdapter, effective_trading_day,
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

    def test_benchmark_updates_independently_of_stock_rows_and_calendar_looks_back(self):
        self.assertEqual(effective_trading_day(date(2026, 8, 30)), date(2026, 8, 28))
        self.assertEqual(effective_trading_day(date(2026, 8, 31), holidays={date(2026, 8, 31)}), date(2026, 8, 28))

    def test_raw_payload_is_staged_and_cache_record_is_uri_only(self):
        raw = json.dumps({"data": [{"date": "2026-08-25", "close": "23000"}]}).encode()
        response = JsonDatasetAdapter("taiex", "benchmark", "https://example.test/data", normalise_benchmark, lambda _: raw).fetch(self.request())
        with tempfile.TemporaryDirectory() as directory:
            staged, metadata = stage_raw_response(response, self.request(), bucket="janus-stage", store=LocalObjectStore(Path(directory)))
            self.assertTrue((Path(directory) / staged.object_name).exists())
            self.assertEqual(metadata.payload_uri, f"gs://janus-stage/{staged.object_name}")
            self.assertTrue(metadata.content_hash.startswith("sha256:"))

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
