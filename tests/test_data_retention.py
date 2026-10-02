from datetime import datetime, timezone
from types import SimpleNamespace

from ingestion_core.retention import retained_core_rows, clean_stage
from packages.duckdb_query.iceberg import DuckDBIcebergCore


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
