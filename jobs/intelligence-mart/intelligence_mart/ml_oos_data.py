"""Versioned ML/OOS Parquet dataset readback for the Intelligence Mart."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import os
from urllib.parse import urlparse


ARTIFACT_KIND = "mart_ml_oos_dataset_v1"
DATASET_SCHEMA_VERSION = "b5-ml-oos-v1"
QUERY_CONTRACT_VERSION = "b5-sql-reduction-v1"
REQUIRED_COLUMNS = {
    "symbol",
    "trade_date",
    "return_5d",
    "return_20d",
    "log_turnover_twd",
    "volume_shares",
    "label_return_20d",
    "label_maturity_date",
    "source_id",
    "provenance_id",
    "core_snapshot_id",
    "analysis_as_of",
    "dataset_schema_version",
    "query_contract_version",
    "feature_version",
    "model_version",
}
FORBIDDEN_COLUMNS = {
    "user_id", "owner_id", "account_id", "cost_basis", "cost", "pnl",
    "unrealized_pnl", "realized_pnl", "quantity", "shares_held",
}
MAX_SHARDS = 64
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ROWS = 500_000


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def dataset_content_hash(identity: dict, shards: list[dict]) -> str:
    """Hash the immutable dataset identity and exact Parquet object digests."""
    normalized = [
        {
            "uri": str(item["uri"]),
            "sha256": str(item["sha256"]),
            "size_bytes": int(item["size_bytes"]),
        }
        for item in sorted(shards, key=lambda value: str(value["uri"]))
    ]
    return "sha256:" + sha256(_canonical({"identity": identity, "shards": normalized})).hexdigest()


def _object_name(uri: str, bucket: str, prefix: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or parsed.netloc != bucket:
        raise ValueError("ML/OOS artifact must stay in the configured Mart bucket")
    name = parsed.path.lstrip("/")
    if not name.startswith(prefix) or not name.endswith(".parquet"):
        raise ValueError("ML/OOS Parquet reference escaped its versioned prefix")
    return name


def inspect_dataset(manifest: dict, store) -> dict:
    """Verify an immutable versioned Parquet dataset without materializing it in pandas."""
    if manifest.get("artifact_kind") != ARTIFACT_KIND:
        raise ValueError("unknown ML/OOS dataset contract")
    if manifest.get("dataset_schema_version") != DATASET_SCHEMA_VERSION:
        raise ValueError("unsupported ML/OOS dataset schema")
    identity = manifest.get("identity")
    shards = manifest.get("parquet_shards")
    if not isinstance(identity, dict) or not isinstance(shards, list) or not 0 < len(shards) <= MAX_SHARDS:
        raise ValueError("ML/OOS dataset identity and bounded shards are required")
    required_identity = {
        "core_snapshot_id", "core_manifest_sha256", "analysis_as_of",
        "dataset_schema_version", "query_contract_version", "feature_version", "model_version",
        "source_tables", "date_bounds", "label_horizon_trading_days",
        "cohort_stride_trading_days",
    }
    if not required_identity <= set(identity):
        raise ValueError("ML/OOS dataset identity is incomplete")
    if identity["dataset_schema_version"] != DATASET_SCHEMA_VERSION:
        raise ValueError("ML/OOS identity schema mismatch")
    if identity["query_contract_version"] != QUERY_CONTRACT_VERSION:
        raise ValueError("unsupported ML/OOS query contract")
    if manifest.get("core_snapshot_id") != identity["core_snapshot_id"] \
            or manifest.get("analysis_as_of") != identity["analysis_as_of"] \
            or manifest.get("query_contract_version") != identity["query_contract_version"] \
            or manifest.get("feature_version") != identity["feature_version"] \
            or manifest.get("model_version") != identity["model_version"]:
        raise ValueError("ML/OOS manifest lineage mismatch")
    if manifest.get("storage_read_api_used") is not False:
        raise ValueError("BigQuery Storage Read API is prohibited")
    retention = manifest.get("retention")
    if not isinstance(retention, dict) or retention.get("policy") != "latest-referenced-oos-or-7d-unreferenced":
        raise ValueError("ML/OOS retention contract missing")
    expected = dataset_content_hash(identity, shards)
    if manifest.get("dataset_content_hash") != expected:
        raise RuntimeError("ML/OOS dataset content identity mismatch")

    analysis_as_of = date.fromisoformat(str(identity["analysis_as_of"]))
    dataset_prefix = str(manifest.get("dataset_prefix", ""))
    expected_prefix = f"gs://{store.bucket}/ml-oos-data/v1/"
    if not dataset_prefix.startswith(expected_prefix) or not dataset_prefix.endswith("/"):
        raise ValueError("invalid ML/OOS dataset prefix")
    object_prefix = dataset_prefix.removeprefix(f"gs://{store.bucket}/")

    import pyarrow as pa
    import pyarrow.parquet as pq

    total_bytes = 0
    total_rows = 0
    symbols: set[str] = set()
    first_date = None
    last_date = None
    for shard in sorted(shards, key=lambda value: str(value["uri"])):
        name = _object_name(str(shard["uri"]), store.bucket, object_prefix)
        raw = store.read(name)
        actual_hash = "sha256:" + sha256(raw).hexdigest()
        if actual_hash != shard.get("sha256") or len(raw) != int(shard.get("size_bytes", -1)):
            raise RuntimeError("ML/OOS Parquet shard hash/size mismatch")
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("ML/OOS dataset byte bound exceeded")
        parquet = pq.ParquetFile(pa.BufferReader(raw))
        names = set(parquet.schema_arrow.names)
        if not REQUIRED_COLUMNS <= names or names & FORBIDDEN_COLUMNS:
            raise ValueError("ML/OOS Parquet schema is incomplete or exposes private fields")
        for batch in parquet.iter_batches(batch_size=8192):
            rows = batch.to_pylist()
            total_rows += len(rows)
            if total_rows > MAX_ROWS:
                raise ValueError("ML/OOS dataset row bound exceeded")
            for row in rows:
                if str(row["core_snapshot_id"]) != str(identity["core_snapshot_id"]) \
                        or str(row["analysis_as_of"]) != str(identity["analysis_as_of"]) \
                        or str(row["dataset_schema_version"]) != DATASET_SCHEMA_VERSION \
                        or str(row["query_contract_version"]) != str(identity["query_contract_version"]) \
                        or str(row["feature_version"]) != str(identity["feature_version"]) \
                        or str(row["model_version"]) != str(identity["model_version"]):
                    raise RuntimeError("ML/OOS row lineage mismatch")
                trade_date = row["trade_date"]
                maturity = row["label_maturity_date"]
                trade_date = trade_date if isinstance(trade_date, date) else date.fromisoformat(str(trade_date))
                maturity = maturity if isinstance(maturity, date) else date.fromisoformat(str(maturity))
                if maturity > analysis_as_of or maturity <= trade_date or row["label_return_20d"] is None:
                    raise ValueError("ML/OOS label maturity contract violated")
                symbols.add(str(row["symbol"]))
                first_date = trade_date if first_date is None or trade_date < first_date else first_date
                last_date = trade_date if last_date is None or trade_date > last_date else last_date
    if total_rows <= 0 or total_rows != int(manifest.get("row_count", -1)):
        raise ValueError("ML/OOS row-count readback mismatch")
    if total_bytes != int(manifest.get("export_bytes", -1)):
        raise ValueError("ML/OOS byte-count readback mismatch")
    return {
        "dataset_content_hash": expected,
        "row_count": total_rows,
        "export_bytes": total_bytes,
        "shard_count": len(shards),
        "symbol_count": len(symbols),
        "first_trade_date": first_date.isoformat() if first_date else None,
        "last_trade_date": last_date.isoformat() if last_date else None,
        "analysis_as_of": identity["analysis_as_of"],
        "core_snapshot_id": identity["core_snapshot_id"],
        "storage_read_api_used": False,
    }


def run_acceptance() -> dict:
    """Cloud Run B5 readback: verify the exported Parquet path using the Mart identity."""
    from ingestion_core.stage import GcsObjectStore

    project = os.environ.get("GCP_PROJECT_ID", "")
    bucket = os.environ.get("MART_BUCKET", "")
    if project != "gen-lang-client-0593591102" or bucket != "gen-lang-client-0593591102-dev-mart":
        raise ValueError("B5 ML/OOS acceptance is restricted to existing Janus dev resources")
    uri = urlparse(os.environ["MART_ML_OOS_MANIFEST_URI"])
    if uri.scheme != "gs" or uri.netloc != bucket or not uri.path.startswith("/ml-oos-data/v1/") \
            or not uri.path.endswith("/manifest.json"):
        raise ValueError("invalid B5 ML/OOS manifest URI")
    store = GcsObjectStore(bucket)
    raw = store.read(uri.path.lstrip("/"))
    manifest = json.loads(raw)
    result = inspect_dataset(manifest, store)
    response = {
        "component": "intelligence-mart",
        "operation": "ml-oos-data-acceptance",
        "status": "pass",
        "manifest_uri": os.environ["MART_ML_OOS_MANIFEST_URI"],
        "manifest_sha256": "sha256:" + sha256(raw).hexdigest(),
        "llm_api_tokens": 0,
        "ceo_triggered": False,
        **result,
    }
    result_uri = os.environ.get("MART_ML_OOS_RESULT_URI", "").strip()
    if result_uri:
        target = urlparse(result_uri)
        if target.scheme != "gs" or target.netloc != bucket or not target.path.startswith("/acceptance/b5-live/") \
                or not target.path.endswith(".json"):
            raise ValueError("invalid B5 ML/OOS result URI")
        payload = (json.dumps(response, sort_keys=True) + "\n").encode()
        name = target.path.lstrip("/")
        if not store.create(name, payload, "application/json") and store.read(name) != payload:
            raise RuntimeError("B5 ML/OOS immutable result conflict")
        if store.read(name) != payload:
            raise RuntimeError("B5 ML/OOS result readback mismatch")
    return response
