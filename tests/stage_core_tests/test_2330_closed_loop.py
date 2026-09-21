import asyncio
import json
import sys
import unittest
import tempfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core.adapters import CollectionRequest, SourceResponse
from ingestion_core.control import SQLiteControlPlane
from ingestion_core.pipeline import run_2330
from ingestion_core.stage import LocalObjectStore
from ingestion_core.core import LocalEventSink
from apps.web.server import WebApplication
from packages.admin_api import AdminService


class FakeAdapter:
    source_id = "twse"
    endpoint = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    def fetch(self, request: CollectionRequest) -> SourceResponse:
        return SourceResponse(rows=({"symbol": "2330", "market": "TWSE", "trade_date": "2026-08-25", "open": "1000", "high": "1030", "low": "995", "close": "1020", "volume_shares": 0, "turnover_twd": 0, "change_percent": "12.5", "source_id": "twse", "observed_at": "2026-08-25T00:00:00Z"},), observed_at=datetime.combine(request.window_end, datetime.min.time(), tzinfo=timezone.utc))


class ReplayAdapter(FakeAdapter):
    def __init__(self):
        self.calls = 0

    def fetch(self, request: CollectionRequest) -> SourceResponse:
        self.calls += 1
        accepted = dict(super().fetch(request).rows[0])
        if self.calls > 1:
            accepted["close"] = None
        quarantined = {**accepted, "trade_date": "2026-08-24", "high": "900"}
        return SourceResponse(rows=(accepted, quarantined), observed_at=datetime.combine(request.window_end, datetime.min.time(), tzinfo=timezone.utc))


class PersistedCoreSummary:
    """Test reader for the exact Core data and summary committed by CoreWriter."""

    def __init__(self, store: LocalObjectStore):
        self.store = store

    def summary(self, symbol: str, *, datasets=None):
        assert datasets == ("ohlcv",)
        prefix = f"core/ohlcv/v1/symbol={symbol}"
        rows = json.loads(self.store.read(f"{prefix}/data.json"))
        summary = json.loads(self.store.read(f"{prefix}/metadata.json"))
        associations = {
            field: sorted({str(row[field]) for row in rows if row.get(field) not in (None, "")})
            for field in ("source_id", "execution_id", "provenance_id")
        }
        return {"symbol": symbol, "datasets": {"ohlcv": {
            "row_count": summary["row_count"], "latest_date": summary["date_to"],
            "coverage": {"received_symbols": 1 if rows else 0, "requested_symbols": 1},
            "null_profile": summary["null_profile"],
            "quality_flags": ("warning",) if summary["warning_count"] else (),
            "warning_count": summary["warning_count"],
            "quarantined_count": summary["quarantined_count"],
            "associations": associations,
        }}}


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

    def test_2330_persisted_source_stage_core_is_queryable_by_admin(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = ReplayAdapter()
            events = LocalEventSink()
            with SQLiteControlPlane(Path(directory) / "control.db") as control:
                store = LocalObjectStore(Path(directory) / "objects")
                first = asyncio.run(run_2330(control=control, store=store, adapters={"twse": adapter}, as_of=date(2026, 8, 25), events=events))
                self.assertEqual(first.core.row_count, 1)
                self.assertEqual(first.core.warning_count, 2)
                self.assertEqual(first.core.quarantined_count, 1)
                self.assertTrue(first.raw_object_names)
                self.assertTrue(first.quarantine_prefixes)
                self.assertTrue(store.read(first.raw_object_names[0]))
                self.assertTrue(store.list(first.quarantine_prefixes[0]))
                self.assertEqual(events.events[0]["executionId"], first.execution_id)

                app = WebApplication(admin=AdminService(control, core=PersistedCoreSummary(store)))
                response_status = []
                response = b"".join(app({
                    "PATH_INFO": "/api/v1/admin/stocks/2330/status",
                    "REQUEST_METHOD": "GET", "CONTENT_LENGTH": "0", "wsgi.input": BytesIO(),
                }, lambda status, headers: response_status.append(status)))
                status = json.loads(response)
                item = status["items"][0]

                self.assertEqual(response_status, ["200 OK"])
                self.assertEqual((item["dataset_id"], item["latest_date"], item["row_count"]), ("ohlcv", "2026-08-25", 1))
                self.assertEqual((item["received_symbols"], item["requested_symbols"]), (1, 1))
                self.assertEqual((item["dq_warning_count"], item["quarantine_count"], item["quarantine_state"]), (2, 1, "available"))
                self.assertEqual(item["execution_ids"], [first.execution_id])
                self.assertEqual(item["provenance_ids"], [first.core.provenance_id])
                self.assertEqual(adapter.calls, 1, "Admin query must not call the source adapter")
                safe_response = response.decode().lower()
                for forbidden in ("payload", "object_uri", "https://", "secret", "upstream error", "traceback"):
                    self.assertNotIn(forbidden, safe_response)

                replay = asyncio.run(run_2330(control=control, store=store, adapters={"twse": adapter}, as_of=date(2026, 8, 25), existing_core=list(first.core.rows)))
                self.assertEqual(replay.core.row_count, 1)
                self.assertEqual(replay.core.rows[0]["close"], first.core.rows[0]["close"])
                self.assertEqual(replay.core.content_hash, first.core.content_hash)
