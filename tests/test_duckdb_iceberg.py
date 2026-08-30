import shutil
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from packages.duckdb_query import DuckDBEngine, DuckDBIcebergCore, IcebergQuery


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
