import shutil
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from packages.duckdb_query import DuckDBEngine, DuckDBIcebergCore, IcebergQuery
from packages.web_api import CoreQueryService


class DuckDBIcebergTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(".tmp") / f"iceberg-unit-{uuid4()}"
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

    def tearDown(self):
        self.core.close()
        shutil.rmtree(self.root)

    def test_natural_key_replay_reuses_snapshot_and_null_does_not_overwrite(self):
        first = self.core.write(
            dataset_id="valuation",
            rows=[{"symbol": "2330", "market": "TWSE", "observed_date": "2026-08-25", "pe_ratio": "20"}],
            execution_id="exec-1", provenance_id="prov-1", source_id="twse", partition_date=date(2026, 8, 25),
        )
        replay = self.core.write(
            dataset_id="valuation",
            rows=[{"symbol": "2330", "market": "TWSE", "observed_date": "2026-08-25", "pe_ratio": None}],
            execution_id="exec-2", provenance_id="prov-2", source_id="twse", partition_date=date(2026, 8, 25),
        )
        self.assertEqual((first.inserted, replay.reused, replay.updated), (1, 1, 0))
        self.assertEqual(first.snapshot_id, replay.snapshot_id)
        query = IcebergQuery(self.catalog, self.engine)
        self.assertEqual(
            query.query("core.valuation_v1", "SELECT symbol, pe_ratio FROM core_table"),
            ({"symbol": "2330", "pe_ratio": "20"},),
        )

    def test_content_change_creates_update_snapshot(self):
        common = dict(dataset_id="benchmark", execution_id="exec-1", provenance_id="prov", source_id="taiex",
                      partition_date=date(2026, 8, 25))
        first = self.core.write(rows=[{"benchmark_id": "TAIEX", "trade_date": "2026-08-25", "close": "24000"}], **common)
        second = self.core.write(rows=[{"benchmark_id": "TAIEX", "trade_date": "2026-08-25", "close": "24001"}], **common)
        self.assertEqual(second.updated, 1)
        self.assertNotEqual(first.snapshot_id, second.snapshot_id)

    def test_core_summary_aggregates_exact_row_and_null_counts(self):
        self.core.write(
            dataset_id="valuation",
            rows=[
                {"symbol": "2330", "market": "TWSE", "observed_date": "2026-08-25", "pe_ratio": "20"},
                {"symbol": "2330", "market": "TWSE", "observed_date": "2026-08-26", "pe_ratio": None},
            ],
            execution_id="exec-1", provenance_id="prov-1", source_id="twse", partition_date=date(2026, 8, 26),
        )
        summary = CoreQueryService(IcebergQuery(self.catalog, self.engine).query).summary("2330", datasets=("valuation",))["datasets"]["valuation"]

        self.assertEqual(summary["row_count"], 2)
        self.assertEqual(summary["null_profile"]["pe_ratio"], 1)

    def test_additive_schema_evolution_preserves_field_ids_and_old_snapshot(self):
        common = dict(dataset_id="valuation", execution_id="exec-1", provenance_id="prov", source_id="twse",
                      partition_date=date(2026, 8, 25))
        first = self.core.write(
            rows=[{"symbol": "2330", "market": "TWSE", "observed_date": "2026-08-25", "pe_ratio": "20"}],
            **common,
        )
        table = self.catalog.load_table(first.table_identifier)
        original_ids = {field.name: field.field_id for field in table.schema().fields}

        second = self.core.write(
            rows=[{"symbol": "2317", "market": "TWSE", "observed_date": "2026-08-25",
                   "pe_ratio": "15", "earnings_yield_percent": "6.67"}],
            **common,
        )
        table = self.catalog.load_table(second.table_identifier)
        evolved_ids = {field.name: field.field_id for field in table.schema().fields}

        self.assertEqual({name: evolved_ids[name] for name in original_ids}, original_ids)
        self.assertGreater(evolved_ids["earnings_yield_percent"], max(original_ids.values()))
        self.assertIn(first.snapshot_id, {snapshot.snapshot_id for snapshot in table.snapshots()})
        self.assertEqual(table.scan(snapshot_id=first.snapshot_id).to_arrow().num_rows, 1)
        self.assertEqual(
            IcebergQuery(self.catalog, self.engine).query(
                "core.valuation_v1",
                "SELECT symbol, earnings_yield_percent FROM core_table ORDER BY symbol",
            ),
            (
                {"symbol": "2317", "earnings_yield_percent": "6.67"},
                {"symbol": "2330", "earnings_yield_percent": None},
            ),
        )

    def test_incompatible_type_change_is_rejected_without_new_snapshot(self):
        common = dict(dataset_id="benchmark", execution_id="exec-1", provenance_id="prov", source_id="taiex",
                      partition_date=date(2026, 8, 25))
        first = self.core.write(
            rows=[{"benchmark_id": "TAIEX", "trade_date": "2026-08-25", "close": 24000}],
            **common,
        )

        with self.assertRaises((TypeError, ValueError)):
            self.core.write(
                rows=[{"benchmark_id": "TAIEX", "trade_date": "2026-08-25", "close": "not-a-number"}],
                **common,
            )

        table = self.catalog.load_table(first.table_identifier)
        self.assertEqual(table.current_snapshot().snapshot_id, first.snapshot_id)
        self.assertEqual(
            IcebergQuery(self.catalog, self.engine).query(
                "core.benchmark_v1", "SELECT close FROM core_table"
            ),
            ({"close": 24000},),
        )

    def test_timestamp_offsets_are_normalised_to_utc_before_iceberg_write(self):
        import pyarrow as pa

        rows = [
            self.core._normalise(
                {"event_id": "event-1", "symbol": "2330", "event_type": "material_information",
                 "published_at": "2026-08-28T12:34:56+08:00"},
                "exec-1", "prov-1", "twse",
            ),
            self.core._normalise(
                {"event_id": "event-2", "symbol": "2330", "event_type": "material_information",
                 "published_at": datetime(2026, 8, 28, 13, 34, 56, tzinfo=timezone(timedelta(hours=8)))},
                "exec-1", "prov-1", "twse",
            ),
        ]
        arrow = self.core._arrow_table(rows)

        self.assertEqual(arrow.schema.field("published_at").type, pa.timestamp("us", tz="UTC"))
        self.catalog.create_table(
            "core.events_v1",
            arrow.schema,
            location=(self.root / "warehouse" / "events_v1").as_posix(),
        )
        self.assertEqual(
            [row["published_at"] for row in rows],
            [
                datetime(2026, 8, 28, 4, 34, 56, tzinfo=timezone.utc),
                datetime(2026, 8, 28, 5, 34, 56, tzinfo=timezone.utc),
            ],
        )


if __name__ == "__main__":
    unittest.main()
