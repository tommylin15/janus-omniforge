"""Regression: no duplicate PyIceberg manifest planning on the read hot path."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs" / "intelligence-mart"))
from intelligence_mart.analytics_reader import IcebergSnapshotReader


class FakeScan:
    def __init__(self):
        self.plan_calls = 0

    def plan_files(self):
        self.plan_calls += 1
        return [SimpleNamespace(length=128)]

    def to_arrow(self):
        return SimpleNamespace(to_pylist=lambda: [{"close": "100"}])


class FakeCatalog:
    def __init__(self):
        self.scan = FakeScan()

    def load_table(self, identifier):
        if identifier != "core.ohlcv_v1":
            raise AssertionError("unexpected table")
        scan = self.scan
        return SimpleNamespace(
            schema=lambda: SimpleNamespace(fields=[SimpleNamespace(name="close")]),
            scan=lambda **kwargs: scan,
        )


class IcebergAnalyticsReadCostTests(unittest.TestCase):
    manifest = {"snapshot_id": "snapshot-hash",
                "iceberg_tables": {"core.ohlcv_v1": {"snapshot_id": 123}}}

    def test_default_read_skips_second_manifest_plan(self):
        catalog = FakeCatalog()
        with patch.dict(os.environ, {"ICEBERG_SCAN_PLAN_DIAGNOSTICS": "false"}):
            result = IcebergSnapshotReader(catalog).read(
                self.manifest, (), core_snapshot_id="snapshot-hash"
            )
        self.assertEqual(catalog.scan.plan_calls, 0)
        self.assertEqual(result.telemetry["total_rows"], 1)
        self.assertFalse(result.telemetry["scan_evidence"]["ohlcv"]["plan_diagnostics_enabled"])
        self.assertIsNone(result.telemetry["scan_evidence"]["ohlcv"]["planned_file_count"])

    def test_explicit_bounded_diagnostics_keep_planned_file_count(self):
        catalog = FakeCatalog()
        with patch.dict(os.environ, {"ICEBERG_SCAN_PLAN_DIAGNOSTICS": "true"}):
            result = IcebergSnapshotReader(catalog).read(
                self.manifest, (), core_snapshot_id="snapshot-hash"
            )
        self.assertEqual(catalog.scan.plan_calls, 1)
        self.assertTrue(result.telemetry["scan_evidence"]["ohlcv"]["plan_diagnostics_enabled"])
        self.assertEqual(result.telemetry["scan_evidence"]["ohlcv"]["planned_file_count"], 1)
        self.assertEqual(result.telemetry["scan_evidence"]["ohlcv"]["planned_scan_bytes"], 128)


if __name__ == "__main__":
    unittest.main()
