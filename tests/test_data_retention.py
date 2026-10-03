from datetime import datetime, timezone
from types import SimpleNamespace

from ingestion_core.retention import retained_core_rows, clean_stage
from packages.duckdb_query.iceberg import DuckDBIcebergCore


def test_deep_valuation_history_retained_but_other_symbols_use_one_year():
    core = SimpleNamespace(PARTITIONS={"valuation": (("observed_date", "month"),)})
    rows = [{"symbol": symbol, "observed_date": day} for symbol in ("2330", "other")
            for day in ("2022-01-01", "2024-01-01", "2026-01-01")]
    retained = retained_core_rows(core, "valuation", rows, datetime(2026, 10, 3, tzinfo=timezone.utc), frozenset({"2330"}))
    assert [(r["symbol"], r["observed_date"]) for r in retained] == [("2330", "2024-01-01"), ("2330", "2026-01-01"), ("other", "2026-01-01")]


def test_mart_cleanup_delete_permission_is_bucket_scoped():
    import json
    from pathlib import Path
    role = json.loads(Path("infra/gcp/dev-mart-retention-iam.json").read_text())
    assert role["includedPermissions"] == ["storage.objects.delete"]
    deploy = Path("scripts/gcp/deploy-dev.sh").read_text()
    assert 'if [[ "${ALLOW_MART_RETENTION_IAM:-false}" == "true" ]]; then' in deploy
    assert 'buckets add-iam-policy-binding "gs://${project}-dev-mart"' in deploy
    assert '--role="projects/${project}/roles/janusDevMartRetention"' in deploy


def test_mart_retention_migration_grants_only_public_reference_columns():
    from pathlib import Path
    sql = Path("infra/postgres/migrations/038_mart_retention_read.sql").read_text()
    assert "GRANT SELECT (table_identifier, iceberg_snapshot_id, artifact_uri)" in sql
    assert "ON publication.mart_report_index TO janus_mart_publication" in sql
    assert "GRANT SELECT ON" not in sql and "GRANT INSERT" not in sql
    assert "BEGIN;" in sql and "COMMIT;" in sql and "ON_ERROR_STOP on" in sql


def test_bucket_cleanup_policy_matches_approved_three_days_without_soft_delete():
    import json
    from pathlib import Path
    policy = json.loads(Path("infra/private-bucket-lifecycle.json").read_text())
    assert policy == {"rule": [{"action": {"type": "Delete"}, "condition": {"daysSinceNoncurrentTime": 3}}]}
    for name in ("provision-dev.sh", "security-finops-dev.sh"):
        assert "--clear-soft-delete" in Path("scripts/gcp", name).read_text()


def test_maintenance_failure_logs_location_without_error_payload(monkeypatch, capsys):
    from contextlib import nullcontext
    import json
    import pytest
    from ingestion_core import iceberg_maintenance as maintenance
    from ingestion_core import __main__ as runtime
    monkeypatch.setenv("CORE_BUCKET", "gen-lang-client-0593591102-dev-core")
    monkeypatch.setattr(runtime, "_iceberg_core", lambda _: SimpleNamespace(mutation_lock=nullcontext, close=lambda: None))
    def fail(**kwargs):
        raise RuntimeError("private credential fixture")
    monkeypatch.setattr(maintenance, "maintain_financials", fail)
    with pytest.raises(RuntimeError):
        maintenance.run("dry-run")
    output = capsys.readouterr().err
    assert "private credential fixture" not in output
    assert json.loads(output)["error_location"].startswith("test_data_retention.py:")


def test_metadata_deletion_readback_allows_new_metadata_to_increase_total(monkeypatch):
    from ingestion_core import iceberg_maintenance as maintenance
    prefix = "gs://dev/warehouse/report/metadata/"
    snapshot = SimpleNamespace(snapshot_id=1, summary={"total-records": "2"})
    table = SimpleNamespace(properties={maintenance.METADATA_HISTORY: "100"},
                            metadata_location=prefix + "current.metadata.json",
                            metadata=SimpleNamespace(metadata_log=[SimpleNamespace(metadata_file=prefix + "current.metadata.json")]),
                            current_snapshot=lambda: snapshot, snapshots=lambda: [snapshot],
                            scan=lambda **_: SimpleNamespace(to_arrow=lambda: None))
    items = [{"name": "warehouse/report/metadata/old.metadata.json", "size": "10", "generation": "1", "updated": "2026-09-01T00:00:00Z"}]
    def commit():
        table.metadata_location = prefix + "new.metadata.json"
        items.append({"name": "warehouse/report/metadata/new.metadata.json", "size": "100", "generation": "2", "updated": "2026-10-02T00:00:00Z"})
    table.transaction = lambda: SimpleNamespace(set_properties=lambda _: SimpleNamespace(commit_transaction=commit))
    core = SimpleNamespace(IDENTIFIERS=("report",), table_identifier=lambda _: "mart.report", catalog=SimpleNamespace(load_table=lambda _: table))
    def delete(name, generation):
        items[:] = [item for item in items if item["name"] != name]
    store = SimpleNamespace(bucket="dev", objects=lambda _: list(items), delete=delete)
    monkeypatch.setattr(maintenance, "_references", lambda *_: (set(), set()))
    monkeypatch.setattr(maintenance, "_keep_snapshots", lambda *_: {1})
    result = maintenance.maintain_financials(core=core, store=store, apply=True, identifier="mart.report",
                                           now=datetime(2026, 10, 2, tzinfo=timezone.utc))
    assert result["deleted_metadata_json"] == 1
    assert result["active_bytes_reclaimed"] == -90


def test_maintenance_accepts_existing_empty_table_without_current_snapshot(monkeypatch):
    from ingestion_core import iceberg_maintenance as maintenance
    table = SimpleNamespace(properties={maintenance.METADATA_HISTORY: "10"},
                            metadata_location="gs://dev/warehouse/empty/metadata/current.metadata.json",
                            metadata=SimpleNamespace(metadata_log=[]), current_snapshot=lambda: None, snapshots=lambda: [])
    core = SimpleNamespace(IDENTIFIERS=("empty",), table_identifier=lambda _: "mart.empty", catalog=SimpleNamespace(load_table=lambda _: table))
    monkeypatch.setattr(maintenance, "_references", lambda *_: (set(), set()))
    monkeypatch.setattr(maintenance, "_keep_snapshots", lambda *_: set())
    result = maintenance.maintain_financials(core=core, store=SimpleNamespace(bucket="dev", objects=lambda _: []),
                                           apply=True, identifier="mart.empty")
    assert result["row_count"] == 0 and result["expired_snapshots"] == 0


def test_mart_retention_uses_psycopg_database_option(monkeypatch):
    import pytest
    import psycopg
    from intelligence_mart import retention
    monkeypatch.setenv("MART_BUCKET", "gen-lang-client-0593591102-dev-mart")
    monkeypatch.setenv("MART_RETENTION_MODE", "dry-run")
    monkeypatch.setattr(retention, "load_postgres_bundle", lambda *_: None)
    monkeypatch.setattr(retention, "_settings", lambda _: {"host": "private", "name": "janus", "user": "worker", "password": "fixture"})
    monkeypatch.setattr(retention, "sql_catalog_from_environment", lambda: None)
    monkeypatch.setattr(retention, "MartMaintenanceStore", lambda *_: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(retention, "GcsObjectStore", lambda _: None)
    def connect(**kwargs):
        assert kwargs["dbname"] == "janus" and "name" not in kwargs
        raise RuntimeError("connection checked")
    monkeypatch.setattr(psycopg, "connect", connect)
    with pytest.raises(RuntimeError, match="connection checked"):
        retention.run()


def test_orphan_cleanup_reads_shared_manifest_once_and_protects_all_snapshots(monkeypatch):
    from ingestion_core import retention
    calls, deleted = [], []
    prefix = "gs://dev/warehouse/ohlcv_v1/"
    def manifest(name, data):
        return SimpleNamespace(manifest_path=prefix + name, fetch_manifest_entry=lambda *a, **k:
            calls.append(name) or [SimpleNamespace(data_file=SimpleNamespace(file_path=prefix + data))])
    shared = manifest("shared.avro", "old.parquet")
    recent = manifest("recent.avro", "new.parquet")
    snapshots = [SimpleNamespace(snapshot_id=1, manifest_list=prefix + "list1.avro", manifests=lambda _: [shared]),
                 SimpleNamespace(snapshot_id=2, manifest_list=prefix + "list2.avro", manifests=lambda _: [shared, recent])]
    table = SimpleNamespace(io=None, snapshots=lambda: snapshots, metadata_location="fixed")
    core = SimpleNamespace(catalog=SimpleNamespace(load_table=lambda _: table))
    store = SimpleNamespace(bucket="dev", objects=lambda _: [{"name": "warehouse/ohlcv_v1/" + name,
        "size": "10", "updated": "2026-09-01T00:00:00Z", "generation": "1"}
        for name in ("old.parquet", "new.parquet", "orphan.parquet")],
        delete=lambda name, generation: deleted.append(name))
    monkeypatch.setattr(retention, "_references", lambda *_: ({1}, set()))
    result = retention.clean_orphans(core, store, "core.ohlcv_v1", apply=True,
                                    now=datetime(2026, 10, 3, tzinfo=timezone.utc))
    assert calls == ["shared.avro", "recent.avro"]
    assert deleted == ["warehouse/ohlcv_v1/orphan.parquet"] and result["deleted_objects"] == 1


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


def test_stage_deletes_old_payload_metadata_and_quarantine_without_commit_requirement():
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
    assert planned["planned_bytes"] == 589 and planned["deleted_bytes"] == 0 and not deletes
    actual = clean_stage(store, apply=True, now=now)
    assert actual["deleted_bytes"] == 589 and actual["held_quarantine_objects"] == 0
    assert len(deletes) == 3


def test_stage_protects_active_execution_and_recent_unknown_payload():
    items = [{"name": "executions/live/stage/quarantine/old.json", "size": "3", "generation": "1", "updated": "2026-09-01T00:00:00Z"},
             {"name": "executions/unknown/stage/raw/recent.json", "size": "4", "generation": "2", "updated": "2026-10-01T00:00:00Z"},
             {"name": "executions/unknown/stage/raw/old.json", "size": "5", "generation": "3", "updated": "2026-09-01T00:00:00Z"}]
    deleted = []
    store = SimpleNamespace(bucket="dev", objects=lambda _: items, delete=lambda name, generation: deleted.append(name))
    result = clean_stage(store, apply=True, now=datetime(2026, 10, 2, tzinfo=timezone.utc), active_executions=frozenset({"live"}))
    assert deleted == [items[2]["name"]] and result["held_active_objects"] == 1


def test_core_manifest_cleanup_requires_fresh_fence_and_preserves_live_references():
    import json
    import pytest
    from ingestion_core.retention import clean_core_manifests
    items = [{"name": f"executions/{identity}/core-snapshot.json", "updated": "2026-01-01T00:00:00Z", "generation": "1"}
             for identity in ("unused", "report", "active")]
    deleted = []
    store = SimpleNamespace(objects=lambda _: items, delete=lambda name, generation: deleted.append(name),
        read=lambda name: json.dumps({"execution_id": name.split("/")[1], "snapshot_id": name.split("/")[1]}).encode())
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="one hour"):
        clean_core_manifests(store, {"created_at": "2026-10-01T00:00:00Z", "core_snapshot_ids": []},
                             apply=True, now=now, active_executions=frozenset())
    result = clean_core_manifests(store, {"created_at": now.isoformat(), "core_snapshot_ids": ["report"]},
                                 apply=True, now=now, active_executions=frozenset({"active"}))
    assert result["deleted_objects"] == 1 and deleted == [items[0]["name"]]


def test_three_generations_per_symbol_and_latest_oos_survive_repeated_cleanup():
    import json
    from hashlib import sha256
    from intelligence_mart.artifact_retention import clean_specialist_artifacts
    data, dates = {}, {}
    def put(name, value, updated="2026-09-01T00:00:00Z"):
        data[name] = json.dumps(value).encode()
        dates[name] = updated
        return {"artifact_uri": "gs://dev/" + name, "artifact_hash": "sha256:" + sha256(data[name]).hexdigest()}
    for i in range(5):
        refs = []
        for symbol in (["2330", "2327"] if i < 2 else ["2330"]):
            for role in ("fundamental", "valuation", "quant", "risk", "event"):
                ref = put(f"specialists/{symbol}-{role}-{i}.json", {"symbol": symbol, "role": role, "generation": i})
                refs.append({"symbol": symbol, "role": role, **ref})
        evaluation = put(f"executions/ex{i}/oos-evaluation.json", {"generation": i})
        put(f"executions/ex{i}/specialist-manifest.json", {"artifact_kind": "mart_specialist_execution_v1", "execution_id": f"ex{i}",
            "analysis_as_of": f"2026-09-0{i+1}", "core_snapshot_id": f"core{i}", "specialists": refs, "evaluation": evaluation})
    store = SimpleNamespace(bucket="dev", read=lambda name: data[name],
        objects=lambda _: [{"name": name, "updated": dates[name], "size": str(len(value)), "generation": "1"} for name, value in data.items()],
        delete=lambda name, generation: data.pop(name, None))
    def create(name, payload, content_type):
        if name in data:
            return False
        data[name], dates[name] = payload, "2026-10-02T00:00:00Z"
        return True
    store.create = create
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)
    before = dict(data)
    plan = clean_specialist_artifacts(store, apply=False, now=now)
    assert data == before and plan["retained_generations"] == {"2330": 3, "2327": 2}
    result = clean_specialist_artifacts(store, apply=True, now=now)
    assert result["deleted_objects"] > 0
    assert sum(name.startswith("specialists/2330-") for name in data) == 15
    assert sum(name.startswith("specialists/2327-") for name in data) == 10
    assert [name for name in data if name.endswith("/oos-evaluation.json")] == ["executions/ex4/oos-evaluation.json"]
    assert "executions/ex0/specialist-manifest.json" not in data
    assert "executions/ex0/specialist-retired.json" in data
    again = clean_specialist_artifacts(store, apply=True, now=now)
    assert again["deleted_objects"] == 0


def test_active_specialist_execution_protects_old_generation_and_oos():
    import json
    from hashlib import sha256
    from intelligence_mart.artifact_retention import clean_specialist_artifacts
    data = {}
    def put(name, value):
        data[name] = json.dumps(value).encode()
        return {"artifact_uri": "gs://dev/" + name,
                "artifact_hash": "sha256:" + sha256(data[name]).hexdigest()}
    for i in range(4):
        refs = [{"symbol": "2330", "role": role, **put(f"specialists/{role}-{i}.json", {"generation": i})}
                for role in ("fundamental", "valuation", "quant", "risk", "event")]
        evaluation = put(f"executions/ex{i}/oos-evaluation.json", {"generation": i})
        put(f"executions/ex{i}/specialist-manifest.json", {
            "artifact_kind": "mart_specialist_execution_v1", "execution_id": f"ex{i}",
            "analysis_as_of": f"2026-09-0{i+1}", "core_snapshot_id": f"core{i}",
            "specialists": refs, "evaluation": evaluation})
    def create(name, payload, _):
        if name in data:
            return False
        data[name] = payload
        return True
    store = SimpleNamespace(bucket="dev", read=lambda name: data[name], create=create,
        objects=lambda _: [{"name": name, "updated": "2026-09-01T00:00:00Z", "size": len(value), "generation": "1"}
                           for name, value in data.items()], delete=lambda name, generation: data.pop(name))
    result = clean_specialist_artifacts(store, apply=True, now=datetime(2026, 10, 3, tzinfo=timezone.utc),
                                       active_executions=frozenset({"ex0"}))
    assert result["core_snapshot_ids"] == ["core0", "core1", "core2", "core3"]
    assert "executions/ex0/specialist-manifest.json" in data
    assert "executions/ex0/oos-evaluation.json" in data
    assert "executions/ex0/specialist-retired.json" not in data
    assert sum(name.startswith("specialists/") for name in data) == 20
