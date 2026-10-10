#!/usr/bin/env python3
"""B8 real fixed-Core PyIceberg read, with isolated injected BQ operational failure.

Safe fault injection exercises the same shared selector/fallback code without
making/altering billable BigQuery jobs or staging a failed GCS export.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import sys
from time import time, monotonic

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "jobs/intelligence-mart")]
SOURCE = "core.ohlcv_v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--backend", choices=("pyiceberg", "bigquery"), default="pyiceberg")
    parser.add_argument("--inject-bq-unavailable", action="store_true")
    args = parser.parse_args()
    # No live BQ query path in this fault-injection acceptance.
    if args.backend == "bigquery" and not args.inject_bq_unavailable:
        parser.error("non-injected BigQuery is validated by b8-ml-oos-equal-run.py")
    if args.inject_bq_unavailable and args.backend != "bigquery":
        parser.error("injected failure requires explicit BigQuery opt-in")

    b2 = runpy.run_path(str(ROOT / "scripts/gcp/b2-lakehouse-acceptance.py"))
    b5 = runpy.run_path(str(ROOT / "scripts/gcp/b5-ml-oos-data.py"))
    b8 = runpy.run_path(str(ROOT / "scripts/gcp/b8-matched-ml-oos.py"))
    from intelligence_mart.ml_oos_backend_policy import (
        BigQueryOperationalError, check_fixed_core, execute_ml_oos,
    )
    from intelligence_mart.analytics_reader import IcebergSnapshotReader
    from pyiceberg.table import StaticTable
    from intelligence_mart.ml_oos_data import REQUIRED_COLUMNS, FORBIDDEN_COLUMNS
    import pyarrow as pa
    import pyarrow.parquet as pq
    from hashlib import sha256

    evidence = {
        "schema_version": "b8-ml-oos-fallback-acceptance-v1",
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "partial", "failure": None,
        "fault_injection": "bigquery_unavailable" if args.inject_bq_unavailable else None,
        "fault_is_synthetic": bool(args.inject_bq_unavailable),
        "real_data_fallback_read": False,
        "bigquery_jobs_submitted": 0, "bigquery_billed_bytes": 0,
        "canonical_write": False, "cache_write": False,
        "storage_read_api_used": False, "ml_retraining_triggered": False,
        "default": "pyiceberg", "cutover": False,
    }
    stage = "preflight"
    try:
        core, core_hash = b2["gcs_json"](b2["CORE_MANIFEST_URI"])
        if core_hash != b2["CORE_MANIFEST_SHA256"] or core["snapshot_id"] != b2["CORE_SNAPSHOT_ID"]:
            raise ValueError("B8 Core immutable fence mismatch")
        old, old_hash = b2["gcs_json"](args.manifest_uri)
        identity = old["identity"]
        check_fixed_core(identity)
        source = core["iceberg_tables"][SOURCE]
        if (identity["core_snapshot_id"] != core["snapshot_id"]
                or identity["core_manifest_sha256"] != "sha256:" + core_hash
                or identity["source_tables"][SOURCE] != {
                    "snapshot_id": source["snapshot_id"],
                    "metadata_location": source["metadata_location"]}):
            raise ValueError("B8 B5/Core identity mismatch")
        verified_size = b5["b6_validate_hit"](
            old, args.manifest_uri, b2["MART_BUCKET"],
            lambda uri: b5["gcs_bytes"](b2, uri))
        if b5["table_pointer"](b2, "ohlcv_v1") != source["metadata_location"]:
            raise ValueError("B8 starting catalog pointer mismatch")
        baseline = []
        for shard in old["parquet_shards"]:
            payload = b5["gcs_bytes"](b2, shard["uri"])
            if "sha256:" + sha256(payload).hexdigest() != shard["sha256"]:
                raise ValueError("B8 immutable Parquet readback mismatch")
            parquet = pq.ParquetFile(pa.BufferReader(payload))
            if not REQUIRED_COLUMNS <= set(parquet.schema_arrow.names) or set(parquet.schema_arrow.names) & FORBIDDEN_COLUMNS:
                raise ValueError("B8 Parquet schema authorization mismatch")
            for batch in parquet.iter_batches(batch_size=8192):
                baseline.extend(batch.to_pylist())
        if len(baseline) != old["row_count"] or not 0 < len(baseline) <= 250_000:
            raise ValueError("B8 baseline row bound mismatch")
        stage = "backend-selection"
        token = b2["token"]()
        props = {
            "gcs.oauth2.token": token,
            "gcs.oauth2.token-expires-at": str(int((time() + 3000) * 1000)),
        }
        table = StaticTable.from_metadata(source["metadata_location"], properties=props)
        catalog = type("Catalog", (), {"load_table": lambda self, _: table})()
        start, end = identity["date_bounds"]
        cols = ("symbol", "trade_date", "close", "volume_shares",
                "turnover_twd", "source_id", "provenance_id")
        metadata = dict(core, iceberg_tables={SOURCE: source})
        started = monotonic()
        scans = [0]

        def pyiceberg_worker():
            scans[0] += 1
            snapshot = IcebergSnapshotReader(
                catalog, date_bounds={SOURCE: ("trade_date", start, end)},
                selected_fields={SOURCE: cols},
            ).read(metadata, tuple(), core_snapshot_id=core["snapshot_id"], row_limit=250_000)
            rows = b8["reduce_ohlcv"](snapshot.datasets["ohlcv"], identity)
            return {"rows": rows, "snapshot": core["snapshot_id"],
                    "telemetry": snapshot.telemetry}

        def bigquery_worker():
            # Synthetic backend error; tests invocation and actual same-Core fallback.
            raise BigQueryOperationalError("unavailable")

        def verify(value):
            if value["snapshot"] != core["snapshot_id"]:
                raise ValueError("fallback Core identity changed")
            comparison = b8["compare_ml_oos_rows"](value["rows"], baseline)
            if not comparison["equal"]:
                raise ValueError("fallback output not equal to immutable B5 Parquet")

        stage = "execute-backend"
        outcome = execute_ml_oos(
            identity=identity, requested_backend=args.backend,
            bigquery_opt_in=args.backend == "bigquery",
            pyiceberg_worker=pyiceberg_worker,
            bigquery_worker=bigquery_worker if args.backend == "bigquery" else None,
            verify=verify)
        if b5["table_pointer"](b2, "ohlcv_v1") != source["metadata_location"]:
            raise ValueError("catalog pointer drifted after fallback")
        if len(outcome.data["rows"]) != 10_978 or scans[0] != 1:
            raise ValueError("unexpected fallback row/scan count")
        if args.inject_bq_unavailable and not (outcome.audit["fallback_triggered"]
                and outcome.audit["fallback_status"] == "validated"):
            raise ValueError("explicit fault injection failed to trigger validated fallback")
        evidence.update(
            status="pass", source_core_snapshot_id=core["snapshot_id"],
            core_manifest_sha256="sha256:" + core_hash,
            export_manifest_sha256="sha256:" + old_hash,
            baseline_parquet_bytes=verified_size,
            row_count=len(outcome.data["rows"]),
            pyiceberg_source_rows=outcome.data["telemetry"]["total_rows"],
            pyiceberg_scan_count=scans[0],
            real_data_fallback_read=bool(args.inject_bq_unavailable),
            elapsed_seconds=monotonic() - started, audit=outcome.audit,
            comparison=b8["compare_ml_oos_rows"](outcome.data["rows"], baseline),
        )
    except Exception as exc:
        # Sanitized error classification only; never log raw payload or tokens.
        from intelligence_mart.ml_oos_backend_policy import BigQueryOperationalError
        evidence["failure"] = {"stage": stage, "exception_class": type(exc).__name__,
                               "error_code": "operational" if isinstance(exc, BigQueryOperationalError) else "validation"}
    finally:
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n")
        print(json.dumps({
            "B8_ML_OOS_FALLBACK": evidence["status"], "failure": evidence["failure"],
            "fault_injection": evidence["fault_injection"],
            "fallback_real_data": evidence["real_data_fallback_read"],
            "cutover": False}, sort_keys=True), flush=True)
    if evidence["status"] != "pass":
        raise RuntimeError("B8 ML/OOS fallback acceptance not PASS")


if __name__ == "__main__":
    main()
