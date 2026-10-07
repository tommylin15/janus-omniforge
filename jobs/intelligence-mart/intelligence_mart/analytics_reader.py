"""Exact-snapshot analytics read boundary for specialist workloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


__all__ = ("AnalyticsSnapshot", "AnalyticsSnapshotReader", "IcebergSnapshotReader")


@dataclass(frozen=True)
class AnalyticsSnapshot:
    """One bounded analytics read tied to an explicit immutable Core snapshot."""

    core_snapshot_id: str
    datasets: dict[str, list[dict[str, Any]]]
    telemetry: dict[str, Any]


@runtime_checkable
class AnalyticsSnapshotReader(Protocol):
    """Backend-neutral exact-snapshot reader contract used by specialist runtime."""

    def read(
        self,
        manifest: dict[str, Any],
        requested_symbols: tuple[str, ...],
        *,
        core_snapshot_id: str,
        row_limit: int = 250_000,
    ) -> AnalyticsSnapshot:
        ...

    def close(self) -> None:
        ...


class IcebergSnapshotReader:
    """Reference/fallback reader over the existing PyIceberg catalog."""

    backend = "pyiceberg"

    def __init__(self, catalog: Any, *, date_bounds=None, selected_fields=None):
        self.catalog = catalog
        self.date_bounds = date_bounds or {}
        self.selected_fields = selected_fields or {}

    def read(
        self,
        manifest: dict[str, Any],
        requested_symbols: tuple[str, ...],
        *,
        core_snapshot_id: str,
        row_limit: int = 250_000,
    ) -> AnalyticsSnapshot:
        identity = str(core_snapshot_id).strip()
        if not identity:
            raise ValueError("core_snapshot_id is required")
        manifest_identity = str(manifest.get("snapshot_id", "")).strip()
        if not manifest_identity:
            raise ValueError("Core manifest is missing immutable snapshot identity")
        if manifest_identity != identity:
            raise ValueError("Core snapshot identity mismatch")
        if row_limit <= 0:
            raise ValueError("row_limit must be positive")

        datasets, telemetry = self._read_datasets(manifest, requested_symbols, row_limit=row_limit)
        telemetry["core_snapshot_id"] = identity
        return AnalyticsSnapshot(core_snapshot_id=identity, datasets=datasets, telemetry=telemetry)

    def close(self) -> None:
        engine = getattr(self.catalog, "engine", None)
        if engine is not None:
            engine.dispose()

    def _read_datasets(
        self,
        manifest: dict[str, Any],
        requested_symbols: tuple[str, ...],
        *,
        row_limit: int,
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        embedded = manifest.get("datasets")
        if embedded is not None:
            if not isinstance(embedded, dict) or any(
                not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                for rows in embedded.values()
            ):
                raise ValueError("Core manifest datasets must be arrays")
            if sum(map(len, embedded.values())) > row_limit:
                raise ValueError("Core snapshot row limit exceeded")
            result = {str(name): [dict(row) for row in rows] for name, rows in embedded.items()}
            rows_by_dataset = {name: len(rows) for name, rows in sorted(result.items())}
            return result, {
                "source": "embedded",
                "rows_by_dataset": rows_by_dataset,
                "total_rows": sum(rows_by_dataset.values()),
                "scan_evidence": {},
            }

        tables = manifest.get("iceberg_tables", {})
        if not isinstance(tables, dict):
            raise ValueError("Core manifest iceberg_tables must be an object")

        from pyiceberg.expressions import And, In, GreaterThanOrEqual, LessThanOrEqual

        datasets: dict[str, list[dict[str, Any]]] = {}
        scan_evidence: dict[str, dict[str, Any]] = {}
        remaining = row_limit
        for identifier, fence in sorted(tables.items()):
            if remaining <= 0:
                raise ValueError("Core snapshot row limit exceeded")
            if not isinstance(fence, dict) or fence.get("snapshot_id") is None:
                raise ValueError("Core table is missing an immutable snapshot ID")
            if not str(identifier).startswith("core.") or not str(identifier).endswith("_v1"):
                raise ValueError("Core manifest contains a non-Core table")
            dataset_id = str(identifier).split(".", 1)[1][:-3].replace("_", "-")
            table = self.catalog.load_table(identifier)
            field_names = {field.name for field in table.schema().fields}
            filter_ = In("symbol", set(requested_symbols)) if requested_symbols and "symbol" in field_names else None
            if identifier in self.date_bounds:
                column, start, end = self.date_bounds[identifier]
                from datetime import date
                if column not in field_names or date.fromisoformat(start) > date.fromisoformat(end):
                    raise ValueError("invalid analytics date bounds")
                date_filter = And(GreaterThanOrEqual(column, start), LessThanOrEqual(column, end))
                filter_ = And(filter_, date_filter) if filter_ is not None else date_filter
            # Read one extra row to detect overflow rather than silently truncate a fixed snapshot.
            scan_options: dict[str, Any] = {"snapshot_id": int(fence["snapshot_id"]), "limit": remaining + 1}
            if filter_ is not None:
                scan_options["row_filter"] = filter_
            if identifier in self.selected_fields:
                selected = tuple(c for c in self.selected_fields[identifier] if c in field_names)
                if not selected:
                    raise ValueError("empty analytics column selection")
                scan_options["selected_fields"] = selected
            scan = table.scan(**scan_options)
            planned_file_count = None
            planned_scan_bytes = None
            planning_error_code = None
            try:
                tasks = list(scan.plan_files())
                planned_file_count = len(tasks)
                task_lengths = [getattr(task, "length", None) for task in tasks]
                if all(isinstance(length, int) and length >= 0 for length in task_lengths):
                    planned_scan_bytes = sum(task_lengths)
            except Exception as error:  # telemetry is best-effort and must not change the read path
                planning_error_code = type(error).__name__.upper()[:64]

            rows = scan.to_arrow().to_pylist()
            remaining -= len(rows)
            if remaining < 0:
                raise ValueError("Core snapshot row limit exceeded")
            datasets[dataset_id] = [
                dict(row, __table_identifier=identifier, __snapshot_id=fence["snapshot_id"])
                for row in rows
            ]
            scan_evidence[dataset_id] = {
                "table_identifier": str(identifier),
                "snapshot_id": int(fence["snapshot_id"]),
                "row_count": len(rows),
                "symbol_filter_applied": filter_ is not None,
                "planned_file_count": planned_file_count,
                "planned_scan_bytes": planned_scan_bytes,
                "actual_gcs_read_bytes": None,
                "planning_error_code": planning_error_code,
            }

        rows_by_dataset = {name: len(rows) for name, rows in sorted(datasets.items())}
        return datasets, {
            "source": self.backend,
            "rows_by_dataset": rows_by_dataset,
            "total_rows": sum(rows_by_dataset.values()),
            "scan_evidence": scan_evidence,
        }
