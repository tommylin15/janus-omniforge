#!/usr/bin/env python3
"""Build one bounded, versioned B5 ML/OOS Parquet dataset from the fixed B2 Core snapshot."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import runpy
import signal
import sys
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "jobs/intelligence-mart")]

from intelligence_mart.ml_oos_data import DATASET_SCHEMA_VERSION, QUERY_CONTRACT_VERSION, dataset_content_hash

PROJECT = "gen-lang-client-0593591102"
LOCATION = "US"
MART_BUCKET = "gen-lang-client-0593591102-dev-mart"
BUDGET = 1_073_741_824
QUERY_TIMEOUT_SECONDS = 60
FEATURE_VERSION = "2"
MODEL_VERSION = "deterministic-v1"
LABEL_HORIZON = 20
COHORT_STRIDE = 5
LOOKBACK_CALENDAR_DAYS = 241
STAGE_HEARTBEAT_SECONDS = 10


def stage_call(label: str, timeout_seconds: float, action):
    """Bound external calls by wall time and emit safe stage heartbeats."""
    if timeout_seconds <= 0:
        raise TimeoutError(f"B5 stage deadline exhausted: {label}")
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("B5 stage deadline must run on the main thread")
    started = time.monotonic()
    stop = threading.Event()

    def expired(_signum, _frame):
        raise TimeoutError(f"B5 stage timeout: {label} ({timeout_seconds:.1f}s)")

    def heartbeat():
        while not stop.wait(STAGE_HEARTBEAT_SECONDS):
            print(
                f"B5_STAGE event=heartbeat stage={label} "
                f"elapsed_seconds={time.monotonic() - started:.1f}",
                flush=True,
            )

    print(f"B5_STAGE event=start stage={label} timeout_seconds={timeout_seconds:.1f}", flush=True)
    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    watcher = threading.Thread(target=heartbeat, daemon=True)
    watcher.start()
    try:
        result = action()
    except BaseException as exc:
        print(
            f"B5_STAGE event=failed stage={label} "
            f"elapsed_seconds={time.monotonic() - started:.1f} error_type={type(exc).__name__}",
            flush=True,
        )
        raise
    else:
        print(
            f"B5_STAGE event=complete stage={label} "
            f"elapsed_seconds={time.monotonic() - started:.1f}",
            flush=True,
        )
        return result
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        stop.set()
        watcher.join(timeout=0.2)




def gcs_bytes(b2, uri: str) -> bytes:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc or not parsed.path.startswith("/"):
        raise ValueError("expected gs:// object URI")
    endpoint = (
        "https://storage.googleapis.com/download/storage/v1/b/"
        f"{urllib.parse.quote(parsed.netloc, safe='')}/o/"
        f"{urllib.parse.quote(parsed.path.lstrip('/'), safe='')}?alt=media"
    )
    request = urllib.request.Request(
        endpoint, headers={"Authorization": f"Bearer {b2['token']()}"}, method="GET"
    )
    with urllib.request.urlopen(request, timeout=65) as response:
        return response.read()


def gcs_create(b2, uri: str, payload: bytes, content_type: str) -> None:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "gs" or parsed.netloc != MART_BUCKET or not parsed.path.startswith("/ml-oos-data/v1/"):
        raise ValueError("B5 output must stay inside the versioned dev-mart ML/OOS prefix")
    name = parsed.path.lstrip("/")
    endpoint = (
        "https://storage.googleapis.com/upload/storage/v1/b/"
        f"{urllib.parse.quote(parsed.netloc, safe='')}/o?uploadType=media&ifGenerationMatch=0&name="
        f"{urllib.parse.quote(name, safe='')}"
    )
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {b2['token']()}",
            "Content-Type": content_type,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=65):
            return
    except Exception as error:
        raise RuntimeError(f"immutable GCS create failed for {uri}") from error


def table_pointer(b2, table: str) -> str:
    return b2["metadata_location"](b2["load_table"](table, b2["CORE_NAMESPACE"]))


def reduction_select(fq: str, *, start: date, end: date, core_snapshot_id: str) -> str:
    return f"""
WITH base AS (
  SELECT
    CAST(symbol AS STRING) AS symbol,
    trade_date,
    SAFE_CAST(close AS FLOAT64) AS close_value,
    SAFE_CAST(volume_shares AS FLOAT64) AS volume_shares,
    SAFE_CAST(turnover_twd AS FLOAT64) AS turnover_twd,
    CAST(source_id AS STRING) AS source_id,
    CAST(provenance_id AS STRING) AS provenance_id,
    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trade_date) AS sample_ordinal,
    LAG(SAFE_CAST(close AS FLOAT64), 5) OVER (PARTITION BY symbol ORDER BY trade_date) AS close_lag_5,
    LAG(SAFE_CAST(close AS FLOAT64), 20) OVER (PARTITION BY symbol ORDER BY trade_date) AS close_lag_20,
    LEAD(SAFE_CAST(close AS FLOAT64), {LABEL_HORIZON}) OVER (PARTITION BY symbol ORDER BY trade_date) AS close_lead,
    LEAD(trade_date, {LABEL_HORIZON}) OVER (PARTITION BY symbol ORDER BY trade_date) AS label_maturity_date
  FROM {fq}
  WHERE trade_date BETWEEN DATE '{start.isoformat()}' AND DATE '{end.isoformat()}'
),
reduced AS (
  SELECT
    symbol,
    trade_date,
    SAFE_DIVIDE(close_value, close_lag_5) - 1.0 AS return_5d,
    SAFE_DIVIDE(close_value, close_lag_20) - 1.0 AS return_20d,
    LN(1.0 + GREATEST(turnover_twd, 0.0)) AS log_turnover_twd,
    volume_shares,
    SAFE_DIVIDE(close_lead, close_value) - 1.0 AS label_return_20d,
    label_maturity_date,
    source_id,
    provenance_id,
    sample_ordinal
  FROM base
  WHERE close_value > 0
    AND close_lag_5 > 0
    AND close_lag_20 > 0
    AND close_lead > 0
    AND label_maturity_date <= DATE '{end.isoformat()}'
)
SELECT
  symbol,
  trade_date,
  return_5d,
  return_20d,
  log_turnover_twd,
  volume_shares,
  label_return_20d,
  label_maturity_date,
  source_id,
  provenance_id,
  '{core_snapshot_id}' AS core_snapshot_id,
  '{end.isoformat()}' AS analysis_as_of,
  '{DATASET_SCHEMA_VERSION}' AS dataset_schema_version,
  '{QUERY_CONTRACT_VERSION}' AS query_contract_version,
  '{FEATURE_VERSION}' AS feature_version,
  '{MODEL_VERSION}' AS model_version
FROM reduced
WHERE MOD(sample_ordinal - 1, {COHORT_STRIDE}) = 0
""".strip()


class QueryBudget:
    def __init__(self, client):
        self.client = client
        self.jobs: list[dict] = []
        self.billed = 0

    @property
    def remaining(self) -> int:
        return BUDGET - self.billed

    def dry_run(self, sql: str) -> int | None:
        from google.cloud import bigquery
        job = stage_call(
            "bigquery-dry-run", 40,
            lambda: self.client.query(
                sql,
                location=LOCATION,
                job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False),
                timeout=35,
            ),
        )
        value = job.total_bytes_processed
        if value is not None and value > BUDGET:
            raise RuntimeError("B5 dry-run estimate exceeds 1 GiB execution budget")
        return int(value) if value is not None else None

    def query(self, sql: str, label: str):
        from google.cloud import bigquery
        if self.remaining <= 0:
            raise RuntimeError("B5 BigQuery execution budget exhausted")
        started = time.monotonic()
        job = stage_call(
            f"bigquery-{label}-submit", 20,
            lambda: self.client.query(
                sql,
                location=LOCATION,
                job_config=bigquery.QueryJobConfig(
                    use_query_cache=False,
                    maximum_bytes_billed=self.remaining,
                    job_timeout_ms=QUERY_TIMEOUT_SECONDS * 1000,
                    labels={"janus_gate": "b5", "janus_workload": label[:63].replace("_", "-")},
                ),
                timeout=18,
                job_retry=None,  # Never blindly resubmit an immutable EXPORT DATA job.
            ),
        )
        print(f"B5_QUERY event=submitted label={label} job_id={job.job_id}", flush=True)
        try:
            remaining = QUERY_TIMEOUT_SECONDS - (time.monotonic() - started)
            rows = stage_call(
                f"bigquery-{label}-result", remaining,
                lambda: list(job.result(timeout=remaining, job_retry=None)),
            )
        except Exception as exc:
            error_result = job.error_result or {}
            print(
                f"B5_QUERY event=failed label={label} job_id={job.job_id} "
                f"error_type={type(exc).__name__} bq_reason={error_result.get('reason', 'unknown')}",
                flush=True,
            )
            try:
                stage_call(f"bigquery-{label}-cancel", 10, lambda: job.cancel(timeout=8))
            except Exception:
                pass
            raise
        elapsed = time.monotonic() - started
        child_jobs = []
        if label == "export-parquet":
            # A SCRIPT parent can summarize child usage. Read individual jobs to
            # audit CREATE TEMP / EXPORT / DROP without double-counting the parent.
            listed = stage_call(
                "bigquery-export-child-list", 20,
                lambda: list(self.client.list_jobs(parent_job=job.job_id, max_results=10)),
            )
            if len(listed) != 3:
                raise RuntimeError("B5 export script child job count unexpected")
            for child in listed:
                detail = stage_call(
                    "bigquery-export-child-readback", 15,
                    lambda child_id=child.job_id: self.client.get_job(
                        child_id, location=LOCATION, timeout=12,
                    ),
                )
                if detail.state != "DONE" or detail.error_result:
                    raise RuntimeError("B5 export child job did not complete successfully")
                child_jobs.append({
                    "job_id": detail.job_id,
                    "statement_type": detail.statement_type,
                    "processed_bytes": int(detail.total_bytes_processed)
                    if detail.total_bytes_processed is not None else None,
                    "billed_bytes": int(detail.total_bytes_billed)
                    if detail.total_bytes_billed is not None else None,
                })
        if job.total_bytes_billed is None:
            if label != "export-parquet" or any(x["billed_bytes"] is None for x in child_jobs):
                raise RuntimeError("B5 BigQuery billed bytes unknown")
            billed = sum(x["billed_bytes"] for x in child_jobs)
        else:
            billed = int(job.total_bytes_billed)
        self.billed += billed
        if self.billed > BUDGET:
            raise RuntimeError("B5 BigQuery cumulative billed bytes exceeded 1 GiB")
        item = {
            "label": label,
            "job_id": job.job_id,
            "processed_bytes": int(job.total_bytes_processed) if job.total_bytes_processed is not None else None,
            "billed_bytes": billed,
            "elapsed_seconds": elapsed,
            "cumulative_billed_bytes": self.billed,
            "remaining_budget_bytes": self.remaining,
            "child_jobs": child_jobs,
        }
        self.jobs.append(item)
        return rows, item


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    b2 = stage_call("load-b2-contract", 10, lambda: runpy.run_path(str(ROOT / "scripts/gcp/b2-lakehouse-acceptance.py")))
    core, manifest_hash = stage_call("gcs-core-manifest", 45, lambda: b2["gcs_json"](b2["CORE_MANIFEST_URI"]))
    if manifest_hash != b2["CORE_MANIFEST_SHA256"] or core.get("snapshot_id") != b2["CORE_SNAPSHOT_ID"]:
        raise RuntimeError("B5 fixed Core manifest fence mismatch")
    fence = core["iceberg_tables"]["core.ohlcv_v1"]
    if stage_call("catalog-pointer-initial", 45, lambda: table_pointer(b2, "ohlcv_v1")) != fence["metadata_location"]:
        raise RuntimeError("B5 shared catalog pointer does not match fixed Core snapshot")

    analysis_as_of = date.fromisoformat(core["analysis_as_of"])
    start = analysis_as_of - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    identity = {
        "core_snapshot_id": core["snapshot_id"],
        "core_manifest_sha256": "sha256:" + manifest_hash,
        "analysis_as_of": core["analysis_as_of"],
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "feature_version": FEATURE_VERSION,
        "model_version": MODEL_VERSION,
        "source_tables": {
            "core.ohlcv_v1": {
                "snapshot_id": fence["snapshot_id"],
                "metadata_location": fence["metadata_location"],
            }
        },
        "date_bounds": [start.isoformat(), analysis_as_of.isoformat()],
        "label_horizon_trading_days": LABEL_HORIZON,
        "cohort_stride_trading_days": COHORT_STRIDE,
    }
    identity_hash = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    prefix = f"ml-oos-data/v1/{identity_hash}/"
    manifest_uri = f"gs://{MART_BUCKET}/{prefix}manifest.json"

    existing = stage_call("gcs-existing-list", 45, lambda: b2["gcs_list_objects"](MART_BUCKET, prefix))
    if existing:
        names = {item["name"] for item in existing}
        if prefix + "manifest.json" not in names:
            raise RuntimeError("partial immutable B5 dataset exists without manifest")
        manifest, _ = stage_call("gcs-existing-manifest", 45, lambda: b2["gcs_json"](manifest_uri))
        if manifest.get("identity") != identity:
            raise RuntimeError("existing B5 manifest identity conflict")
        args.output.write_text(json.dumps({
            "status": "pass",
            "reused": True,
            "manifest_uri": manifest_uri,
            "dataset_content_hash": manifest["dataset_content_hash"],
            "row_count": manifest["row_count"],
            "export_bytes": manifest["export_bytes"],
            "bigquery_jobs": [],
            "total_billed_bytes": 0,
            "storage_read_api_used": False,
            "core_snapshot_id": core["snapshot_id"],
            "analysis_as_of": core["analysis_as_of"],
        }, indent=2, sort_keys=True) + "\n")
        print(args.output.read_text())
        return

    from google.cloud import bigquery

    client = stage_call("bigquery-client-init", 20, lambda: bigquery.Client(project=PROJECT, location=LOCATION))
    budget = QueryBudget(client)
    fq = f"`{PROJECT}.{b2['CATALOG']}.{b2['CORE_NAMESPACE']}.ohlcv_v1`"
    select_sql = reduction_select(
        fq, start=start, end=analysis_as_of, core_snapshot_id=core["snapshot_id"]
    )
    estimate = budget.dry_run(select_sql)
    count_rows, _ = budget.query(f"SELECT COUNT(*) AS n FROM ({select_sql})", "count-reduced")
    row_count = int(count_rows[0]["n"]) if count_rows else 0
    if row_count <= 0 or row_count > 500_000:
        raise RuntimeError(f"B5 reduced row count outside bound: {row_count}")

    export_uri = f"gs://{MART_BUCKET}/{prefix}part-*.parquet"
    # BigQuery cannot export directly from a shared Iceberg/external catalog table.
    # First materialize only the already bounded/reduced columns into a native
    # session-temporary table; export that derived table, then drop it explicitly.
    # No permanent dataset/table, Core mutation, or Storage Read API.
    export_sql = (
        "CREATE TEMP TABLE b5_export_reduced AS\n"
        f"{select_sql};\n"
        "EXPORT DATA OPTIONS("
        f"uri='{export_uri}', format='PARQUET', overwrite=false"
        ") AS SELECT * FROM _SESSION.b5_export_reduced;\n"
        "DROP TABLE _SESSION.b5_export_reduced;"
    )
    budget.query(export_sql, "export-parquet")
    if stage_call("catalog-pointer-post-export", 45, lambda: table_pointer(b2, "ohlcv_v1")) != fence["metadata_location"]:
        raise RuntimeError("B5 shared catalog pointer changed during export")

    objects = [
        item for item in stage_call("gcs-export-list", 45, lambda: b2["gcs_list_objects"](MART_BUCKET, prefix))
        if item["name"].endswith(".parquet")
    ]
    if not objects or len(objects) > 64:
        raise RuntimeError("B5 export did not produce a bounded Parquet shard set")
    shards = []
    export_bytes = 0
    for item in sorted(objects, key=lambda value: value["name"]):
        uri = f"gs://{MART_BUCKET}/{item['name']}"
        raw = stage_call("gcs-parquet-readback", 65, lambda: gcs_bytes(b2, uri))
        size = len(raw)
        if size != int(item["size"]):
            raise RuntimeError("B5 GCS object size changed during readback")
        export_bytes += size
        shards.append({
            "uri": uri,
            "sha256": "sha256:" + sha256(raw).hexdigest(),
            "size_bytes": size,
            "generation": str(item["generation"]),
        })
    if export_bytes <= 0 or export_bytes > 512 * 1024 * 1024:
        raise RuntimeError("B5 export byte size outside bounded acceptance")

    manifest = {
        "artifact_kind": "mart_ml_oos_dataset_v1",
        "schema_version": "1.0.0",
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "dataset_prefix": f"gs://{MART_BUCKET}/{prefix}",
        "core_snapshot_id": core["snapshot_id"],
        "analysis_as_of": core["analysis_as_of"],
        "feature_version": FEATURE_VERSION,
        "model_version": MODEL_VERSION,
        "identity": identity,
        "parquet_shards": shards,
        "row_count": row_count,
        "export_bytes": export_bytes,
        "dataset_content_hash": dataset_content_hash(identity, shards),
        "query": {
            "backend": "bigquery-shared-catalog",
            "dry_run_estimated_bytes": estimate,
            "jobs": budget.jobs,
            "total_billed_bytes": budget.billed,
            "execution_byte_budget": BUDGET,
            "query_timeout_seconds": QUERY_TIMEOUT_SECONDS,
            "column_date_partition_bounded": True,
        },
        "storage_read_api_used": False,
        "canonical_write": False,
        "provenance": {
            "core_manifest_uri": b2["CORE_MANIFEST_URI"],
            "core_manifest_sha256": "sha256:" + manifest_hash,
            "source_tables": identity["source_tables"],
        },
        "retention": {
            "policy": "latest-referenced-oos-or-7d-unreferenced",
            "reference_protected": True,
            "canonical": False,
        },
    }
    payload = (json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n").encode()
    stage_call("gcs-manifest-create", 65, lambda: gcs_create(b2, manifest_uri, payload, "application/json"))
    readback = stage_call("gcs-manifest-readback", 65, lambda: gcs_bytes(b2, manifest_uri))
    if readback != payload:
        raise RuntimeError("B5 immutable manifest readback mismatch")

    evidence = {
        "status": "pass",
        "reused": False,
        "manifest_uri": manifest_uri,
        "manifest_sha256": "sha256:" + sha256(payload).hexdigest(),
        "dataset_content_hash": manifest["dataset_content_hash"],
        "row_count": row_count,
        "export_bytes": export_bytes,
        "parquet_shards": len(shards),
        "bigquery_jobs": budget.jobs,
        "total_billed_bytes": budget.billed,
        "execution_byte_budget": BUDGET,
        "query_timeout_seconds": QUERY_TIMEOUT_SECONDS,
        "dry_run_estimated_bytes": estimate,
        "storage_read_api_used": False,
        "core_snapshot_id": core["snapshot_id"],
        "analysis_as_of": core["analysis_as_of"],
    }
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(evidence, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
