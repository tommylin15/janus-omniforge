import json
import sys
from datetime import date
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "jobs/intelligence-mart"))

from intelligence_mart.ml_oos_data import (
    DATASET_SCHEMA_VERSION,
    QUERY_CONTRACT_VERSION,
    dataset_content_hash,
    inspect_dataset,
)


class Store:
    bucket = "mart"

    def __init__(self):
        self.data = {}

    def read(self, name):
        if name not in self.data:
            raise FileNotFoundError(name)
        return self.data[name]


def parquet_bytes(**overrides):
    row = {
        "symbol": "2330",
        "trade_date": date(2026, 8, 3),
        "return_5d": 0.01,
        "return_20d": 0.03,
        "log_turnover_twd": 18.0,
        "volume_shares": 1000000.0,
        "label_return_20d": 0.05,
        "label_maturity_date": date(2026, 8, 31),
        "source_id": "twse",
        "provenance_id": "prov-1",
        "core_snapshot_id": "sha256:core",
        "analysis_as_of": "2026-10-06",
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "feature_version": "2",
        "model_version": "deterministic-v1",
    }
    row.update(overrides)
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist([row]), sink)
    return sink.getvalue().to_pybytes()


def manifest_for(raw, **changes):
    identity = {
        "core_snapshot_id": "sha256:core",
        "core_manifest_sha256": "sha256:manifest",
        "analysis_as_of": "2026-10-06",
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "feature_version": "2",
        "model_version": "deterministic-v1",
        "source_tables": {
            "core.ohlcv_v1": {
                "snapshot_id": 42,
                "metadata_location": "gs://core/warehouse/ohlcv/metadata/00001-x.metadata.json",
            }
        },
        "date_bounds": ["2026-02-07", "2026-10-06"],
        "label_horizon_trading_days": 20,
        "cohort_stride_trading_days": 5,
    }
    shard = {
        "uri": "gs://mart/ml-oos-data/v1/abc/part-000.parquet",
        "sha256": "sha256:" + sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    manifest = {
        "artifact_kind": "mart_ml_oos_dataset_v1",
        "schema_version": "1.0.0",
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "dataset_prefix": "gs://mart/ml-oos-data/v1/abc/",
        "core_snapshot_id": identity["core_snapshot_id"],
        "analysis_as_of": identity["analysis_as_of"],
        "feature_version": identity["feature_version"],
        "model_version": identity["model_version"],
        "identity": identity,
        "parquet_shards": [shard],
        "row_count": 1,
        "export_bytes": len(raw),
        "storage_read_api_used": False,
        "retention": {
            "policy": "latest-referenced-oos-or-7d-unreferenced",
            "reference_protected": True,
        },
    }
    manifest["dataset_content_hash"] = dataset_content_hash(identity, manifest["parquet_shards"])
    manifest.update(changes)
    return manifest


def test_b5_parquet_readback_preserves_lineage_without_pandas():
    store = Store()
    raw = parquet_bytes()
    store.data["ml-oos-data/v1/abc/part-000.parquet"] = raw
    result = inspect_dataset(manifest_for(raw), store)
    assert result["row_count"] == 1
    assert result["symbol_count"] == 1
    assert result["analysis_as_of"] == "2026-10-06"
    assert result["storage_read_api_used"] is False


def test_b5_rejects_tampered_shard_before_acceptance():
    store = Store()
    raw = parquet_bytes()
    store.data["ml-oos-data/v1/abc/part-000.parquet"] = raw + b"x"
    with pytest.raises(RuntimeError, match="hash/size"):
        inspect_dataset(manifest_for(raw), store)


@pytest.mark.parametrize(
    "override,error",
    [
        ({"core_snapshot_id": "sha256:other"}, "lineage"),
        ({"label_maturity_date": date(2026, 10, 7)}, "maturity"),
    ],
)
def test_b5_rejects_lineage_or_future_label(override, error):
    store = Store()
    raw = parquet_bytes(**override)
    store.data["ml-oos-data/v1/abc/part-000.parquet"] = raw
    with pytest.raises((RuntimeError, ValueError), match=error):
        inspect_dataset(manifest_for(raw), store)


def test_b5_rejects_private_fields_and_manifest_identity_tampering():
    store = Store()
    raw = parquet_bytes(owner_id="private-owner")
    store.data["ml-oos-data/v1/abc/part-000.parquet"] = raw
    with pytest.raises(ValueError, match="private"):
        inspect_dataset(manifest_for(raw), store)

    raw = parquet_bytes()
    store.data["ml-oos-data/v1/abc/part-000.parquet"] = raw
    manifest = manifest_for(raw)
    manifest["identity"]["feature_version"] = "changed"
    with pytest.raises(ValueError, match="lineage"):
        inspect_dataset(manifest, store)


def test_b5_hash_is_order_stable_and_bound_to_identity():
    identity = manifest_for(parquet_bytes())["identity"]
    shards = [
        {"uri": "gs://mart/ml-oos-data/v1/abc/b.parquet", "sha256": "sha256:b", "size_bytes": 2},
        {"uri": "gs://mart/ml-oos-data/v1/abc/a.parquet", "sha256": "sha256:a", "size_bytes": 1},
    ]
    assert dataset_content_hash(identity, shards) == dataset_content_hash(identity, list(reversed(shards)))
    changed = dict(identity, model_version="other")
    assert dataset_content_hash(identity, shards) != dataset_content_hash(changed, shards)


def test_b5_bigquery_reduction_is_column_date_and_label_bounded():
    import runpy
    script = runpy.run_path(str(ROOT / "scripts/gcp/b5-ml-oos-data.py"))
    sql = script["reduction_select"](
        "`project.catalog.ns.ohlcv_v1`",
        start=date(2026, 2, 7),
        end=date(2026, 10, 6),
        core_snapshot_id="sha256:core",
    )
    assert "SELECT *" not in sql
    assert "BETWEEN DATE '2026-02-07' AND DATE '2026-10-06'" in sql
    assert "LEAD(" in sql and "label_maturity_date <= DATE '2026-10-06'" in sql
    assert "MOD(sample_ordinal - 1, 5) = 0" in sql
    assert "user_id" not in sql and "owner_id" not in sql


def test_b5_retention_keeps_latest_dataset_and_expires_old_unreferenced():
    from datetime import datetime, timezone
    from intelligence_mart.artifact_retention import clean_specialist_artifacts

    old_manifest = {
        "artifact_kind": "mart_ml_oos_dataset_v1",
        "analysis_as_of": "2026-09-01",
        "parquet_shards": [
            {"uri": "gs://mart/ml-oos-data/v1/old/part-000.parquet", "sha256": "sha256:old", "size_bytes": 3}
        ],
    }
    new_manifest = {
        "artifact_kind": "mart_ml_oos_dataset_v1",
        "analysis_as_of": "2026-10-01",
        "parquet_shards": [
            {"uri": "gs://mart/ml-oos-data/v1/new/part-000.parquet", "sha256": "sha256:new", "size_bytes": 3}
        ],
    }
    raw = {
        "ml-oos-data/v1/old/manifest.json": json.dumps(old_manifest).encode(),
        "ml-oos-data/v1/old/part-000.parquet": b"old",
        "ml-oos-data/v1/new/manifest.json": json.dumps(new_manifest).encode(),
        "ml-oos-data/v1/new/part-000.parquet": b"new",
        "ml-oos-data/v1/partial/part-000.parquet": b"partial",
    }
    meta = {
        name: {
            "name": name,
            "size": str(len(value)),
            "updated": "2026-09-01T00:00:00Z" if "/old/" in name or "/partial/" in name
                       else "2026-10-06T00:00:00Z",
            "generation": "1",
        }
        for name, value in raw.items()
    }

    class RetentionStore:
        bucket = "mart"
        def objects(self, prefix):
            return tuple(value for name, value in meta.items() if name.startswith(prefix))
        def read(self, name):
            return raw[name]
        def create(self, name, payload, content_type):
            raw[name] = payload
            return True
        def delete(self, name, generation=None):
            raw.pop(name, None)

    result = clean_specialist_artifacts(
        RetentionStore(), apply=False, now=datetime(2026, 10, 7, tzinfo=timezone.utc)
    )
    assert result["retained_ml_oos_datasets"] == 1
    assert result["planned_objects"] == 3
