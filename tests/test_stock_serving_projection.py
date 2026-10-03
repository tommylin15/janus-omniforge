from datetime import date

from ingestion_core.serving_projection import StockServingProjection
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
