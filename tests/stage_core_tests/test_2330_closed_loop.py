import asyncio
import json
import unittest
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from ingestion_core.adapters import CollectionRequest, SourceResponse
from ingestion_core.control import SQLiteControlPlane
from ingestion_core.pipeline import run_2330
from ingestion_core.stage import LocalObjectStore
from ingestion_core.core import LocalEventSink


class FakeAdapter:
    source_id = "twse"
    endpoint = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    def fetch(self, request: CollectionRequest) -> SourceResponse:
        return SourceResponse(rows=({"symbol": "2330", "market": "TWSE", "trade_date": "2026-08-25", "open": "1000", "high": "1030", "low": "995", "close": "1020", "volume_shares": 0, "turnover_twd": 0, "change_percent": "12.5", "source_id": "twse", "observed_at": "2026-08-25T00:00:00Z"},), observed_at=datetime.combine(request.window_end, datetime.min.time(), tzinfo=timezone.utc))


class ClosedLoopTests(unittest.TestCase):
    def test_2330_source_stage_core_and_ready_event(self):
        with tempfile.TemporaryDirectory() as directory:
            events = LocalEventSink()
            with SQLiteControlPlane(Path(directory) / "control.db") as control:
                store = LocalObjectStore(Path(directory) / "objects")
                result = asyncio.run(run_2330(control=control, store=store, adapters={"twse": FakeAdapter()}, as_of=date(2026, 8, 25), events=events))
                self.assertEqual(result.ingestion.status.value, "succeeded")
                self.assertIsNotNone(result.core)
                self.assertEqual(result.core.row_count, 1)
                self.assertEqual((result.core.date_from, result.core.date_to), ("2026-08-25", "2026-08-25"))
                self.assertEqual(result.core.null_profile["close"], 0)
                self.assertEqual(result.core.warning_count, 1)
                self.assertTrue(result.raw_object_names)
                self.assertEqual(events.events[0]["eventType"], "core.dataset.ready.v1")
                self.assertGreaterEqual(len(list((Path(directory) / "objects").rglob("metadata.json"))), 2)
                sidecar = json.loads((Path(directory) / "objects" / result.raw_object_names[0]).with_name("metadata.json").read_text())
                self.assertEqual((sidecar["provenance"]["source_id"], sidecar["provenance"]["dataset_id"]), ("twse", "ohlcv"))
                self.assertIsNotNone(sidecar["provenance"]["observed_at"])
                self.assertIsNotNone(sidecar["provenance"]["fetched_at"])
                second = asyncio.run(run_2330(control=control, store=store, adapters={"twse": FakeAdapter()}, as_of=date(2026, 8, 25), events=events, existing_core=list(result.core.rows)))
                self.assertEqual(second.core.content_hash, result.core.content_hash)
                self.assertEqual([{key: value for key, value in row.items() if key not in {"execution_id", "provenance_id"}} for row in second.core.rows], [{key: value for key, value in row.items() if key not in {"execution_id", "provenance_id"}} for row in result.core.rows])
                self.assertEqual(len(list((Path(directory) / "objects").rglob("payload.json"))), 1)
