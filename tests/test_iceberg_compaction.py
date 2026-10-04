import os
import shutil
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "jobs" / "ingestion-core"))

from ingestion_core.iceberg_maintenance import compact_core, core_health
from packages.duckdb_query import DuckDBEngine, DuckDBIcebergCore


class IcebergCompactionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(".tmp") / f"iceberg-compaction-{uuid4()}"
        self.root.mkdir(parents=True)
        from pyiceberg.catalog import load_catalog
        self.catalog = load_catalog(
            "unit",
            type="sql",
            uri="sqlite:///" + str((self.root.resolve() / "catalog.db")).replace("\\", "/"),
            warehouse=(self.root / "warehouse").as_posix(),
        )
        self.engine = DuckDBEngine(temp_directory=str(self.root / "duckdb"))
        self.core = DuckDBIcebergCore(self.catalog, (self.root / "warehouse").as_posix(), engine=self.engine)
        for day in range(1, 7):
            self.core.write(
                dataset_id="valuation",
                rows=[{"symbol": f"{2300 + day}", "market": "TWSE",
                       "observed_date": f"2026-08-{day:02d}", "pe_ratio": str(10 + day)}],
                execution_id=f"exec-{day}", provenance_id="prov", source_id="twse",
                partition_date=date(2026, 8, day),
            )

    def tearDown(self):
        self.core.close()
        shutil.rmtree(self.root)

    def _env(self):
        return patch.dict(os.environ, {
            "ICEBERG_TARGET_FILE_SIZE_BYTES": str(32 * 1024 * 1024),
            "ICEBERG_SMALL_FILE_THRESHOLD_BYTES": str(1024 * 1024),
            "ICEBERG_COMPACTION_MAX_PARTITION_BYTES": str(32 * 1024 * 1024),
            "ICEBERG_COMPACTION_MAX_REWRITE_BYTES": str(32 * 1024 * 1024),
            "ICEBERG_COMPACTION_MAX_PERIODS": "4",
            "ICEBERG_COMPACTION_MIN_FILES": "4",
        })

    def test_health_reports_small_files_without_mutation(self):
        table = self.catalog.load_table("core.valuation_v1")
        snapshot = table.current_snapshot().snapshot_id
        with self._env():
            health = core_health(core=self.core)
        valuation = next(item for item in health["tables"] if item["dataset_id"] == "valuation")
        self.assertGreaterEqual(valuation["data_files"], 6)
        self.assertEqual(valuation["small_files"], valuation["data_files"])
        self.assertEqual(valuation["partition_fields"], ["observed_date_month"])
        self.assertEqual(self.catalog.load_table("core.valuation_v1").current_snapshot().snapshot_id, snapshot)

    def test_dry_run_plans_but_does_not_rewrite(self):
        before = self.catalog.load_table("core.valuation_v1")
        snapshot = before.current_snapshot().snapshot_id
        file_count = len(before.inspect.files().to_pylist())
        with self._env():
            report = compact_core(core=self.core, apply=False)
        valuation = next(item for item in report["tables"] if item["dataset_id"] == "valuation")
        self.assertEqual([item["period"] for item in valuation["planned_periods"]], ["2026-08"])
        self.assertEqual(valuation["rewritten_periods"], [])
        after = self.catalog.load_table("core.valuation_v1")
        self.assertEqual(after.current_snapshot().snapshot_id, snapshot)
        self.assertEqual(len(after.inspect.files().to_pylist()), file_count)

    def test_apply_reduces_files_preserves_rows_and_old_snapshot(self):
        before = self.catalog.load_table("core.valuation_v1")
        old_snapshot = before.current_snapshot().snapshot_id
        before_files = len(before.inspect.files().to_pylist())
        before_rows = before.scan().to_arrow().to_pylist()
        with self._env():
            report = compact_core(core=self.core, apply=True)
        valuation = next(item for item in report["tables"] if item["dataset_id"] == "valuation")
        self.assertEqual(len(valuation["rewritten_periods"]), 1)
        after = self.catalog.load_table("core.valuation_v1")
        self.assertEqual(after.scan().to_arrow().to_pylist(), before_rows)
        self.assertLess(len(after.inspect.files().to_pylist()), before_files)
        self.assertEqual(after.scan(snapshot_id=old_snapshot).to_arrow().to_pylist(), before_rows)
        self.assertEqual(after.spec().fields[0].name, "observed_date_month")


if __name__ == "__main__":
    unittest.main()
