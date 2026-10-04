from datetime import date, datetime, timezone

import pytest

from ingestion_core.serving_projection import StockServingProjection, backfill_recent
from packages.duckdb_query.serving_core import ServingDuckDBIcebergCore


class Cursor:
    def __init__(self):
        self.executed = []
        self.many = []

    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def executemany(self, sql, rows):
        self.many.append((sql, list(rows)))

    def execute(self, sql, params):
        self.executed.append((sql, params))


class Transaction:
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class Connection:
    def __init__(self): self.cursor_value = Cursor()
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def transaction(self): return Transaction()
    def cursor(self): return self.cursor_value


class ArrowRows:
    def __init__(self, rows): self.rows = rows
    def to_pylist(self): return list(self.rows)


class DataFile:
    def __init__(self, size): self.file_size_in_bytes = size


class FileTask:
    def __init__(self, size): self.file = DataFile(size)


class Scan:
    def __init__(self, rows, sizes):
        self.rows = rows
        self.sizes = sizes
        self.arrow_called = False

    def plan_files(self):
        return [FileTask(size) for size in self.sizes]

    def to_arrow(self):
        self.arrow_called = True
        return ArrowRows(self.rows)


class Snapshot:
    def __init__(self, snapshot_id): self.snapshot_id = snapshot_id


class Table:
    def __init__(self, rows, sizes=(1024,), snapshot_id=77):
        self.rows = rows
        self.sizes = sizes
        self.snapshot = Snapshot(snapshot_id)
        self.last_scan = None

    def current_snapshot(self): return self.snapshot

    def scan(self, **_kwargs):
        self.last_scan = Scan(self.rows, self.sizes)
        return self.last_scan


class Catalog:
    def __init__(self, tables): self.tables = tables
    def load_table(self, identifier): return self.tables[identifier]


class Core:
    def __init__(self, tables): self.catalog = Catalog(tables)
    def table_identifier(self, dataset_id): return f"core.{dataset_id}_v1"
    def table_exists(self, dataset_id): return self.table_identifier(dataset_id) in self.catalog.tables


def test_projection_writes_bounded_recent_rows_and_strips_raw_payload():
    connection = Connection()
    projection = StockServingProjection(lambda: connection, retention_days=400)
    count = projection.publish(
        "ohlcv",
        [{"symbol": "2330", "market": "TWSE", "trade_date": date(2026, 10, 2),
          "open": "2790", "close": "2800", "raw_payload": b"not-for-serving"}],
        execution_id="11111111-1111-1111-1111-111111111111",
        provenance_id="sha256:abc", source_id="twse", core_snapshot_id=123,
    )

    assert count == 1
    _, rows = connection.cursor_value.many[0]
    row = rows[0]
    assert row[0] == "ohlcv"
    assert row[1] == "2330"
    assert row[3].isoformat().startswith("2026-10-02")
    assert '"raw_payload"' not in row[4]
    assert '"close":"2800"' in row[4]
    assert row[8] == 123
    assert connection.cursor_value.executed[-1][1] == ("ohlcv", 400)


def test_projection_ignores_non_serving_datasets():
    projection = StockServingProjection(lambda: (_ for _ in ()).throw(AssertionError("no connection")))
    assert projection.publish(
        "financials", [{"symbol": "2330"}], execution_id="x", provenance_id="p",
        source_id="s", core_snapshot_id=1,
    ) == 0


def test_serving_core_keeps_canonical_commit_success_when_projection_fails(monkeypatch):
    class Result:
        snapshot_id = 77

    calls = []

    def canonical_write(self, **kwargs):
        calls.append(kwargs)
        return Result()

    monkeypatch.setattr(
        "packages.duckdb_query.serving_core._CanonicalDuckDBIcebergCore.write",
        canonical_write,
    )
    monkeypatch.setattr(
        "ingestion_core.serving_projection.StockServingProjection.from_env",
        classmethod(lambda _cls: (_ for _ in ()).throw(RuntimeError("projection unavailable"))),
    )
    core = object.__new__(ServingDuckDBIcebergCore)
    result = core.write(
        dataset_id="ohlcv", rows=[{"symbol": "2330"}], execution_id="e",
        provenance_id="p", source_id="s", partition_date=date(2026, 10, 2),
    )

    assert result.snapshot_id == 77
    assert calls[0]["dataset_id"] == "ohlcv"


def test_backfill_preserves_canonical_provenance_and_snapshot():
    connection = Connection()
    projection = StockServingProjection(lambda: connection, retention_days=400)
    core = Core({
        "core.ohlcv_v1": Table([
            {"symbol": "2330", "market": "TWSE", "trade_date": date(2026, 10, 2),
             "close": "2800", "execution_id": "exec-1", "provenance_id": "sha256:prov",
             "source_id": "twse"}
        ], sizes=(2048,), snapshot_id=88)
    })

    report = backfill_recent(
        core, projection,
        as_of=datetime(2026, 10, 4, tzinfo=timezone.utc),
        max_rows=10, max_bytes=16 * 1024 * 1024,
    )

    assert report["published_rows"] == 1
    assert report["source_bytes"] == 2048
    assert report["datasets"]["ohlcv"]["snapshot_id"] == 88
    _, rows = connection.cursor_value.many[0]
    assert rows[0][5:9] == ("twse", "sha256:prov", "exec-1", 88)


def test_backfill_fails_closed_when_eligible_row_lacks_provenance():
    connection = Connection()
    projection = StockServingProjection(lambda: connection, retention_days=400)
    core = Core({
        "core.ohlcv_v1": Table([
            {"symbol": "2330", "market": "TWSE", "trade_date": date(2026, 10, 2),
             "close": "2800", "execution_id": "exec-1", "provenance_id": None, "source_id": "twse"}
        ])
    })

    with pytest.raises(RuntimeError, match="missing canonical provenance"):
        backfill_recent(
            core, projection,
            as_of=datetime(2026, 10, 4, tzinfo=timezone.utc),
            max_rows=10, max_bytes=16 * 1024 * 1024,
        )
    assert connection.cursor_value.many == []


def test_backfill_checks_planned_bytes_before_reading_parquet():
    projection = StockServingProjection(lambda: (_ for _ in ()).throw(AssertionError("no write")))
    table = Table([], sizes=(17 * 1024 * 1024,))
    core = Core({"core.ohlcv_v1": table})

    with pytest.raises(RuntimeError, match="byte cap exceeded before read"):
        backfill_recent(
            core, projection,
            as_of=datetime(2026, 10, 4, tzinfo=timezone.utc),
            max_rows=10, max_bytes=16 * 1024 * 1024,
        )
    assert table.last_scan is not None
    assert table.last_scan.arrow_called is False
