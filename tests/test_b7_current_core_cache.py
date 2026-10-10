"""B7 current-source cache refresh: source-fence and monthly reference guards.

No GCS credentials, model fitting, Cloud Run execution or BigQuery calls.
"""
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import json
import runpy
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
b7 = runpy.run_path(str(ROOT / "scripts/gcp/b7-refresh-derived-cache.py"))
CORE_BUCKET = b7["CORE_BUCKET"]
MART_BUCKET = b7["MART_BUCKET"]


class FakeGcs:
    def __init__(self):
        self.today = datetime.now(ZoneInfo("Asia/Taipei")).date()
        self.analysis = self.today.isoformat()
        self.snapshot = "sha256:" + "a" * 64
        self.fence = {"snapshot_id": 1234,
                      "metadata_location": f"gs://{CORE_BUCKET}/warehouse/core/metadata/m.json"}
        self.core = {"execution_id": "live-test", "snapshot_id": self.snapshot,
                     "analysis_as_of": self.analysis,
                     "iceberg_tables": {"core.ohlcv_v1": self.fence}}
        self.path = f"executions/{self.core['execution_id']}/core-snapshot.json"
        self.uri = f"gs://{CORE_BUCKET}/{self.path}"
        self.objects = {
            CORE_BUCKET: [{"name": self.path, "updated": "2026-10-10T04:00:00Z"}],
            MART_BUCKET: [],
        }
        self.contents = {
            self.uri: self.core,
            self.fence["metadata_location"]: {"current-snapshot-id": 1234, "format-version": 2},
        }

    def list(self, bucket, prefix):
        return [x for x in self.objects[bucket] if x["name"].startswith(prefix)]

    def get(self, uri):
        value = self.contents[uri]
        return value, sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def adapter(self):
        return {"gcs_list_objects": self.list, "gcs_json": self.get}


def test_b7_selects_latest_real_core_by_immutable_manifest_and_snapshot():
    fake = FakeGcs()
    got = b7["core_latest"](fake.adapter())
    assert got["core"]["snapshot_id"] == fake.snapshot
    assert got["fence"] == fake.fence
    assert got["sha256"].startswith("sha256:")
    b7["unchanged_source"](fake.adapter(), got)


def test_b7_rejects_invalid_snapshot_metadata_and_stale_core():
    fake = FakeGcs()
    fake.contents[fake.fence["metadata_location"]]["current-snapshot-id"] = 9999
    with pytest.raises(RuntimeError, match="metadata/snapshot mismatch"):
        b7["core_latest"](fake.adapter())
    fake = FakeGcs()
    fake.core["analysis_as_of"] = (fake.today - timedelta(days=8)).isoformat()
    with pytest.raises(RuntimeError, match="7-day freshness"):
        b7["core_latest"](fake.adapter())


def test_b7_detects_concurrent_core_advance_without_promoting_old_data():
    fake = FakeGcs()
    pinned = b7["core_latest"](fake.adapter())
    fake.objects[CORE_BUCKET].append({
        "name": "executions/newer/core-snapshot.json", "updated": "2026-10-11T00:00:00Z"})
    new_uri = f"gs://{CORE_BUCKET}/executions/newer/core-snapshot.json"
    fake.contents[new_uri] = dict(fake.core, execution_id="newer")
    with pytest.raises(RuntimeError, match="Core changed during cache refresh"):
        b7["unchanged_source"](fake.adapter(), pinned)


def test_b7_only_reuses_same_core_existing_monthly_reconciliation():
    fake = FakeGcs()
    pinned = b7["core_latest"](fake.adapter())
    mart_name = "executions/monthly-01/specialist-manifest.json"
    target_uri = f"gs://{MART_BUCKET}/executions/monthly-01/target-snapshot.json"
    fake.objects[MART_BUCKET] = [{"name": mart_name, "updated": "2026-10-10T05:00:00Z"}]
    fake.contents[target_uri] = {"symbols": ["2330"]}
    monthly_uri = f"gs://{MART_BUCKET}/{mart_name}"
    fake.contents[monthly_uri] = {
        "artifact_kind": "mart_specialist_execution_v1",
        "core_snapshot_id": fake.snapshot, "execution_id": "monthly-01",
        "reconciliation": {"artifact_uri": "gs://example/monthly-reconciliation.json"},
        "evaluation": {"artifact_uri": "gs://example/oos-evaluation.json"},
        "target_snapshot": {"artifact_uri": target_uri,
                            "artifact_hash": "sha256:" + fake.get(target_uri)[1]},
        "llm_api_tokens": 0, "ceo_triggered": False,
    }
    manifest, symbols, uri = b7["load_monthly_evidence"](fake.adapter(), pinned)
    assert manifest["execution_id"] == "monthly-01"
    assert symbols == ["2330"] and uri == monthly_uri
    fake.contents[monthly_uri]["core_snapshot_id"] = "sha256:" + "b" * 64
    with pytest.raises(RuntimeError, match="monthly specialist evidence for current Core missing"):
        b7["load_monthly_evidence"](fake.adapter(), pinned)


def test_b7_rejects_changed_immutable_target_hash():
    fake = FakeGcs()
    pinned = b7["core_latest"](fake.adapter())
    mart_name = "executions/monthly-01/specialist-manifest.json"
    uri = f"gs://{MART_BUCKET}/{mart_name}"
    fake.objects[MART_BUCKET] = [{"name": mart_name, "updated": "2026-10-10T05:00:00Z"}]
    fake.contents[uri] = {
        "artifact_kind": "mart_specialist_execution_v1", "core_snapshot_id": fake.snapshot,
        "reconciliation": {"artifact_uri": "gs://example/receipt"},
        "evaluation": {"artifact_uri": "gs://example/evaluation"},
        "target_snapshot": {"artifact_uri": f"gs://{MART_BUCKET}/executions/monthly-01/target.json",
                            "artifact_hash": "sha256:bad"},
        "llm_api_tokens": 0, "ceo_triggered": False,
    }
    fake.contents[fake.contents[uri]["target_snapshot"]["artifact_uri"]] = {"symbols": ["2330"]}
    with pytest.raises(RuntimeError, match="target hash mismatch"):
        b7["load_monthly_evidence"](fake.adapter(), pinned)


def test_b7_does_not_require_bigquery_or_retraining_in_refresh_script():
    source = (ROOT / "scripts/gcp/b7-refresh-derived-cache.py").read_text()
    assert "StaticTable.from_metadata" in source
    assert "reconcile_monthly_cache(" in source
    assert "b6_dependency_key" in source
    assert "unchanged_source(b2, pinned)" in source
    assert "MART_OPERATION" not in source and "execute_job" not in source
    assert "BigQuery" not in source and "bigquery.Client" not in source
    assert "delete(" not in source and "champion_promotion" in source


def test_b7_receipt_writer_keeps_b5_writer_scope_unchanged(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False

    monkeypatch.setattr(b7["urllib"].request, "urlopen",
                        lambda request, timeout: calls.append((request, timeout)) or Response())
    adapter = {"token": lambda: "synthetic-not-logged"}
    permitted = f"gs://{MART_BUCKET}/acceptance/b7-cache-freshness/" + "a" * 64 + ".json"
    b7["gcs_create_b7_receipt"](adapter, permitted, b"{}")
    assert len(calls) == 1 and calls[0][0].method == "POST"
    assert "ifGenerationMatch=0" in calls[0][0].full_url
    for rejected in (
        f"gs://{MART_BUCKET}/ml-oos-data/v1/" + "a" * 64 + ".json",
        "gs://other-bucket/acceptance/b7-cache-freshness/" + "a" * 64 + ".json",
        f"gs://{MART_BUCKET}/acceptance/b7-cache-freshness/wrong.json",
    ):
        with pytest.raises(RuntimeError, match="outside immutable acceptance prefix"):
            b7["gcs_create_b7_receipt"](adapter, rejected, b"{}")
    assert len(calls) == 1
