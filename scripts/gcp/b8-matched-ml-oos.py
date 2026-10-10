#!/usr/bin/env python3
"""B8 read-only, same-Core PyIceberg vs B5 BigQuery-exported ML/OOS Parquet."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import isclose, isfinite, log1p
from pathlib import Path
import runpy
import sys
from time import monotonic, time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "jobs/intelligence-mart")]

SOURCE_TABLE = "core.ohlcv_v1"
FLOAT_COLUMNS = (
    "return_5d", "return_20d", "log_turnover_twd",
    "volume_shares", "label_return_20d",
)


def safe_number(value):
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return n if isfinite(n) else None


def reduce_ohlcv(rows, identity):
    """Independent reference for B5 SQL LAG/LEAD/ROW_NUMBER, never fitted model."""
    start, end = (date.fromisoformat(value) for value in identity["date_bounds"])
    if end.isoformat() != identity["analysis_as_of"]:
        raise ValueError("B8 analysis_as_of/date bounds mismatch")
    grouped = defaultdict(list)
    for row in rows:
        day = row["trade_date"]
        day = day if isinstance(day, date) else date.fromisoformat(str(day))
        if start <= day <= end:
            grouped[str(row["symbol"])].append((day, row))
    outputs = []
    for symbol, group in sorted(grouped.items()):
        group.sort(key=lambda item: item[0])
        # B5 window SQL has ORDER BY trade_date; duplicates have undefined tie order.
        if len({day for day, _ in group}) != len(group):
            raise ValueError("ambiguous duplicate symbol/date in source snapshot")
        for i, (day, row) in enumerate(group):
            if (i % 5) != 0 or i < 20 or i + 20 >= len(group):
                continue
            close = safe_number(row.get("close"))
            lag5 = safe_number(group[i - 5][1].get("close"))
            lag20 = safe_number(group[i - 20][1].get("close"))
            future = safe_number(group[i + 20][1].get("close"))
            maturity = group[i + 20][0]
            if any(value is None or value <= 0 for value in (close, lag5, lag20, future)):
                continue
            if maturity > end:
                continue
            turnover = safe_number(row.get("turnover_twd"))
            outputs.append({
                "symbol": symbol,
                "trade_date": day,
                "return_5d": close / lag5 - 1.0,
                "return_20d": close / lag20 - 1.0,
                "log_turnover_twd": log1p(max(turnover, 0.0)) if turnover is not None else None,
                "volume_shares": safe_number(row.get("volume_shares")),
                "label_return_20d": future / close - 1.0,
                "label_maturity_date": maturity,
                "source_id": str(row["source_id"]) if row.get("source_id") is not None else None,
                "provenance_id": str(row["provenance_id"]) if row.get("provenance_id") is not None else None,
                "core_snapshot_id": identity["core_snapshot_id"],
                "analysis_as_of": identity["analysis_as_of"],
                "dataset_schema_version": identity["dataset_schema_version"],
                "query_contract_version": identity["query_contract_version"],
                "feature_version": identity["feature_version"],
                "model_version": identity["model_version"],
            })
    return outputs


def compare_ml_oos_rows(reference, bigquery_export):
    """Compare exact record keys and null/provenance; floats use declared tolerance."""
    def index(items):
        rows = {}
        for item in items:
            key = str(item["symbol"]), str(item["trade_date"])
            if key in rows:
                raise ValueError("duplicate ML/OOS dataset row key")
            rows[key] = item
        return rows

    ref, candidate = index(reference), index(bigquery_export)
    different_keys = len(set(ref) ^ set(candidate))
    changed = 0
    examples = []
    for key in sorted(set(ref) & set(candidate)):
        a, b = ref[key], candidate[key]
        if set(a) != set(b):
            changed += 1
            if len(examples) < 5:
                examples.append({"symbol": key[0], "date": key[1], "field": "schema"})
            continue
        for column in sorted(a):
            left, right = a[column], b[column]
            if left is None or right is None:
                match = left is None and right is None
            elif column in FLOAT_COLUMNS:
                match = isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-10)
            elif column in ("trade_date", "label_maturity_date"):
                match = str(left) == str(right)
            else:
                match = left == right
            if not match:
                changed += 1
                if len(examples) < 5:
                    examples.append({"symbol": key[0], "date": key[1], "field": column})
                break
    return {
        "reference_rows": len(ref),
        "bigquery_export_rows": len(candidate),
        "different_keys": different_keys,
        "changed_rows": changed,
        "difference_examples": examples,
        "equal": not different_keys and not changed,
        "numeric_tolerance": {"relative": 1e-9, "absolute": 1e-10},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-uri", required=True)
    args = parser.parse_args()
    b2 = runpy.run_path(str(ROOT / "scripts/gcp/b2-lakehouse-acceptance.py"))
    b5 = runpy.run_path(str(ROOT / "scripts/gcp/b5-ml-oos-data.py"))
    from pyiceberg.table import StaticTable
    from intelligence_mart.analytics_reader import IcebergSnapshotReader
    from intelligence_mart.ml_oos_data import REQUIRED_COLUMNS, FORBIDDEN_COLUMNS
    import pyarrow as pa
    import pyarrow.parquet as pq

    core, manifest_hash = b2["gcs_json"](b2["CORE_MANIFEST_URI"])
    if manifest_hash != b2["CORE_MANIFEST_SHA256"] or core.get("snapshot_id") != b2["CORE_SNAPSHOT_ID"]:
        raise ValueError("B8 immutable fixed Core manifest mismatch")
    exported, exported_hash = b2["gcs_json"](args.manifest_uri)
    identity = exported["identity"]
    if identity.get("core_snapshot_id") != core["snapshot_id"] or identity.get("core_manifest_sha256") != "sha256:" + manifest_hash:
        raise ValueError("B8 BigQuery export does not match PyIceberg Core identity")
    source = identity["source_tables"][SOURCE_TABLE]
    core_source = core["iceberg_tables"][SOURCE_TABLE]
    if (source["snapshot_id"], source["metadata_location"]) != (
        core_source["snapshot_id"], core_source["metadata_location"],
    ):
        raise ValueError("B8 ML/OOS Core source table fence mismatch")
    if exported.get("row_count", 0) > 500_000 or exported.get("storage_read_api_used") is not False:
        raise ValueError("B8 ML/OOS export boundary violated")
    read_bytes = lambda uri: b5["gcs_bytes"](b2, uri)
    verified = b5["b6_validate_hit"](exported, args.manifest_uri, b2["MART_BUCKET"], read_bytes)

    exported_rows = []
    for shard in exported["parquet_shards"]:
        raw = read_bytes(shard["uri"])
        if "sha256:" + sha256(raw).hexdigest() != shard["sha256"]:
            raise ValueError("B8 Parquet hash mismatch on second independent read")
        parquet = pq.ParquetFile(pa.BufferReader(raw))
        if not REQUIRED_COLUMNS <= set(parquet.schema_arrow.names) or set(parquet.schema_arrow.names) & FORBIDDEN_COLUMNS:
            raise ValueError("B8 ML/OOS schema is incomplete or exposes private data")
        for batch in parquet.iter_batches(batch_size=8192):
            exported_rows.extend(batch.to_pylist())
            if len(exported_rows) > 500_000:
                raise ValueError("B8 ML/OOS row limit exceeded")
    if len(exported_rows) != exported["row_count"]:
        raise ValueError("B8 ML/OOS export row count mismatch")

    token = b2["token"]()
    props = {"gcs.oauth2.token": token,
             "gcs.oauth2.token-expires-at": str(int((time() + 3000) * 1000))}
    table = StaticTable.from_metadata(core_source["metadata_location"], properties=props)
    catalog = type("Catalog", (), {"load_table": lambda self, _: table})()
    cols = ("symbol", "trade_date", "close", "volume_shares", "turnover_twd", "source_id", "provenance_id")
    start, end = identity["date_bounds"]
    began = monotonic()
    snap = IcebergSnapshotReader(
        catalog, date_bounds={SOURCE_TABLE: ("trade_date", start, end)},
        selected_fields={SOURCE_TABLE: cols},
    ).read(dict(core, iceberg_tables={SOURCE_TABLE: core_source}), tuple(),
           core_snapshot_id=core["snapshot_id"], row_limit=250_000)
    py_read_seconds = monotonic() - began
    reference = reduce_ohlcv(snap.datasets["ohlcv"], identity)
    py_total_seconds = monotonic() - began
    comparison = compare_ml_oos_rows(reference, exported_rows)
    evidence = {
        "schema_version": "b8-matched-ml-oos-fidelity-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if comparison["equal"] else "failed",
        "core_snapshot_id": core["snapshot_id"],
        "core_manifest_sha256": "sha256:" + manifest_hash,
        "source_table": source,
        "analysis_as_of": identity["analysis_as_of"],
        "export_manifest_uri": args.manifest_uri,
        "export_manifest_sha256": "sha256:" + exported_hash,
        "export_bytes_verified": verified,
        "comparison": comparison,
        "pyiceberg_read_elapsed_seconds": py_read_seconds,
        "pyiceberg_total_elapsed_seconds": py_total_seconds,
        "pyiceberg_telemetry": snap.telemetry,
        "bigquery_legacy_export_elapsed_seconds": None,
        "bigquery_current_query_billed_bytes": None,
        "equal_run_performance": "not_verified",
        "default": "pyiceberg", "cutover": False,
        "canonical_write": False, "storage_read_api_used": False,
        "ml_retraining_triggered": False,
    }
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": evidence["status"], "rows": comparison["reference_rows"],
        "changed": comparison["changed_rows"], "different_keys": comparison["different_keys"],
        "cutover": False,
    }, sort_keys=True))
    if evidence["status"] != "pass":
        raise RuntimeError("B8 ML/OOS Parquet/PyIceberg source fidelity failed")


if __name__ == "__main__":
    main()
