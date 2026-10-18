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

from ingestion_core.iceberg_maintenance import compact_core, compact_batch_events, compact_nightly, core_health
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
        metadata_location = table.metadata_location
        properties = dict(table.properties)
        with self._env():
            health = core_health(core=self.core)
        valuation = next(item for item in health["tables"] if item["dataset_id"] == "valuation")
        self.assertGreaterEqual(valuation["data_files"], 6)
        self.assertEqual(valuation["small_files"], valuation["data_files"])
        self.assertEqual(valuation["partition_fields"], ["observed_date_month"])
        self.assertEqual(self.catalog.load_table("core.valuation_v1").current_snapshot().snapshot_id, snapshot)
        # Metadata-only property changes are still writes and incur GCS requests.
        self.assertEqual(self.catalog.load_table("core.valuation_v1").metadata_location, metadata_location)
        self.assertEqual(self.catalog.load_table("core.valuation_v1").properties, properties)

    def test_weekly_compaction_manifest_fence_rejects_changed_snapshot_and_bad_digest(self):
        import json
        from hashlib import sha256
        from ingestion_core.iceberg_maintenance import verify_compaction_eod_fence
        table = self.catalog.load_table("core.valuation_v1")
        snapshot_id = table.current_snapshot().snapshot_id
        tables = {"core.valuation_v1": {"rows": 6, "snapshot_id": snapshot_id,
                                         "metadata_location": table.metadata_location}}
        def evidence(mapping):
            digest = "sha256:" + sha256(json.dumps(mapping, sort_keys=True,
                            separators=(",", ":")).encode()).hexdigest()
            return digest, json.dumps({"artifact_kind": "core_snapshot_v1",
                         "analysis_as_of": "2026-10-16", "snapshot_id": digest,
                         "iceberg_tables": mapping}).encode()
        digest, raw = evidence(tables)
        env = {"CORE_BUCKET": "gen-lang-client-0593591102-dev-core",
               "FINOPS_SOURCE_CORE_SNAPSHOT_ID": digest,
               "FINOPS_SOURCE_CORE_SNAPSHOT_URI":
                   "gs://gen-lang-client-0593591102-dev-core/executions/eod-1/core-snapshot.json",
               "FINOPS_SOURCE_EOD_DATE": "2026-10-16"}
        with patch.dict(os.environ, env), \
             patch("ingestion_core.iceberg_maintenance.GcsObjectStore") as store:
            store.return_value.read.return_value = raw
            result = verify_compaction_eod_fence(core=self.core)
            self.assertEqual(result["status"], "verified")
            self.assertEqual(result["verified_tables"], 1)
            store.return_value.read.assert_called_once_with("executions/eod-1/core-snapshot.json")
            store.return_value.read.return_value = raw.replace(digest.encode(), b"sha256:" + b"0" * 64)
            with self.assertRaisesRegex(RuntimeError, "digest_mismatch"):
                verify_compaction_eod_fence(core=self.core)
            drifted = {"core.valuation_v1": {**tables["core.valuation_v1"],
                                              "snapshot_id": snapshot_id + 99}}
            new_hash, newer_raw = evidence(drifted)
            store.return_value.read.return_value = newer_raw
            with patch.dict(os.environ, {"FINOPS_SOURCE_CORE_SNAPSHOT_ID": new_hash}):
                with self.assertRaisesRegex(RuntimeError, "catalog_changed"):
                    verify_compaction_eod_fence(core=self.core)
            with patch.dict(os.environ, {"FINOPS_SOURCE_EOD_DATE": ""}):
                with self.assertRaisesRegex(RuntimeError, "incomplete"):
                    verify_compaction_eod_fence(core=self.core)

    def test_retention_noop_lists_metadata_once_and_preserves_current_snapshot(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from ingestion_core.iceberg_maintenance import maintain_financials

        now = datetime(2026, 10, 18, 3, tzinfo=timezone.utc)
        snapshot = SimpleNamespace(snapshot_id=1234,
                                   timestamp_ms=int(now.timestamp() * 1000),
                                   summary={"total-records": "6"})
        table = MagicMock()
        table.current_snapshot.return_value = snapshot
        table.snapshots.return_value = [snapshot]
        table.properties = {"write.metadata.previous-versions-max": "10"}
        table.metadata.refs = {}
        table.metadata.metadata_log = []
        table.metadata_location = ("gs://gen-lang-client-0593591102-dev-core/"
                                   "warehouse/valuation_v1/metadata/current.metadata.json")
        core = MagicMock()
        core.IDENTIFIERS = {"valuation": ("symbol",)}
        core.table_identifier.return_value = "core.valuation_v1"
        core.catalog.load_table.return_value = table
        store = MagicMock()
        store.bucket = "gen-lang-client-0593591102-dev-core"
        store.objects.return_value = [{"name": "warehouse/valuation_v1/metadata/current.metadata.json",
                                       "size": "120", "updated": now.isoformat(), "generation": "1"}]
        with patch("ingestion_core.iceberg_maintenance._references",
                   return_value=(set(), set())):
            result = maintain_financials(core=core, store=store, apply=True,
                                         now=now, identifier="core.valuation_v1")
        self.assertEqual(store.objects.call_count, 1)
        self.assertEqual(result["active_metadata_bytes_before"], result["active_metadata_bytes_after"])
        self.assertEqual(result["deleted_metadata_json"], 0)
        store.delete.assert_not_called()
        table.transaction.assert_not_called()

    def test_no_work_compaction_reuses_preflight_health_without_second_catalog_read(self):
        table = self.catalog.load_table("core.valuation_v1")
        before = table.current_snapshot().snapshot_id
        pointer = table.metadata_location
        from ingestion_core import iceberg_maintenance as maintenance
        with patch.dict(os.environ, {"ICEBERG_COMPACTION_MIN_FILES": "1000"}), \
             patch.object(maintenance, "_data_file_health", wraps=maintenance._data_file_health) as health:
            report = compact_core(core=self.core, apply=True)
        self.assertEqual(health.call_count, 1)
        valuation = next(item for item in report["tables"] if item["dataset_id"] == "valuation")
        self.assertEqual(valuation["planned_periods"], [])
        self.assertEqual(valuation["before"], valuation["after"])
        after = self.catalog.load_table("core.valuation_v1")
        self.assertEqual(after.current_snapshot().snapshot_id, before)
        self.assertEqual(after.metadata_location, pointer)

    def test_dry_run_plans_but_does_not_rewrite(self):
        before = self.catalog.load_table("core.valuation_v1")
        snapshot = before.current_snapshot().snapshot_id
        metadata_location = before.metadata_location
        properties = dict(before.properties)
        file_count = len(before.inspect.files().to_pylist())
        with self._env():
            report = compact_core(core=self.core, apply=False)
        valuation = next(item for item in report["tables"] if item["dataset_id"] == "valuation")
        self.assertEqual([item["period"] for item in valuation["planned_periods"]], ["2026-08"])
        self.assertEqual(valuation["rewritten_periods"], [])
        after = self.catalog.load_table("core.valuation_v1")
        self.assertEqual(after.current_snapshot().snapshot_id, snapshot)
        self.assertEqual(after.metadata_location, metadata_location)
        self.assertEqual(after.properties, properties)
        self.assertEqual(len(after.inspect.files().to_pylist()), file_count)

    def test_unpartitioned_audit_compaction_reduces_files_and_preserves_history(self):
        import pyarrow as pa
        self.catalog.create_namespace_if_not_exists("ops")
        schema = pa.schema([pa.field("event_id", pa.string()), pa.field("payload_json", pa.string())])
        table = self.catalog.create_table("ops.batch_events_v1", schema)
        for index in range(6):
            table.append(pa.Table.from_pylist([{"event_id": str(index), "payload_json": "v1"}], schema=schema))
            table = self.catalog.load_table("ops.batch_events_v1")
        old_snapshot = table.current_snapshot().snapshot_id
        prior = sorted(table.scan().to_arrow().to_pylist(), key=lambda item: item["event_id"])
        dry = compact_batch_events(core=self.core, apply=False)
        self.assertEqual(dry["planned_files"], 6)
        self.assertEqual(self.catalog.load_table("ops.batch_events_v1").current_snapshot().snapshot_id, old_snapshot)
        applied = compact_batch_events(core=self.core, apply=True)
        self.assertEqual(applied["status"], "rewritten")
        table = self.catalog.load_table("ops.batch_events_v1")
        self.assertLess(len(table.inspect.files().to_pylist()), 6)
        self.assertEqual(sorted(table.scan().to_arrow().to_pylist(), key=lambda item: item["event_id"]), prior)
        self.assertEqual(sorted(table.scan(snapshot_id=old_snapshot).to_arrow().to_pylist(), key=lambda item: item["event_id"]), prior)

    def test_nightly_skips_retired_audit_table_and_no_work_second_scan(self):
        calls = []
        def fake_core(*, core, apply):
            calls.append(("core", apply))
            if not apply:
                return {"planned_rewrite_bytes": 12, "tables": [{"planned_periods": ["2026-10"]}]}
            return {"rewritten_bytes": 12}
        with patch("ingestion_core.iceberg_maintenance.compact_core", side_effect=fake_core), \
             patch("ingestion_core.iceberg_maintenance.compact_batch_events",
                   side_effect=AssertionError("retired audit mirror must not be scanned")):
            report = compact_nightly(core=self.core)
        self.assertEqual(calls, [("core", False), ("core", True)])
        self.assertEqual(report["mode"], "dry-run-then-apply")
        self.assertEqual(report["preflight"]["audit"]["status"], "disabled")
        calls.clear()
        def no_work(*, core, apply):
            calls.append(("core", apply))
            if apply:
                raise AssertionError("no-work must not perform apply")
            return {"planned_rewrite_bytes": 0, "tables": [{"planned_periods": []}]}
        with patch("ingestion_core.iceberg_maintenance.compact_core", side_effect=no_work), \
             patch("ingestion_core.iceberg_maintenance.compact_batch_events",
                   side_effect=AssertionError("audit table must not be scanned")):
            result = compact_nightly(core=self.core)
        self.assertEqual(calls, [("core", False)])
        self.assertEqual(result["mode"], "skipped_no_work")
        self.assertEqual(result["apply"]["core"]["reason"], "no_fragmented_periods")

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


def test_audit_only_cleanup_cannot_mutate_market_or_model_tables():
    from types import SimpleNamespace
    from ingestion_core.iceberg_maintenance import cleanup_controller_audit_only
    ops=[]
    core=SimpleNamespace(catalog=SimpleNamespace(table_exists=lambda name: name=="ops.batch_events_v1"))
    item={"name":"warehouse/batch_events_v1/data/old.parquet","size":"100"}
    before=[item,{"name":"warehouse/batch_events_v1/metadata/old.metadata.json","size":"30"}]
    state={"items":before}
    store=SimpleNamespace(bucket="gen-lang-client-0593591102-dev-core",
                          objects=lambda _: list(state["items"]))
    def fake_maintenance(*,core,store,apply,identifier):
        ops.append(("expire",identifier,apply))
        state["items"]=[item]
        return {"expired_snapshots":3}
    def fake_orphans(core,store,identifier,*,apply,now):
        ops.append(("orphans",identifier,apply))
        state["items"]=[]
        return {"deleted_objects":1}
    with patch("ingestion_core.iceberg_maintenance.maintain_financials",side_effect=fake_maintenance), \
         patch("ingestion_core.retention.clean_orphans",side_effect=fake_orphans):
        result=cleanup_controller_audit_only(core=core,store=store)
    self_expected=[("expire","ops.batch_events_v1",True),("orphans","ops.batch_events_v1",True)]
    assert ops==self_expected
    assert result["deleted_objects"]==2 and result["expired_snapshots"]==3
    assert result["canonical_tables_modified"]==0 and result["core_execution_manifests_deleted"]==0


def test_audit_only_missing_table_does_nothing():
    from types import SimpleNamespace
    from ingestion_core.iceberg_maintenance import cleanup_controller_audit_only
    core=SimpleNamespace(catalog=SimpleNamespace(table_exists=lambda _:False))
    store=SimpleNamespace(bucket="gen-lang-client-0593591102-dev-core")
    with patch("ingestion_core.iceberg_maintenance.maintain_financials") as expire:
        result=cleanup_controller_audit_only(core=core,store=store)
    expire.assert_not_called()
    assert result["deleted_objects"]==0 and result["status"]=="no-audit-table"
