"""Opt-in bounded legacy/shared-catalog reads; no automatic default cutover."""

from __future__ import annotations

import json
import re
from datetime import date
from time import monotonic
from typing import Any

from .analytics_reader import AnalyticsSnapshot


class BigQueryAnalyticsReader:
    backend = "bigquery-compatibility"

    def __init__(self, client: Any, catalog: Any, table_ids: dict[str, str], *,
                 location: str, maximum_bytes_billed: int = 1_073_741_824,
                 date_bounds: dict[str, tuple[str, str, str]], timeout: float = 60,
                 selected_fields=None, shared_metadata_loader=None):
        if not location or not 0 < maximum_bytes_billed <= 1_073_741_824 or not 0 < timeout <= 60:
            raise ValueError("location, execution byte budget <=1 GiB and timeout <=60s required")
        self.client, self.catalog, self.table_ids = client, catalog, dict(table_ids)
        self.location, self.maximum_bytes_billed, self.timeout = location, maximum_bytes_billed, timeout
        self.date_bounds = dict(date_bounds)
        self.selected_fields = selected_fields or {}
        self.shared_metadata_loader = shared_metadata_loader

    def close(self) -> None:
        self.client.close()

    def _mapping_unchanged(self, identifier, fence, external):
        table_id = self.table_ids[identifier]
        if self.shared_metadata_loader is not None:
            return self.shared_metadata_loader(table_id) == fence["metadata_location"]
        return self.client.get_table(table_id).etag == external.etag

    def read(self, manifest: dict[str, Any], requested_symbols: tuple[str, ...], *,
             core_snapshot_id: str, row_limit: int = 250_000) -> AnalyticsSnapshot:
        return self.probe(manifest, requested_symbols, core_snapshot_id=core_snapshot_id,
                          row_limit=row_limit, dry_run=False)

    def probe(self, manifest: dict[str, Any], requested_symbols: tuple[str, ...], *,
              core_snapshot_id: str, row_limit: int = 250_000,
              dry_run: bool = True, table_scope: tuple[str, ...] | None = None) -> AnalyticsSnapshot:
        if not core_snapshot_id or manifest.get("snapshot_id") != core_snapshot_id:
            raise ValueError("Core snapshot identity mismatch")
        if row_limit <= 0 or len(requested_symbols) > 500:
            raise ValueError("positive row limit and at most 500 symbols required")
        fences = manifest.get("iceberg_tables")
        if not isinstance(fences, dict) or not fences:
            raise ValueError("Core table fences required")
        if table_scope is not None:
            if not table_scope or not set(table_scope) <= set(fences):
                raise ValueError("invalid probe table scope")
            fences = {k: fences[k] for k in table_scope}
        if set(fences) != set(self.table_ids):
            raise ValueError("existing BigQuery mapping must cover exactly the Core manifest")

        # Validate every fence before submitting any job. Never substitute latest.
        plans = []
        for identifier, fence in sorted(fences.items()):
            table_id = self.table_ids[identifier]
            if not re.fullmatch(r"core\.[a-z][a-z0-9_]*_v1", identifier):
                raise ValueError("non-Core table")
            if not re.fullmatch(r"[a-z][a-z0-9-]*(?:\.[A-Za-z0-9_]+){2,3}", table_id):
                raise ValueError("invalid BigQuery table ID")
            uri = fence.get("metadata_location", "") if isinstance(fence, dict) else ""
            if not re.fullmatch(r"gs://[^/]+/.*/[0-9]+-[0-9a-f-]{36}\.metadata\.json", uri):
                raise ValueError("immutable versioned Iceberg metadata URI required")
            table = self.catalog.load_table(identifier)
            with table.io.new_input(uri).open() as stream:
                metadata = json.load(stream)
            if metadata.get("format-version") != 2 or metadata.get("current-snapshot-id") != fence.get("snapshot_id"):
                raise ValueError("metadata does not prove the exact Iceberg V2 snapshot")
            schema = next((s for s in metadata["schemas"]
                           if s["schema-id"] == metadata["current-schema-id"]), None)
            if schema is None:
                raise ValueError("missing snapshot schema")
            columns = [f["name"] for f in schema["fields"]]
            if not columns or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", c) for c in columns):
                raise ValueError("unsupported Core column identifier")
            bound = self.date_bounds.get(identifier)
            if bound is None or len(bound) != 3 or bound[0] not in columns:
                raise ValueError("explicit date/partition bounds required for every table")
            start, end = date.fromisoformat(bound[1]), date.fromisoformat(bound[2])
            if start > end:
                raise ValueError("invalid date interval")
            if self.shared_metadata_loader is not None:
                if table_id.count(".") != 3 or self.shared_metadata_loader(table_id) != uri:
                    raise ValueError("shared catalog exact metadata mapping mismatch")
                external = None
            else:
                if table_id.count(".") != 2:
                    raise ValueError("shared catalog mapping validator required")
                external = self.client.get_table(table_id)
                config = external.external_data_configuration
                if (external.location.lower() != self.location.lower() or config is None
                        or config.source_format != "ICEBERG" or config.source_uris != [uri]
                        or not external.etag):
                    raise ValueError("BigQuery region or exact metadata mapping mismatch")
                if [f.name for f in external.schema] != columns:
                    raise ValueError("BigQuery schema evolution mismatch")
            selected = self.selected_fields.get(identifier, columns)
            if not selected or not set(selected) <= set(columns):
                raise ValueError("selected columns missing from pinned schema")
            if bound[0] not in selected or ("symbol" in columns and "symbol" not in selected):
                raise ValueError("selected columns must preserve date and symbol predicates")
            columns = list(selected)
            plans.append((identifier, fence, columns, external))

        from google.cloud import bigquery

        datasets, evidence, queries = {}, {}, []
        estimated_total = 0
        for identifier, fence, columns, external in plans:
            params = []
            column, start, end = self.date_bounds[identifier]
            predicate = f" WHERE DATE(`{column}`) >= DATE '{date.fromisoformat(start).isoformat()}' AND DATE(`{column}`) <= DATE '{date.fromisoformat(end).isoformat()}'"
            if requested_symbols and "symbol" in columns:
                predicate += " AND `symbol` IN UNNEST(@symbols)"
                params.append(bigquery.ArrayQueryParameter("symbols", "STRING", list(requested_symbols)))
            sql = ("SELECT " + ", ".join(f"`{c}`" for c in columns)
                   + f" FROM `{self.table_ids[identifier]}`" + predicate + f" LIMIT {row_limit + 1}")
            estimate = self.client.query(sql, location=self.location, timeout=self.timeout,
                job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False, query_parameters=params))
            estimated = estimate.total_bytes_processed
            # External-source dry runs can be a lower bound. Zero is not proof of a free scan.
            known_estimate = estimated is not None and estimated > 0
            if known_estimate:
                estimated_total += estimated
            if estimated_total > self.maximum_bytes_billed:
                raise ValueError("query byte budget exceeded")
            dataset = identifier.split(".", 1)[1][:-3].replace("_", "-")
            item = {"table_identifier": identifier, "snapshot_id": fence["snapshot_id"],
                    "metadata_location": fence["metadata_location"], "region": self.location,
                    "estimated_bytes": estimated if known_estimate else None,
                    "dry_run_lower_bound_bytes": estimated, "processed_bytes": None, "billed_bytes": None,
                    "elapsed_seconds": None, "actual_gcs_read_bytes": None,
                    "partition_pruning": "unknown", "selected_columns": columns}
            evidence[dataset] = item
            queries.append((identifier, fence, external, sql, params, dataset, item))
        remaining, billed_total = row_limit, 0
        for identifier, fence, external, sql, params, dataset, item in ([] if dry_run else queries):
            if remaining <= 0 or billed_total >= self.maximum_bytes_billed:
                raise ValueError("Core snapshot row or query byte budget exceeded")
            started = monotonic()
            job = self.client.query(sql, location=self.location, timeout=self.timeout,
                job_config=bigquery.QueryJobConfig(use_query_cache=False, query_parameters=params,
                    maximum_bytes_billed=self.maximum_bytes_billed - billed_total))
            try:
                rows = [dict(row.items()) for row in job.result(timeout=self.timeout)]
            except Exception:
                try:
                    job.cancel()
                except Exception:
                    pass  # Preserve the read failure if cancellation also fails.
                raise
            if not self._mapping_unchanged(identifier, fence, external):
                raise ValueError("BigQuery metadata mapping changed during probe")
            remaining -= len(rows)
            if remaining < 0:
                raise ValueError("Core snapshot row limit exceeded")
            if job.total_bytes_billed is None:
                raise ValueError("billed bytes unknown; further queries blocked")
            billed_total += job.total_bytes_billed
            if billed_total > self.maximum_bytes_billed:
                raise ValueError("actual billed bytes exceeded execution budget")
            datasets[dataset] = [dict(row, __table_identifier=identifier, __snapshot_id=fence["snapshot_id"])
                                 for row in rows]
            item.update(processed_bytes=job.total_bytes_processed, billed_bytes=job.total_bytes_billed,
                        elapsed_seconds=monotonic() - started, row_count=len(rows))
        if not dry_run:
            for identifier, fence, _, external in plans:
                if not self._mapping_unchanged(identifier, fence, external):
                    raise ValueError("BigQuery metadata mapping changed before snapshot completion")
        return AnalyticsSnapshot(core_snapshot_id, datasets, {
            "source": self.backend, "core_snapshot_id": core_snapshot_id, "dry_run": dry_run,
            "transition_only": self.shared_metadata_loader is None, "scan_evidence": evidence,
            "unknown_estimate_policy": "bounded-execution",
            "execution_byte_budget": self.maximum_bytes_billed,
            "table_scope": sorted(fences),
            "rows_by_dataset": {k: len(v) for k, v in datasets.items()},
            "total_rows": sum(map(len, datasets.values())) if not dry_run else None,
        })
