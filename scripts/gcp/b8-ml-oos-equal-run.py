#!/usr/bin/env python3
"""Fixed-Core B8: fair B5 SQL reduction/Parquet vs PyIceberg, no retraining."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import resource
import runpy
import sys
from time import monotonic, time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "jobs/intelligence-mart")]
SOURCE = "core.ohlcv_v1"
PREFIX = "b8-ml-oos-benchmark/v1"
BUDGET = 1_073_741_824
MAX_ROWS = 250_000
MAX_BYTES = 64 * 1024 * 1024


def path_order():
    return (("pyiceberg", "cold"), ("bigquery-export", "cold"),
            ("bigquery-export", "warm"), ("pyiceberg", "warm"))


def output_prefix(bucket, run_id, phase):
    import re
    if not re.fullmatch(r"[0-9a-f]{32}", run_id) or phase not in ("cold", "warm"):
        raise ValueError("invalid bounded benchmark output prefix")
    return f"gs://{bucket}/{PREFIX}/{run_id}/{phase}/"


def safe_reason(exc):
    msg = str(exc).lower()
    if "403" in msg or "permissiondenied" in msg or "access denied" in msg:
        return "permission_denied"
    if "quota" in msg or "billed" in msg or "billing" in msg or "budget" in msg:
        return "budget_or_billing"
    if "timeout" in msg or isinstance(exc, TimeoutError):
        return "timeout"
    if "metadata" in msg or "pointer" in msg or "snapshot" in msg:
        return "source_fence"
    if "export" in msg or "storage" in msg or "parquet" in msg:
        return "export_or_readback"
    return "unknown"


def restore_parquet(payload, required, forbidden):
    import pyarrow as pa
    import pyarrow.parquet as pq
    if not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("Parquet export byte bound violated")
    obj = pq.ParquetFile(pa.BufferReader(payload))
    fields = set(obj.schema_arrow.names)
    if not required <= fields or fields & forbidden:
        raise ValueError("Parquet schema source authorization violated")
    if not 0 < obj.metadata.num_rows <= MAX_ROWS:
        raise ValueError("Parquet row bound violated")
    rows = []
    for batch in obj.iter_batches(batch_size=8192):
        rows.extend(batch.to_pylist())
        if len(rows) > MAX_ROWS:
            raise ValueError("Parquet streaming row bound")
    if len(rows) != obj.metadata.num_rows:
        raise ValueError("Parquet row count mismatch")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-uri", required=True)
    args = parser.parse_args()
    b2 = runpy.run_path(str(ROOT / "scripts/gcp/b2-lakehouse-acceptance.py"))
    b5 = runpy.run_path(str(ROOT / "scripts/gcp/b5-ml-oos-data.py"))
    b8 = runpy.run_path(str(ROOT / "scripts/gcp/b8-matched-ml-oos.py"))
    from intelligence_mart.analytics_reader import IcebergSnapshotReader
    from intelligence_mart.ml_oos_data import REQUIRED_COLUMNS, FORBIDDEN_COLUMNS
    from pyiceberg.table import StaticTable
    from google.cloud import bigquery
    import pyarrow as pa
    import pyarrow.parquet as pq

    evidence = {
        "schema_version": "b8-ml-oos-equal-run-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "partial", "failure": None,
        "default": "pyiceberg", "cutover": False,
        "canonical_write": False, "cache_write": False,
        "storage_read_api_used": False, "ml_retraining_triggered": False,
        "research_only_parquet": True, "phase_order": list(path_order()),
        "samples": [], "budget_bytes": BUDGET, "billed_bytes": None,
        "runner_peak_rss_mib": None, "actual_gcs_read_bytes": None,
        "overall_fidelity": None, "performance_decision": "inconclusive",
        "fallback_audit": None,
    }
    stage = "init"
    client = None
    budget = None
    try:
        stage = "fixed-core-preflight"
        core, raw_sha = b2["gcs_json"](b2["CORE_MANIFEST_URI"])
        if raw_sha != b2["CORE_MANIFEST_SHA256"] or core.get("snapshot_id") != b2["CORE_SNAPSHOT_ID"]:
            raise ValueError("B8 Core immutable raw manifest mismatch")
        old, _ = b2["gcs_json"](args.manifest_uri)
        identity = old["identity"]
        source = core["iceberg_tables"][SOURCE]
        if (identity["core_snapshot_id"] != core["snapshot_id"]
                or identity["core_manifest_sha256"] != "sha256:" + raw_sha
                or identity["source_tables"][SOURCE] != {
                    k: source[k] for k in ("snapshot_id", "metadata_location")}
                or identity["analysis_as_of"] != core["analysis_as_of"]
                or identity["label_horizon_trading_days"] != 20
                or identity["cohort_stride_trading_days"] != 5):
            raise ValueError("B8 B5 identical source/PIT identity mismatch")
        old_size = b5["b6_validate_hit"](
            old, args.manifest_uri, b2["MART_BUCKET"],
            lambda uri: b5["gcs_bytes"](b2, uri))
        if b5["table_pointer"](b2, "ohlcv_v1") != source["metadata_location"]:
            raise ValueError("B8 shared catalog pointer drifted before benchmark")
        evidence.update(
            core_snapshot_id=core["snapshot_id"],
            core_manifest_sha256="sha256:" + raw_sha,
            analysis_as_of=core["analysis_as_of"],
            source_fence=identity["source_tables"][SOURCE],
            b5_manifest_uri=args.manifest_uri,
            baseline_rows=old["row_count"], baseline_export_bytes=old_size,
            label_horizon=20, stride=5, date_bounds=identity["date_bounds"])
        stage = "prepare-sql"
        token = b2["token"]()
        props = {"gcs.oauth2.token": token,
                 "gcs.oauth2.token-expires-at": str(int((time() + 3000) * 1000))}
        table = StaticTable.from_metadata(source["metadata_location"], properties=props)
        catalog = type("Catalog", (), {"load_table": lambda self, _: table})()
        fields = ("symbol", "trade_date", "close", "volume_shares",
                  "turnover_twd", "source_id", "provenance_id")
        start, end = identity["date_bounds"]
        sql = b5["reduction_select"](
            chr(96) + ".".join([b2["PROJECT"], b2["CATALOG"], b2["CORE_NAMESPACE"], "ohlcv_v1"]) + chr(96),
            start=date.fromisoformat(start), end=date.fromisoformat(end),
            core_snapshot_id=core["snapshot_id"])
        client = bigquery.Client(project=b2["PROJECT"], location="US")
        budget = b5["QueryBudget"](client)
        evidence["dry_run_lower_bound_bytes"] = budget.dry_run(sql)
        run_id = uuid.uuid4().hex
        evidence["research_run_id"] = run_id
        manifest = dict(core, iceberg_tables={SOURCE: source})
        reference = None
        for backend, phase in path_order():
            stage = backend + "-" + phase
            start_clock = monotonic()
            rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            if backend == "pyiceberg":
                snap = IcebergSnapshotReader(
                    catalog, date_bounds={SOURCE: ("trade_date", start, end)},
                    selected_fields={SOURCE: fields},
                ).read(manifest, tuple(), core_snapshot_id=core["snapshot_id"], row_limit=MAX_ROWS)
                read_sec = monotonic() - start_clock
                rows = b8["reduce_ohlcv"](snap.datasets["ohlcv"], identity)
                if len(rows) != old["row_count"]:
                    raise ValueError("B8 reference row count inconsistent with B5")
                buf = BytesIO()
                pq.write_table(pa.Table.from_pylist(rows), buf, compression="snappy")
                payload = buf.getvalue()
                if not b8["compare_ml_oos_rows"](
                        rows, restore_parquet(payload, REQUIRED_COLUMNS, FORBIDDEN_COLUMNS))["equal"]:
                    raise ValueError("PyIceberg in-memory Parquet roundtrip mismatch")
                if reference is None:
                    reference = rows
                comparison = b8["compare_ml_oos_rows"](reference, rows)
                sample = {
                    "backend": backend, "phase": phase, "rows": len(rows),
                    "parquet_bytes": len(payload),
                    "parquet_sha256": "sha256:" + sha256(payload).hexdigest(),
                    "sink": "local-memory-parquet",
                    "reader_elapsed_seconds": read_sec, "reader_telemetry": snap.telemetry,
                    "bigquery_job": None, "gcs_export_bytes": None,
                }
            else:
                if reference is None or budget.remaining <= 0:
                    raise ValueError("B8 reference or BQ budget unavailable")
                prefix = output_prefix(b2["MART_BUCKET"], run_id, phase)
                # Same B5 SQL, temp native table and native Parquet export;
                # strictly fresh research-only GCS prefix; never overwrite B5/B6.
                script = ("CREATE TEMP TABLE b8_export_reduced AS\n" + sql
                          + ";\nEXPORT DATA OPTIONS(uri='" + prefix
                          + "part-*.parquet', format='PARQUET', overwrite=false)"
                          + " AS SELECT * FROM _SESSION.b8_export_reduced;\n"
                          + "DROP TABLE _SESSION.b8_export_reduced;")
                _, job = budget.query(script, "export-parquet")
                objs = b2["gcs_list_objects"](
                    b2["MART_BUCKET"], f"{PREFIX}/{run_id}/{phase}/")
                objs = [o for o in objs if o["name"].endswith(".parquet")]
                if not 0 < len(objs) <= 8:
                    raise ValueError("B8 research export shard count mismatch")
                candidate, shards, total = [], [], 0
                for obj in sorted(objs, key=lambda x: x["name"]):
                    uri = "gs://" + b2["MART_BUCKET"] + "/" + obj["name"]
                    raw = b5["gcs_bytes"](b2, uri)
                    if len(raw) != int(obj["size"]):
                        raise ValueError("B8 export object size mismatch")
                    total += len(raw)
                    if total > MAX_BYTES:
                        raise ValueError("B8 research Parquet export exceeds byte bound")
                    candidate.extend(restore_parquet(raw, REQUIRED_COLUMNS, FORBIDDEN_COLUMNS))
                    shards.append({"uri": uri, "generation": str(obj["generation"]),
                                   "size_bytes": len(raw),
                                   "sha256": "sha256:" + sha256(raw).hexdigest()})
                if len(candidate) != old["row_count"]:
                    raise ValueError("B8 BigQuery export row count mismatch")
                comparison = b8["compare_ml_oos_rows"](reference, candidate)
                sample = {
                    "backend": backend, "phase": phase, "rows": len(candidate),
                    "parquet_bytes": total, "gcs_export_bytes": total,
                    "research_parquet_shards": shards, "sink": "dev-mart-gcs-parquet",
                    "bigquery_job": job,
                }
            sample["elapsed_seconds"] = monotonic() - start_clock
            sample["runner_rss_high_water_mib_start"] = rss_before
            sample["runner_rss_high_water_mib_end"] = resource.getrusage(
                resource.RUSAGE_SELF).ru_maxrss / 1024
            sample["comparison"] = comparison
            evidence["samples"].append(sample)
            if not comparison["equal"]:
                raise ValueError("B8 same-Core ML/OOS data output mismatch")
            if b5["table_pointer"](b2, "ohlcv_v1") != source["metadata_location"]:
                raise ValueError("B8 shared catalog pointer changed during comparison")
        if budget.billed > BUDGET:
            raise ValueError("B8 billed budget exceeded")
        evidence["status"] = "pass"
        evidence["overall_fidelity"] = True
        evidence["billed_bytes"] = budget.billed
    except Exception as exc:
        evidence["failure"] = {"stage": stage, "type": type(exc).__name__,
                               "reason": safe_reason(exc)}
        evidence["fallback_audit"] = {
            "stage": stage, "preserves_default": True,
            "automatic_reexecution_verified": False,
            "failed_job_bill_unknown": True,
        }
        if budget and budget.jobs:
            evidence["billed_bytes"] = budget.billed
        # Raw errors may contain credentials, filenames or private metadata; never print.
    finally:
        if client:
            client.close()
        evidence["final_stage"] = stage
        evidence["runner_peak_rss_mib"] = resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss / 1024
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8")
        print(json.dumps({
            "status": evidence["status"], "sample_count": len(evidence["samples"]),
            "billed_bytes": evidence["billed_bytes"], "failure": evidence["failure"],
            "cutover": False, "default": "pyiceberg"}, sort_keys=True), flush=True)
    if evidence["status"] != "pass":
        raise RuntimeError("B8 ML/OOS equal-run validation not PASS")


if __name__ == "__main__":
    main()
