import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core.dq import merge_without_null_overwrite, semantic_zero, validate_ohlcv
from ingestion_core.stage import LocalObjectStore, StageWriter
from packages.provenance import Provenance, content_hash
from ingestion_core.__main__ import _empty_is_nonfatal, _limit_response, _requested_dates
from ingestion_core.adapters import SourceResponse


class StageWriterTests(unittest.TestCase):
    def provenance(self, payload: bytes) -> Provenance:
        return Provenance(
            provenance_id="prov-1",
            source_id="twse",
            source_url="https://example.twse.test/api?api_key=secret#fragment",
            dataset_id="ohlcv",
            observed_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
            published_at=None,
            fetched_at=datetime(2026, 8, 25, 1, tzinfo=timezone.utc),
            content_hash=content_hash(payload),
            quality_details={"rows": 1},
        )

    def test_raw_sidecar_manifest_and_idempotent_reuse(self):
        payload = b'{"symbol":"2330"}'
        with tempfile.TemporaryDirectory() as directory:
            writer = StageWriter(LocalObjectStore(Path(directory)))
            first = writer.write_raw(
                payload=payload,
                media_type="application/json",
                extension="json",
                execution_id="exec-1",
                provenance=self.provenance(payload),
            )
            second = writer.write_raw(
                payload=payload,
                media_type="application/json",
                extension="json",
                execution_id="exec-2",
                provenance=self.provenance(payload),
            )
            self.assertFalse(first.reused)
            self.assertTrue(second.reused)
            self.assertEqual(first.object_name, second.object_name)
            self.assertTrue((Path(directory) / second.manifest_name).exists())
            sidecar = json.loads((Path(directory) / first.sidecar_name).read_text(encoding="utf-8"))
            self.assertEqual(sidecar["provenance"]["source_url"], "https://example.twse.test/api")
            self.assertNotIn("secret", json.dumps(sidecar))

    def test_quarantine_writes_payload_and_violations(self):
        payload = b"bad,csv"
        with tempfile.TemporaryDirectory() as directory:
            writer = StageWriter(LocalObjectStore(Path(directory)))
            prefix = writer.quarantine(
                payload=payload,
                media_type="text/csv",
                extension="csv",
                execution_id="exec-1",
                provenance=self.provenance(payload),
                violations=[{"code": "SCHEMA_DRIFT", "field": "x", "message": "unexpected"}],
            )
            self.assertTrue((Path(directory) / prefix / "payload.csv").exists())
            self.assertTrue((Path(directory) / prefix / "violations.json").exists())

    def test_payload_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = StageWriter(LocalObjectStore(Path(directory)))
            with self.assertRaises(ValueError):
                writer.write_raw(
                    payload=b"changed",
                    media_type="application/json",
                    extension="json",
                    execution_id="exec-1",
                    provenance=self.provenance(b"original"),
                )

    def test_execution_scoped_stage_is_cleaned_only_after_core_commit(self):
        payload = b'{"symbol":"2330"}'
        with tempfile.TemporaryDirectory() as directory:
            store = LocalObjectStore(Path(directory))
            writer = StageWriter(store)
            staged = writer.write_raw(payload=payload, media_type="application/json", extension="json",
                                      execution_id="exec-1", provenance=self.provenance(payload), execution_scoped=True)
            self.assertTrue(Path(directory, staged.object_name).exists())
            self.assertEqual(writer.cleanup_committed_execution("exec-1"), {"committed": False, "deleted": 0})
            self.assertTrue(Path(directory, staged.object_name).exists())
            writer.mark_core_committed("exec-1", stage_results=(staged,))
            result = writer.cleanup_committed_execution("exec-1")
            self.assertEqual(result, {"committed": True, "deleted": 3})
            self.assertFalse(Path(directory, staged.object_name).exists())

    def test_failed_execution_without_commit_fence_is_preserved(self):
        payload = b'{"symbol":"2330"}'
        with tempfile.TemporaryDirectory() as directory:
            store = LocalObjectStore(Path(directory))
            writer = StageWriter(store)
            staged = writer.write_raw(payload=payload, media_type="application/json", extension="json",
                                      execution_id="exec-failed", provenance=self.provenance(payload), execution_scoped=True)
            self.assertEqual(writer.cleanup_committed_execution("exec-failed"), {"committed": False, "deleted": 0})
            self.assertTrue(Path(directory, staged.object_name).exists())

    def test_replay_date_resolution_supports_single_day_and_bounded_range(self):
        holidays = {date(2026, 8, 24)}
        self.assertEqual(_requested_dates(today=date(2026, 8, 26), holidays=holidays, single="2026-08-24"), (date(2026, 8, 21),))
        self.assertEqual(_requested_dates(today=date(2026, 8, 26), holidays=set(), start="2026-08-24", end="2026-08-25"), (date(2026, 8, 24), date(2026, 8, 25)))
        with self.assertRaises(ValueError):
            _requested_dates(today=date(2026, 8, 26), holidays=set(), start="2026-08-25")

    def test_selected_symbol_filter_is_applied_before_stage(self):
        response = SourceResponse(
            rows=(
                {"symbol": "2330", "close": "100"},
                {"symbol": "1102", "close": "20"},
                {"symbol": "9999", "close": "1"},
            ),
            raw_payload=b"full-market-payload",
        )
        limited = _limit_response(response, ("2330", "1102"))
        self.assertEqual([row["symbol"] for row in limited.rows], ["2330", "1102"])
        self.assertNotIn(b"full-market-payload", limited.raw_payload or b"")

    def test_sparse_financial_and_event_sources_allow_empty_windows(self):
        self.assertTrue(_empty_is_nonfatal("finmind"))
        self.assertTrue(_empty_is_nonfatal("twse-events"))
        self.assertFalse(_empty_is_nonfatal("twse-valuation"))


class CoreDqTests(unittest.TestCase):
    def valid_row(self):
        return {
            "symbol": "2330",
            "market": "TWSE",
            "trade_date": "2026-08-25",
            "open": "1000",
            "high": "1030",
            "low": "995",
            "close": "1020",
            "volume_shares": 0,
            "turnover_twd": 0,
            "change_percent": "12.5",
            "source_id": "twse",
            "observed_at": "2026-08-25T06:00:00Z",
        }

    def test_extreme_move_is_retained_with_warning(self):
        result = validate_ohlcv([self.valid_row()], analysis_as_of=date(2026, 8, 25))
        self.assertEqual(len(result.accepted), 1)
        self.assertEqual(result.accepted[0]["volume_shares"], Decimal("0"))
        self.assertEqual(result.warnings[0][1].code, "EXTREME_MOVE_REVIEW")

    def test_duplicate_schema_drift_and_future_date_are_quarantined(self):
        row = self.valid_row()
        duplicate = self.valid_row() | {"unexpected": 1}
        result = validate_ohlcv([row, duplicate], analysis_as_of=date(2026, 8, 24))
        codes = {violation.code for _, violations in result.quarantined for violation in violations}
        self.assertTrue({"FUTURE_DATE", "DUPLICATE", "SCHEMA_DRIFT"}.issubset(codes))

    def test_null_does_not_overwrite_and_zero_is_semantic(self):
        self.assertEqual(merge_without_null_overwrite({"close": 10}, {"close": None})["close"], 10)
        self.assertEqual(semantic_zero(0, "volume_shares"), 0)
        with self.assertRaises(ValueError):
            semantic_zero(0, "close")

    def test_price_range_and_type_fail(self):
        row = self.valid_row() | {"high": "900", "close": "not-a-number"}
        result = validate_ohlcv([row], analysis_as_of=date(2026, 8, 25))
        codes = {violation.code for violation in result.quarantined[0][1]}
        self.assertIn("TYPE", codes)
        self.assertIn("PRICE_RANGE", codes)


class IcebergSchemaTests(unittest.TestCase):
    def test_ohlcv_schema_has_stable_ids_and_bounded_partitions(self):
        schema = json.loads((ROOT / "jobs/ingestion-core/schemas/core/ohlcv.v1.json").read_text())
        ids = [field["id"] for field in schema["schema"]["fields"]]
        self.assertEqual(len(ids), len(set(ids)))
        transforms = {field["transform"] for field in schema["partition-spec"]}
        self.assertEqual(transforms, {"month", "bucket[32]"})
        self.assertEqual(schema["format-version"], 2)

    def test_first_phase_core_catalog_is_complete_and_versioned(self):
        catalog = json.loads((ROOT / "jobs/ingestion-core/schemas/core/catalog.v1.json").read_text())
        self.assertEqual(
            set(catalog["tables"]),
            {"valuation_v1", "institutional_v1", "financials_v1", "events_v1", "market_activity_v1", "benchmark_v1"},
        )
        for table in catalog["tables"].values():
            self.assertIn("provenance_id", table["required_fields"])
            self.assertIn("execution_id", table["required_fields"])
            self.assertTrue(table["partitions"])
        self.assertEqual(catalog["evolution"]["snapshots"], "immutable")


if __name__ == "__main__":
    unittest.main()
