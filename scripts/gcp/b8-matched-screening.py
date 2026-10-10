#!/usr/bin/env python3
"""B8 fixed-Core matched screening canary; read-only and never cuts over."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import sys
from time import monotonic, time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "jobs/intelligence-mart")]

BUDGET = 1_073_741_824
PER_READ_BUDGET = BUDGET // 2
SCOPE = ("core.ohlcv_v1", "core.benchmark_v1")
VALUATION = "core.valuation_v1"


def compare_snapshots(reference, candidate, *, core_identity: str) -> dict:
    """Fail closed on rows, nulls, types, PIT/provenance or source differences."""
    from intelligence_mart.facts import canonical_json

    if reference.core_snapshot_id != core_identity or candidate.core_snapshot_id != core_identity:
        raise ValueError("B8 Core snapshot identity mismatch")
    if set(reference.datasets) != set(candidate.datasets):
        raise ValueError("B8 dataset scope mismatch")
    tables = {}
    for name in sorted(reference.datasets):
        left, right = reference.datasets[name], candidate.datasets[name]
        equal = Counter(canonical_json(r) for r in left) == Counter(canonical_json(r) for r in right)
        tables[name] = {"reference_rows": len(left), "candidate_rows": len(right), "equal": equal}
    return {"tables": tables, "all_tables_equal": all(v["equal"] for v in tables.values())}


def _rss_mib():
    # Linux GitHub runner reports ru_maxrss in KiB; it is process-high-water telemetry.
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    b2 = runpy.run_path(str(ROOT / "scripts/gcp/b2-lakehouse-acceptance.py"))
    b3 = runpy.run_path(str(ROOT / "scripts/gcp/b3-screening-canary.py"))
    from google.cloud import bigquery
    from google.oauth2.credentials import Credentials
    from pyiceberg.table import StaticTable
    from intelligence_mart.analytics_reader import IcebergSnapshotReader
    from intelligence_mart.bigquery_reader import BigQueryAnalyticsReader
    from intelligence_mart.market_screening import FIELDS, market_features, read_plan
    from intelligence_mart.specialists import digest

    core, manifest_hash = b2["gcs_json"](b2["CORE_MANIFEST_URI"])
    if manifest_hash != b2["CORE_MANIFEST_SHA256"] or core.get("snapshot_id") != b2["CORE_SNAPSHOT_ID"]:
        raise RuntimeError("B8 fixed Core raw-byte manifest fence mismatch")
    membership, membership_uri, membership_hash = b3["fixed_membership"](b2, core)
    symbols = tuple(str(symbol) for symbol in membership["symbols"])
    if len(symbols) != 500 or len(set(symbols)) != 500 or membership["analysis_as_of"] != core["analysis_as_of"]:
        raise RuntimeError("B8 immutable membership scope mismatch")
    token = b2["token"]()
    properties = {
        "gcs.oauth2.token": token,
        "gcs.oauth2.token-expires-at": str(int((time() + 3000) * 1000)),
    }
    tables = {}

    class Catalog:
        def load_table(self, identifier):
            if identifier not in tables:
                tables[identifier] = StaticTable.from_metadata(
                    core["iceberg_tables"][identifier]["metadata_location"], properties=properties,
                )
            return tables[identifier]

    catalog = Catalog()
    inputs, bounds = read_plan(core, core["analysis_as_of"])
    if not set(SCOPE) <= set(bounds):
        raise RuntimeError("B8 missing pinned source tables")
    selected = {
        identifier: tuple(field for field in FIELDS[identifier]
                          if field in {item.name for item in catalog.load_table(identifier).schema().fields})
        for identifier in bounds
    }
    mapping = {
        identifier: f"{b2['PROJECT']}.{b2['CATALOG']}.{b2['CORE_NAMESPACE']}.{identifier.split('.')[1]}"
        for identifier in SCOPE
    }

    def pointer(table_id):
        _, _, namespace, table = table_id.split(".")
        return b2["metadata_location"](b2["load_table"](table, namespace))

    def run_pyiceberg():
        reader = IcebergSnapshotReader(catalog, date_bounds=bounds, selected_fields=selected)
        started = monotonic()
        snapshot = reader.read(inputs, symbols, core_snapshot_id=core["snapshot_id"], row_limit=150_000)
        rows = market_features(snapshot.datasets, symbols, core["analysis_as_of"], core["snapshot_id"])
        return snapshot, rows, monotonic() - started

    stage = {"name": "init"}

    def run_bigquery():
        stage["name"] = "bq-client"
        # The valuation leg is part of the candidate wall clock, not reused from
        # an earlier PyIceberg measurement as in the historical B3 spike.
        client = bigquery.Client(
            project=b2["PROJECT"], credentials=Credentials(token), location="US",
        )
        reader = BigQueryAnalyticsReader(
            client, catalog, mapping, location="US",
            maximum_bytes_billed=PER_READ_BUDGET,
            timeout=60, shared_metadata_loader=pointer,
            date_bounds={k: bounds[k] for k in SCOPE},
            selected_fields={k: selected[k] for k in SCOPE},
        )
        started = monotonic()
        try:
            stage["name"] = "bq-probe"
            snapshot = reader.probe(
                inputs, symbols, core_snapshot_id=core["snapshot_id"],
                table_scope=SCOPE, row_limit=150_000, dry_run=False,
            )
        finally:
            reader.close()
        combined = dict(snapshot.datasets)
        if VALUATION in bounds:
            stage["name"] = "valuation-read"
            valuation_input = dict(inputs, iceberg_tables={VALUATION: inputs["iceberg_tables"][VALUATION]})
            valuation = IcebergSnapshotReader(
                catalog, date_bounds={VALUATION: bounds[VALUATION]},
                selected_fields={VALUATION: selected[VALUATION]},
            ).read(valuation_input, symbols, core_snapshot_id=core["snapshot_id"], row_limit=150_000)
            combined.update(valuation.datasets)
        from intelligence_mart.analytics_reader import AnalyticsSnapshot
        full_snapshot = AnalyticsSnapshot(core["snapshot_id"], combined, snapshot.telemetry)
        stage["name"] = "screening-features"
        rows = market_features(combined, symbols, core["analysis_as_of"], core["snapshot_id"])
        stage["name"] = "complete"
        return full_snapshot, rows, monotonic() - started

    evidence = {
        "schema_version": "b8-matched-screening-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "partial",
        "core_snapshot_id": core["snapshot_id"],
        "core_manifest_raw_sha256": "sha256:" + manifest_hash,
        "core_manifest_uri": b2["CORE_MANIFEST_URI"],
        "source_table_fences": {key: dict(value) for key, value in inputs["iceberg_tables"].items()},
        "analysis_as_of": core["analysis_as_of"],
        "membership_uri": membership_uri,
        "membership_sha256": membership_hash,
        "membership_version": membership["membership_version"],
        "cohort_size": len(symbols),
        "workload": "full-market-screening-with-valuation",
        "path_order": ["pyiceberg-cold", "bigquery-cold", "bigquery-warm", "pyiceberg-warm"],
        "samples": [],
        "billed_budget_bytes": BUDGET,
        "total_billed_bytes": None,
        "process_peak_rss_mib": None,
        "actual_gcs_read_bytes": None,
        "performance_decision": "inconclusive",
        "default": "pyiceberg",
        "cutover": False,
        "storage_read_api_used": False,
        "canonical_write": False,
        "fallback_audit": None,
        "llm_api_tokens": 0,
        "specialist_count": 0,
    }
    billed = 0
    try:
        cold_ref, cold_ref_rows, cold_ref_elapsed = run_pyiceberg()
        evidence["samples"].append({
            "path": "pyiceberg", "phase": "cold", "elapsed_seconds": cold_ref_elapsed,
            "output_hash": digest(cold_ref_rows), "telemetry": cold_ref.telemetry,
        })
        if len(cold_ref_rows) != 500:
            raise RuntimeError("B8 reference screening cohort incomplete")
        for phase in ("cold", "warm"):
            try:
                candidate, candidate_rows, elapsed = run_bigquery()
            except Exception as exc:
                # Keep reference runnable, audit only the safe error class; never log raw payloads.
                # Diagnostic uses only a strict allowlist; never print GCP error payloads.
                msg = str(exc).lower()
                safe_reasons = (
                    ("http 403", "permission-denied"),
                    ("http 404", "missing-resource"),
                    ("permissiondenied", "permission-denied"),
                    ("access denied", "permission-denied"),
                    ("quota", "quota"),
                    ("timeout", "timeout"),
                    ("budget", "budget"),
                    ("billed bytes", "billed-unknown"),
                    ("row limit", "row-bound"),
                    ("snapshot", "snapshot-fence"),
                    ("metadata", "metadata-fence"),
                    ("catalog", "catalog"),
                )
                reason = next((value for pattern, value in safe_reasons if pattern in msg), "unknown")
                evidence["fallback_audit"] = {
                    "triggered": True, "error_code": type(exc).__name__.upper()[:64],
                    "failed_stage": stage["name"], "reason_code": reason,
                    "reference_preserved": True,
                    "canonical_write": False, "default": "pyiceberg",
                }
                break
            comparison = compare_snapshots(cold_ref, candidate, core_identity=core["snapshot_id"])
            equal = digest(cold_ref_rows) == digest(candidate_rows)
            amounts = [v["billed_bytes"] for v in candidate.telemetry["scan_evidence"].values()]
            if not amounts or any(v is None for v in amounts):
                raise RuntimeError("B8 unknown BigQuery billed bytes")
            billed += sum(amounts)
            evidence["samples"].append({
                "path": "bigquery-hybrid", "phase": phase,
                "elapsed_seconds": elapsed, "output_hash": digest(candidate_rows),
                "rows_equal": comparison, "screening_equal": equal,
                "telemetry": candidate.telemetry,
            })
            if billed > BUDGET or not (comparison["all_tables_equal"] and equal):
                break
            if phase == "warm":
                break
        if evidence["fallback_audit"] is None and len(evidence["samples"]) == 3:
            warm_ref, warm_ref_rows, warm_ref_elapsed = run_pyiceberg()
            warm_parity = compare_snapshots(cold_ref, warm_ref, core_identity=core["snapshot_id"])
            evidence["samples"].append({
                "path": "pyiceberg", "phase": "warm", "elapsed_seconds": warm_ref_elapsed,
                "output_hash": digest(warm_ref_rows), "rows_equal": warm_parity,
                "screening_equal": digest(cold_ref_rows) == digest(warm_ref_rows),
                "telemetry": warm_ref.telemetry,
            })
        evidence["total_billed_bytes"] = billed if any(
            item["path"] == "bigquery-hybrid" for item in evidence["samples"]
        ) else None
        candidates = [sample for sample in evidence["samples"] if sample["path"] == "bigquery-hybrid"]
        evidence["status"] = (
            "pass" if len(evidence["samples"]) == 4 and
            all(item.get("rows_equal", {}).get("all_tables_equal") and item.get("screening_equal")
                for item in evidence["samples"][1:]) and billed <= BUDGET
            else "partial"
        )
        # Two non-randomized observations are not a performance/FinOps cutover decision.
        evidence["candidate_count"] = len(candidates)
    finally:
        evidence["process_peak_rss_mib"] = _rss_mib()
        args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": evidence["status"], "samples": len(evidence["samples"]),
            "billed_bytes": evidence["total_billed_bytes"],
            "fallback_audit": evidence["fallback_audit"],
            "cutover": False,
        }, sort_keys=True))
    if evidence["status"] != "pass":
        raise RuntimeError("B8 matched screening fidelity/fallback gate is not PASS")


if __name__ == "__main__":
    main()
