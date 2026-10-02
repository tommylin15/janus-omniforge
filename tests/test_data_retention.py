from datetime import datetime, timezone
from types import SimpleNamespace

from ingestion_core.retention import retained_core_rows, clean_stage
from packages.duckdb_query.iceberg import DuckDBIcebergCore


def test_mart_retention_uses_psycopg_database_option(monkeypatch):
    import pytest
    import psycopg
    from intelligence_mart import retention
    monkeypatch.setenv("MART_BUCKET", "gen-lang-client-0593591102-dev-mart")
    monkeypatch.setenv("MART_RETENTION_MODE", "dry-run")
    monkeypatch.setattr(retention, "load_postgres_bundle", lambda *_: None)
    monkeypatch.setattr(retention, "_settings", lambda _: {"host": "private", "name": "janus", "user": "worker", "password": "fixture"})
    monkeypatch.setattr(retention, "sql_catalog_from_environment", lambda: None)
    monkeypatch.setattr(retention, "MartIcebergStore", lambda *_: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(retention, "GcsObjectStore", lambda _: None)
    def connect(**kwargs):
        assert kwargs["dbname"] == "janus" and "name" not in kwargs
        raise RuntimeError("connection checked")
    monkeypatch.setattr(psycopg, "connect", connect)
    with pytest.raises(RuntimeError, match="connection checked"):
        retention.run()


def test_maintenance_preserves_extra_publication_references(monkeypatch):
    from ingestion_core import iceberg_maintenance as maintenance
    prefix = "gs://dev/warehouse/report/metadata/"
    snapshot = SimpleNamespace(snapshot_id=1, summary={"total-records": "2"})
    scanned = []
    table = SimpleNamespace(properties={maintenance.METADATA_HISTORY: "10"},
                            metadata_location=prefix + "current.metadata.json",
                            metadata=SimpleNamespace(metadata_log=[]), current_snapshot=lambda: snapshot,
                            scan=lambda snapshot_id, limit: SimpleNamespace(to_arrow=lambda: scanned.append(snapshot_id)))
    core = SimpleNamespace(IDENTIFIERS=("report",), table_identifier=lambda _: "mart.report",
                           catalog=SimpleNamespace(load_table=lambda _: table))
    store = SimpleNamespace(bucket="dev", objects=lambda _: [])
    monkeypatch.setattr(maintenance, "_references", lambda *_: ({1}, {prefix + "manifest.metadata.json"}))
    monkeypatch.setattr(maintenance, "_keep_snapshots", lambda *_: {1, 2})
    table.snapshots = lambda: [SimpleNamespace(snapshot_id=1), SimpleNamespace(snapshot_id=2)]
    result = maintenance.maintain_financials(core=core, store=store, apply=True, identifier="mart.report",
                                           protected_snapshot_ids={2}, protected_metadata={prefix + "published.metadata.json"})
    assert result["referenced_snapshots"] == 2 and set(scanned) == {1, 2}


def test_financial_retention_preserves_twelve_periods_per_symbol_and_original_metadata():
    core = SimpleNamespace(_financial_observations=DuckDBIcebergCore._financial_observations)
    def row(symbol, year):
        return {"symbol": symbol, "fiscal_year": year, "fiscal_quarter": 1, "statement_type": "income",
                "source_id": "mops", "metric": "revenue", "value": "100", "published_at": f"{year}-05-01",
                "availability_at": None, "publication_time_authoritative": None}
    rows = [row("old", year) for year in range(2000, 2013)] + [row("new", year) for year in range(2014, 2027)]
    kept = retained_core_rows(core, "financials", rows, datetime(2026, 10, 2, tzinfo=timezone.utc))
    assert len(kept) == 24
    assert min(item["fiscal_year"] for item in kept if item["symbol"] == "old") == 2001
    assert all(item["availability_at"] is None and item["publication_time_authoritative"] is None for item in kept)


def test_stage_deletes_only_old_committed_payload_and_reports_actual_bytes():
    import json
    prefix = "executions/test/stage/"
    items = [{"name": "executions/test/core-commit.json", "size": "10", "generation": "1", "updated": "2026-09-01T00:00:00Z"},
             {"name": prefix + "raw/payload.json", "size": "123", "generation": "2", "updated": "2026-09-01T00:00:00Z"},
             {"name": prefix + "quarantine/unknown.json", "size": "456", "generation": "3", "updated": "2026-09-01T00:00:00Z"}]
    deletes = []
    store = SimpleNamespace(bucket="dev", objects=lambda _: items,
                            read=lambda _: json.dumps({"execution_id": "test", "stage_objects": [prefix + "raw/payload.json"]}).encode(),
                            delete=lambda name, generation: deletes.append((name, generation)))
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)
    planned = clean_stage(store, apply=False, now=now)
    assert planned["planned_bytes"] == 123 and planned["deleted_bytes"] == 0 and not deletes
    actual = clean_stage(store, apply=True, now=now)
    assert actual["deleted_bytes"] == 123 and actual["held_quarantine_objects"] == 1
    assert deletes == [(prefix + "raw/payload.json", "2")]
