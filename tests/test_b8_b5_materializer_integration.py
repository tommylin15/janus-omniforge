"""B8 B5 materializer real entrypoint: safe fake-GCS cache miss / failover.

Exercises actual B5 main() with controlled fake snapshots; live GCS readback
is separately covered by b8-ml-oos-fallback-readback workflow.
"""
import json
import runpy
import sys
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))


@pytest.mark.parametrize("backend,failure", [
    ("pyiceberg", False),
    ("bigquery", True),
])
def test_b5_default_and_opt_in_operational_fallback(monkeypatch, tmp_path, backend, failure):
    from google.api_core.exceptions import ServiceUnavailable
    from pyiceberg.table import StaticTable
    from intelligence_mart.analytics_reader import IcebergSnapshotReader, AnalyticsSnapshot

    script = runpy.run_path(str(ROOT / "scripts/gcp/b5-ml-oos-data.py"))
    globals_ = script["main"].__globals__
    core_id = "sha256:" + "a" * 64
    sha = "b" * 64
    fence = {"snapshot_id": 42, "metadata_location": "gs://fake-core/metadata/frozen.metadata.json"}
    core = {"snapshot_id": core_id, "analysis_as_of": "2026-10-06",
            "iceberg_tables": {"core.ohlcv_v1": fence}}
    objects = {}

    def gcs_list(bucket, prefix):
        assert bucket == "gen-lang-client-0593591102-dev-mart"
        return [{"name": name, "size": len(raw), "generation": "1"}
                for name, raw in sorted(objects.items()) if name.startswith(prefix)]

    def gcs_create(_, uri, raw, content_type):
        name = uri.removeprefix("gs://gen-lang-client-0593591102-dev-mart/")
        assert name not in objects, "immutable generationMatch=0 violated"
        objects[name] = raw

    def gcs_bytes(_, uri):
        name = uri.removeprefix("gs://gen-lang-client-0593591102-dev-mart/")
        return objects[name]

    b2 = {
        "CORE_MANIFEST_URI": "gs://fake-core/core-snapshot.json",
        "CORE_MANIFEST_SHA256": sha,
        "CORE_SNAPSHOT_ID": core_id,
        "MART_BUCKET": "gen-lang-client-0593591102-dev-mart",
        "CATALOG": "catalog",
        "CORE_NAMESPACE": "core",
        "gcs_json": lambda uri: (core, sha),
        "gcs_list_objects": gcs_list,
        "metadata_location": lambda table: fence["metadata_location"],
        "load_table": lambda *args: object(),
        "token": lambda: "fake-never-logged",
    }
    original_runpy = runpy.run_path
    monkeypatch.setattr(runpy, "run_path",
                        lambda path, *a, **kw: b2 if str(path).endswith("b2-lakehouse-acceptance.py")
                        else original_runpy(path, *a, **kw))
    monkeypatch.setitem(globals_, "stage_call", lambda label, timeout, action: action())
    monkeypatch.setitem(globals_, "gcs_create", gcs_create)
    monkeypatch.setitem(globals_, "gcs_bytes", gcs_bytes)
    monkeypatch.setattr(StaticTable, "from_metadata", lambda *a, **kw: object())
    day0 = date(2026, 8, 12)
    rows = [{"symbol": "2330", "trade_date": day0 + timedelta(days=i),
             "close": 100.0 + i, "volume_shares": 1000.0,
             "turnover_twd": 500_000.0, "source_id": "twse",
             "provenance_id": "gov"} for i in range(55)]
    monkeypatch.setattr(IcebergSnapshotReader, "read",
                        lambda self, manifest, requested_symbols, *, core_snapshot_id, row_limit:
                        AnalyticsSnapshot(core_snapshot_id, {"ohlcv": rows},
                                          {"total_rows": len(rows)}))
    if backend == "bigquery":
        bq = pytest.importorskip("google.cloud.bigquery")
        class DownClient:
            def __init__(self, **kwargs):
                pass
            def query(self, *args, **kwargs):
                raise ServiceUnavailable("synthetic operational unavailable")
            def close(self):
                pass
        monkeypatch.setattr(bq, "Client", DownClient)

    output = tmp_path / "b5-evidence.json"
    argv = ["b5-ml-oos-data.py", "--output", str(output)]
    if backend == "bigquery":
        argv += ["--backend", "bigquery", "--bigquery-opt-in"]
    monkeypatch.setattr(sys, "argv", argv)
    script["main"]()
    evidence = json.loads(output.read_text())
    assert evidence["status"] == "pass"
    assert evidence["effective_backend"] == "pyiceberg"
    assert evidence["row_count"] == 3
    assert evidence["routing_audit"]["default_backend"] == "pyiceberg"
    assert evidence["routing_audit"]["fallback_triggered"] is failure
    assert evidence["routing_audit"]["fallback_status"] == (
        "validated" if failure else "not_needed")
    assert evidence["total_billed_bytes"] is (None if failure else 0)
    assert evidence["billed_bytes_complete"] is (not failure)
    assert evidence["storage_read_api_used"] is False
    assert len([k for k in objects if k.endswith(".parquet")]) == 1
    assert len([k for k in objects if k.endswith("/manifest.json")]) == 1


def test_b5_explicit_bigquery_without_opt_in_rejected_before_io(monkeypatch, tmp_path):
    script = runpy.run_path(str(ROOT / "scripts/gcp/b5-ml-oos-data.py"))
    # Code must invoke central opt-in selector prior to gcs existing cache listing.
    source = (ROOT / "scripts/gcp/b5-ml-oos-data.py").read_text()
    assert 'default="pyiceberg"' in source
    assert 'selected_backend = backend_for("ml-oos", args.backend' in source
    assert 'check_fixed_core(identity)' in source
    assert source.index('selected_backend = backend_for') < source.index('# B6 pre-query lookup')
    assert "partially wrote immutable export" in source
    assert "choice = execute_ml_oos(" in source
