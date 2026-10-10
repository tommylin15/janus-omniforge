#!/usr/bin/env python3
"""Refresh B7 ML/OOS derived cache from the latest immutable Core, without retraining.

Uses the existing B5/B6 immutable schema and B7 monthly specialist references.
Never writes Core, changes champion, invokes CEO, or edits the original monthly
reconciliation. A new separate, source-pinned acceptance receipt is issued only
when the refreshed dataset and all monthly specialist pointers reconcile.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import runpy
import sys
import urllib.parse
import urllib.request
from time import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "jobs/intelligence-mart")]
CORE_BUCKET = "gen-lang-client-0593591102-dev-core"
MART_BUCKET = "gen-lang-client-0593591102-dev-mart"
SOURCE = "core.ohlcv_v1"
MAX_INVENTORY = 12000
B7_RECEIPT_PREFIX = "acceptance/b7-cache-freshness/"


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def core_latest(b2):
    """Recheck the exact latest Core object, raw hash, date and Iceberg metadata."""
    objects = b2["gcs_list_objects"](CORE_BUCKET, "executions/")
    require(len(objects) <= MAX_INVENTORY, "B7 Core inventory exceeds safety bound")
    candidates = [o for o in objects if o["name"].endswith("/core-snapshot.json")]
    require(bool(candidates), "B7 no immutable Core snapshot")
    newest = max(candidates, key=lambda o: (o.get("updated", ""), o["name"]))
    uri = f"gs://{CORE_BUCKET}/{newest['name']}"
    core, digest = b2["gcs_json"](uri)
    require(newest["name"] == f"executions/{core.get('execution_id')}/core-snapshot.json",
            "B7 latest Core path/execution mismatch")
    require(str(core.get("snapshot_id", "")).startswith("sha256:"),
            "B7 latest Core snapshot identity missing")
    as_of = date.fromisoformat(str(core["analysis_as_of"]))
    age = (datetime.now(ZoneInfo("Asia/Taipei")).date() - as_of).days
    require(0 <= age <= 7, "B7 latest Core outside approved 7-day freshness")
    fence = core.get("iceberg_tables", {}).get(SOURCE, {})
    metadata_uri = str(fence.get("metadata_location", ""))
    require(metadata_uri.startswith(f"gs://{CORE_BUCKET}/"),
            "B7 Core OHLCV metadata is outside canonical bucket")
    require(isinstance(fence.get("snapshot_id"), int) and fence["snapshot_id"] > 0,
            "B7 Core OHLCV snapshot ID missing")
    metadata, _ = b2["gcs_json"](metadata_uri)
    require(metadata.get("current-snapshot-id") == fence["snapshot_id"]
            and metadata.get("format-version") == 2,
            "B7 pinned OHLCV Iceberg metadata/snapshot mismatch")
    return {"uri": uri, "sha256": "sha256:" + digest, "core": core, "fence": fence}


def unchanged_source(b2, pinned):
    current = core_latest(b2)
    require(current["uri"] == pinned["uri"]
            and current["sha256"] == pinned["sha256"]
            and current["core"]["snapshot_id"] == pinned["core"]["snapshot_id"]
            and current["fence"] == pinned["fence"],
            "B7 Core changed during cache refresh; refuse current publication")


def load_monthly_evidence(b2, pinned):
    """Reuse the existing B7 monthly execution; never dispatch or retrain it."""
    entries = b2["gcs_list_objects"](MART_BUCKET, "executions/")
    require(len(entries) <= MAX_INVENTORY, "B7 Mart inventory exceeds safety bound")
    manifests = sorted((o for o in entries if o["name"].endswith("/specialist-manifest.json")),
                       key=lambda o: (o.get("updated", ""), o["name"]), reverse=True)
    require(len(manifests) <= 256, "B7 specialist manifest inventory exceeds bound")
    for item in manifests:
        uri = f"gs://{MART_BUCKET}/{item['name']}"
        value, _ = b2["gcs_json"](uri)
        if value.get("core_snapshot_id") != pinned["core"]["snapshot_id"] or not value.get("reconciliation"):
            continue
        require(value.get("artifact_kind") == "mart_specialist_execution_v1"
                and value.get("llm_api_tokens") == 0 and value.get("ceo_triggered") is False,
                "B7 monthly manifest safety contract mismatch")
        require(bool(value.get("evaluation")), "B7 monthly OOS reference missing")
        targets = value.get("target_snapshot", {})
        require(str(targets.get("artifact_uri", "")).startswith(f"gs://{MART_BUCKET}/executions/"),
                "B7 monthly target reference invalid")
        target, rawhash = b2["gcs_json"](targets["artifact_uri"])
        require("sha256:" + rawhash == targets.get("artifact_hash"),
                "B7 immutable monthly target hash mismatch")
        require(bool(target.get("symbols")), "B7 monthly target empty")
        return value, target["symbols"], uri
    raise RuntimeError("B7 monthly specialist evidence for current Core missing; do not retrain")


def gcs_create_b7_receipt(b2, uri: str, payload: bytes) -> None:
    """Create-only acceptance receipt with its own narrow write allowlist.

    Do not relax B5's ml-oos-data/v1 writer or permit arbitrary GCS writes.
    """
    parsed = urllib.parse.urlparse(uri)
    name = parsed.path.lstrip("/")
    suffix = name.removeprefix(B7_RECEIPT_PREFIX)
    require(parsed.scheme == "gs" and parsed.netloc == MART_BUCKET
            and name.startswith(B7_RECEIPT_PREFIX)
            and len(suffix) == 69 and suffix.endswith(".json")
            and all(ch in "0123456789abcdef" for ch in suffix[:-5]),
            "B7 receipt URI outside immutable acceptance prefix")
    endpoint = (
        "https://storage.googleapis.com/upload/storage/v1/b/"
        f"{urllib.parse.quote(MART_BUCKET, safe='')}/o?uploadType=media"
        "&ifGenerationMatch=0&name="
        f"{urllib.parse.quote(name, safe='')}"
    )
    request = urllib.request.Request(
        endpoint, data=payload, method="POST",
        headers={"Authorization": f"Bearer {b2['token']()}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=65):
        pass


class ExistingGcsStore:
    """WIF-compatible GCS reader for original B7 reconciliation/Parquet validator."""
    def __init__(self, b2, b5):
        self.b2, self.b5, self.bucket = b2, b5, MART_BUCKET

    def read(self, name):
        return self.b5["gcs_bytes"](self.b2, f"gs://{self.bucket}/{name}")

    def list(self, prefix):
        return tuple(o["name"] for o in self.b2["gcs_list_objects"](self.bucket, prefix))

    def objects(self, prefix):
        return tuple(self.b2["gcs_list_objects"](self.bucket, prefix))


def refresh(b2, b5, *, output: Path):
    from datetime import timedelta
    from intelligence_mart.analytics_reader import IcebergSnapshotReader
    from intelligence_mart.ml_oos_data import (
        DATASET_SCHEMA_VERSION, QUERY_CONTRACT_VERSION, dataset_content_hash,
        inspect_dataset,
    )
    from intelligence_mart.monthly_reconciliation import reconcile_monthly_cache
    from pyiceberg.table import StaticTable
    import pyarrow as pa
    import pyarrow.parquet as pq

    pinned = core_latest(b2)
    core, fence = pinned["core"], pinned["fence"]
    monthly, target_symbols, monthly_uri = load_monthly_evidence(b2, pinned)
    require(len(monthly.get("specialists", [])) == len(target_symbols) * 5,
            "B7 monthly specialist coverage not complete")
    start = date.fromisoformat(core["analysis_as_of"]) - timedelta(days=b5["LOOKBACK_CALENDAR_DAYS"])
    identity = {
        "core_snapshot_id": core["snapshot_id"],
        "core_manifest_sha256": pinned["sha256"],
        "analysis_as_of": core["analysis_as_of"],
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "feature_version": b5["FEATURE_VERSION"],
        "model_version": b5["MODEL_VERSION"],
        "source_tables": {SOURCE: {
            "snapshot_id": fence["snapshot_id"],
            "metadata_location": fence["metadata_location"],
        }},
        "date_bounds": [start.isoformat(), core["analysis_as_of"]],
        "label_horizon_trading_days": b5["LABEL_HORIZON"],
        "cohort_stride_trading_days": b5["COHORT_STRIDE"],
    }
    key = b5["b6_dependency_key"](identity)
    prefix = "ml-oos-data/v1/" + sha256(canonical(identity)).hexdigest() + "/"
    uri = f"gs://{MART_BUCKET}/{prefix}manifest.json"
    store = ExistingGcsStore(b2, b5)
    objects = b2["gcs_list_objects"](MART_BUCKET, prefix)
    manifests = [obj for obj in objects if obj["name"] == prefix + "manifest.json"]
    require(not objects or len(manifests) == 1,
            "B7 partial immutable cache exists; refuse overwrite")
    reused = bool(manifests)
    if reused:
        manifest, _ = b2["gcs_json"](uri)
        require(manifest.get("identity") == identity, "B7 cache identity collision")
        b5["b6_validate_hit"](manifest, uri, MART_BUCKET,
                              lambda shard_uri: b5["gcs_bytes"](b2, shard_uri))
        inspected = inspect_dataset(manifest, store)
    else:
        unchanged_source(b2, pinned)
        props = {"gcs.oauth2.token": b2["token"](),
                 "gcs.oauth2.token-expires-at": str(int((time() + 3000) * 1000))}
        table = StaticTable.from_metadata(fence["metadata_location"], properties=props)
        catalog = type("PinnedCatalog", (), {"load_table": lambda self, _: table})()
        scan = IcebergSnapshotReader(
            catalog, date_bounds={SOURCE: ("trade_date", *identity["date_bounds"])},
            selected_fields={SOURCE: ("symbol", "trade_date", "close", "volume_shares",
                                      "turnover_twd", "source_id", "provenance_id")},
        ).read(dict(core, iceberg_tables={SOURCE: fence}), tuple(),
               core_snapshot_id=core["snapshot_id"], row_limit=250_000)
        reducer = runpy.run_path(str(ROOT / "scripts/gcp/b8-matched-ml-oos.py"))["reduce_ohlcv"]
        rows = reducer(scan.datasets["ohlcv"], identity)
        require(0 < len(rows) <= 500000, "B7 current derived dataset empty/oversized")
        buffer = pa.BufferOutputStream()
        pq.write_table(pa.Table.from_pylist(rows), buffer, compression="snappy")
        raw = buffer.getvalue().to_pybytes()
        require(0 < len(raw) <= 512 * 1024 * 1024, "B7 current Parquet exceeds byte bound")
        shard_uri = f"gs://{MART_BUCKET}/{prefix}part-00000.parquet"
        shards = [{"uri": shard_uri, "sha256": "sha256:" + sha256(raw).hexdigest(),
                   "size_bytes": len(raw)}]
        manifest = {
            "artifact_kind": "mart_ml_oos_dataset_v1", "schema_version": "1.0.0",
            "dataset_schema_version": DATASET_SCHEMA_VERSION,
            "query_contract_version": QUERY_CONTRACT_VERSION,
            "dataset_prefix": f"gs://{MART_BUCKET}/{prefix}",
            "core_snapshot_id": core["snapshot_id"],
            "analysis_as_of": core["analysis_as_of"],
            "feature_version": b5["FEATURE_VERSION"],
            "model_version": b5["MODEL_VERSION"],
            "identity": identity, "parquet_shards": shards,
            "row_count": len(rows), "export_bytes": len(raw),
            "dataset_content_hash": dataset_content_hash(identity, shards),
            "derived_cache": {"contract_version": "b6-ml-oos-dirty-v1",
                              "dependency_cache_key": key,
                              "source_dependencies": [SOURCE]},
            "query": {"backend": "pyiceberg", "jobs": [], "total_billed_bytes": 0,
                      "billed_bytes_complete": True, "storage_read_api_used": False},
            "storage_read_api_used": False, "canonical_write": False,
            "provenance": {"core_manifest_uri": pinned["uri"],
                           "core_manifest_sha256": pinned["sha256"],
                           "source_tables": identity["source_tables"]},
            "retention": {"policy": "latest-referenced-oos-or-7d-unreferenced",
                          "reference_protected": True, "canonical": False},
        }
        draft = type("DraftStore", (), {
            "bucket": MART_BUCKET,
            "read": lambda self, name: raw if name == prefix + "part-00000.parquet"
                    else (_ for _ in ()).throw(FileNotFoundError(name)),
        })()
        inspect_dataset(manifest, draft)
        unchanged_source(b2, pinned)
        b5["gcs_create"](b2, shard_uri, raw, "application/octet-stream")
        require(b5["gcs_bytes"](b2, shard_uri) == raw, "B7 written Parquet readback mismatch")
        unchanged_source(b2, pinned)
        payload = json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n"
        b5["gcs_create"](b2, uri, payload, "application/json")
        require(b5["gcs_bytes"](b2, uri) == payload, "B7 manifest readback mismatch")
        inspected = inspect_dataset(manifest, store)

    unchanged_source(b2, pinned)
    reconciliation = reconcile_monthly_cache(
        store, MART_BUCKET, target_symbols, monthly["specialists"],
        core["snapshot_id"], core_manifest=core)
    require(reconciliation["status"] == "pass"
            and reconciliation["ml_oos_derived_cache"]["status"] == "current"
            and reconciliation["ml_oos_derived_cache"]["core_identity_relation"] == "exact-core"
            and reconciliation["ml_oos_derived_cache"]["manifest_uri"] == uri
            and reconciliation["missed_invalidation_detected"] is False
            and reconciliation["champion_promotion"] is False
            and reconciliation["llm_api_tokens"] == 0,
            "B7 refreshed current-Core reconciliation not PASS")
    require(inspected["core_snapshot_id"] == core["snapshot_id"]
            and inspected["row_count"] == manifest["row_count"],
            "B7 source-pinned ML/OOS readback mismatch")
    unchanged_source(b2, pinned)
    receipt = {
        "artifact_kind": "b7_current_source_derived_cache_freshness_v1",
        "status": "pass", "core_snapshot_id": core["snapshot_id"],
        "core_manifest_uri": pinned["uri"], "core_manifest_sha256": pinned["sha256"],
        "monthly_specialist_manifest_uri": monthly_uri,
        "monthly_execution_id": monthly["execution_id"],
        "monthly_original_reconciliation_status": monthly.get("reconciliation_status"),
        "new_reconciliation": reconciliation,
        "dataset_manifest_uri": uri,
        "dataset_manifest_sha256": "sha256:" + sha256(b5["gcs_bytes"](b2, uri)).hexdigest(),
        "dataset_content_hash": manifest["dataset_content_hash"],
        "row_count": manifest["row_count"], "export_bytes": inspected["export_bytes"],
        "derived_cache_reused": reused,
        "ml_retraining_triggered": False, "bigquery_jobs": [],
        "bigquery_storage_read_api_used": False, "canonical_write": False,
        "champion_promotion": False, "llm_api_tokens": 0, "ceo_triggered": False,
    }
    # Separate immutable acceptance evidence. Never alter the original monthly receipt.
    name = B7_RECEIPT_PREFIX + sha256(canonical({
        "core": pinned["sha256"], "dataset": receipt["dataset_manifest_sha256"],
        "monthly": monthly_uri,
    })).hexdigest() + ".json"
    receipt["receipt_uri"] = f"gs://{MART_BUCKET}/{name}"
    payload = json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n"
    if any(o["name"] == name for o in b2["gcs_list_objects"](MART_BUCKET, B7_RECEIPT_PREFIX)):
        require(b5["gcs_bytes"](b2, receipt["receipt_uri"]) == payload,
                "B7 prior immutable receipt conflict")
    else:
        gcs_create_b7_receipt(b2, receipt["receipt_uri"], payload)
    require(b5["gcs_bytes"](b2, receipt["receipt_uri"]) == payload,
            "B7 immutable acceptance receipt readback mismatch")
    unchanged_source(b2, pinned)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": "pass", "row_count": receipt["row_count"],
        "core_snapshot_id": core["snapshot_id"],
        "dataset_manifest_uri": uri, "receipt_uri": receipt["receipt_uri"],
        "reconciliation_status": "pass", "retrained": False,
        "reused": reused,
    }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Reuse approved GCS access and exact B5/B6 schema; no BQ catalog registration.
    b2 = runpy.run_path(str(ROOT / "scripts/gcp/b2-lakehouse-acceptance.py"))
    b5 = runpy.run_path(str(ROOT / "scripts/gcp/b5-ml-oos-data.py"))
    refresh(b2, b5, output=args.output)


if __name__ == "__main__":
    main()
