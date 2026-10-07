"""Read-only liquid-500 canary on existing B2 shared mappings; no cutover."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "jobs/intelligence-mart")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    b2 = runpy.run_path(str(ROOT / "scripts/gcp/b2-lakehouse-acceptance.py"))
    from google.cloud import bigquery
    from google.oauth2.credentials import Credentials
    from pyiceberg.table import StaticTable
    from intelligence_mart.analytics_reader import IcebergSnapshotReader
    from intelligence_mart.bigquery_reader import BigQueryAnalyticsReader
    from intelligence_mart.facts import canonical_json
    from intelligence_mart.market_screening import FIELDS, read_plan, market_features
    from intelligence_mart.specialists import digest, screening_quality

    core, manifest_hash = b2["gcs_json"](b2["CORE_MANIFEST_URI"])
    if manifest_hash != b2["CORE_MANIFEST_SHA256"] or core["snapshot_id"] != b2["CORE_SNAPSHOT_ID"]:
        raise ValueError("fixed Core manifest fence mismatch")
    membership, _ = b2["gcs_json"](
        f"gs://{b2['MART_BUCKET']}/executions/3ece7127-9c04-4e00-aff3-21de583bcf36/market-membership.json")
    symbols = tuple(membership["symbols"])
    if len(symbols) != 500 or len(set(symbols)) != 500 or membership["analysis_as_of"] != core["analysis_as_of"]:
        raise ValueError("fixed liquid-500 membership mismatch")
    token = b2["token"]()
    properties = {"gcs.oauth2.token": token, "gcs.oauth2.token-expires-at": str(int((time.time() + 3000) * 1000))}
    tables = {}
    class Catalog:
        def load_table(self, identifier):
            if identifier not in tables:
                tables[identifier] = StaticTable.from_metadata(core["iceberg_tables"][identifier]["metadata_location"], properties=properties)
            return tables[identifier]
    catalog = Catalog()
    inputs, bounds = read_plan(core, core["analysis_as_of"])
    selected = {k: tuple(c for c in FIELDS[k] if c in {f.name for f in catalog.load_table(k).schema().fields}) for k in bounds}
    reference = IcebergSnapshotReader(catalog, date_bounds=bounds, selected_fields=selected)
    started = time.monotonic()
    ref = reference.read(inputs, symbols, core_snapshot_id=core["snapshot_id"], row_limit=150_000)
    ref_rows = market_features(ref.datasets, symbols, core["analysis_as_of"], core["snapshot_id"])
    reference_elapsed = time.monotonic() - started
    # Existing B2 shared mappings cover price/benchmark. Valuation stays on PyIceberg.
    scope = ("core.ohlcv_v1", "core.benchmark_v1")
    mapping = {k: f"{b2['PROJECT']}.{b2['CATALOG']}.{b2['CORE_NAMESPACE']}.{k.split('.')[1]}" for k in scope}
    client = bigquery.Client(project=b2["PROJECT"], credentials=Credentials(token), location="US")
    def pointer(table_id):
        _, _, namespace, table = table_id.split(".")
        return b2["metadata_location"](b2["load_table"](table, namespace))
    reader = BigQueryAnalyticsReader(client, catalog, mapping, location="US",
        date_bounds={k: bounds[k] for k in scope}, selected_fields={k: selected[k] for k in scope},
        shared_metadata_loader=pointer)
    started = time.monotonic()
    try:
        candidate = reader.probe(inputs, symbols, core_snapshot_id=core["snapshot_id"], row_limit=150_000,
                                 table_scope=scope, dry_run=False)
    finally:
        reader.close()
    # Reuse only the bounded valuation read, never copy it into BigQuery.
    datasets = {**candidate.datasets, "valuation": ref.datasets.get("valuation", [])}
    cand_rows = market_features(datasets, symbols, core["analysis_as_of"], core["snapshot_id"])
    candidate_elapsed = time.monotonic() - started
    comparisons = {}
    for name in candidate.datasets:
        equal = Counter(canonical_json(r) for r in ref.datasets[name]) == Counter(canonical_json(r) for r in candidate.datasets[name])
        comparisons[name] = {"row_multiset_equal": equal, "rows": len(candidate.datasets[name])}
    equal = digest(ref_rows) == digest(cand_rows)
    evidence = {"status": "pass" if equal and all(r["row_multiset_equal"] for r in comparisons.values()) else "failed",
                "core_snapshot_id": core["snapshot_id"], "manifest_sha256": manifest_hash,
                "membership": membership, "output_equal": equal, "output_hash": digest(ref_rows),
                "comparison": comparisons, "screening_count": len(ref_rows), "quality": screening_quality(ref_rows),
                "pyiceberg_elapsed_seconds": reference_elapsed, "bigquery_hybrid_elapsed_seconds": candidate_elapsed,
                "valuation_backend": "pyiceberg_shared_bounded_read", "valuation_read_time_excluded_from_candidate": True,
                "pyiceberg_telemetry": ref.telemetry, "bigquery_telemetry": candidate.telemetry,
                "host_peak_rss_mib": None, "actual_gcs_read_bytes": None,
                "default": "pyiceberg", "cutover": False, "llm_api_tokens": 0, "specialist_count": 0}
    args.output.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: evidence[k] for k in ("status", "screening_count", "output_equal", "comparison", "pyiceberg_elapsed_seconds", "bigquery_hybrid_elapsed_seconds", "cutover")}))
    if evidence["status"] != "pass":
        raise RuntimeError("screening canary fidelity failed")


if __name__ == "__main__":
    main()
