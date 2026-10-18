"""Bounded dev maintenance for Core Iceberg tables."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

from .stage import GcsObjectStore


TABLE = "core.financials_v1"
TABLE_PREFIX = "warehouse/financials_v1/metadata/"
METADATA_HISTORY = "write.metadata.previous-versions-max"
DEFAULT_TARGET_FILE_SIZE = 128 * 1024 * 1024
DEFAULT_SMALL_FILE_SIZE = 32 * 1024 * 1024
DEFAULT_MAX_PARTITION_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_REWRITE_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_PERIODS = 48
DEFAULT_MIN_FILES = 4


def _references(store: GcsObjectStore, identifier: str = TABLE) -> tuple[set[int], set[str]]:
    snapshots: set[int] = set()
    metadata: set[str] = set()
    if not hasattr(store, "_maintenance_execution_documents"):
        store._maintenance_execution_documents = [json.loads(store.read(name)) for name in store.list("executions/")
                                                 if name.endswith(("/core-snapshot.json", "/manifest.json"))]
    for document in store._maintenance_execution_documents:
        reference = document.get("iceberg_tables", {}).get(identifier)
        if reference:
            snapshots.add(int(reference["snapshot_id"]))
            metadata.add(str(reference["metadata_location"]))
        for reference in document.get("reports", []):
            if reference.get("table_identifier") == identifier:
                snapshots.add(int(reference["iceberg_snapshot_id"]))
                metadata.add(str(reference["artifact_uri"]))
    return snapshots, metadata


def _keep_snapshots(table: Any, referenced: set[int], now: datetime) -> set[int]:
    snapshots = table.snapshots()
    available = {snapshot.snapshot_id for snapshot in snapshots}
    if not referenced <= available:
        raise RuntimeError("Core manifest references an unavailable financials snapshot")
    # A daily 90-day snapshot archive was retaining unused Iceberg file
    # versions long after the study/model or publication that used them ended.
    # Immutable PIT/research/ML references remain protected by _references()
    # and caller-provided protected_snapshot_ids. Preserve 24h for in-flight
    # readers and the current/named refs, never invent a 90-day research use.
    keep = set(referenced)
    recent_ms = int((now - timedelta(days=1)).timestamp() * 1000)
    for snapshot in snapshots:
        if snapshot.timestamp_ms >= recent_ms:
            keep.add(snapshot.snapshot_id)
    current = table.current_snapshot()
    if current:
        keep.add(current.snapshot_id)
    keep.update(reference.snapshot_id for reference in (table.metadata.refs or {}).values())
    return keep


def _protected_metadata(table: Any, bucket: str, referenced: set[str], identifier: str = TABLE) -> set[str]:
    prefix = f"gs://{bucket}/warehouse/{identifier.split('.')[1]}/metadata/"
    paths = {table.metadata_location, *referenced}
    paths.update(entry.metadata_file for entry in table.metadata.metadata_log)
    if any(not path.startswith(prefix) or not path.endswith(".metadata.json") for path in paths):
        raise RuntimeError("financials metadata reference escaped the dev table prefix")
    return {path.removeprefix(f"gs://{bucket}/") for path in paths}


def maintain_financials(*, core: Any, store: GcsObjectStore, apply: bool,
                        now: datetime | None = None, identifier: str = TABLE,
                        protected_snapshot_ids: set[int] | None = None,
                        protected_metadata: set[str] | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    allowed = {core.table_identifier(name) for name in core.IDENTIFIERS}
    # The controller audit journal lives in the Core bucket but is intentionally
    # not a canonical price/research dataset. It previously received neither
    # snapshot expiration nor orphan cleanup, despite daily compaction.
    if store.bucket == "gen-lang-client-0593591102-dev-core":
        allowed.add("ops.batch_events_v1")
    if identifier not in allowed:
        raise ValueError("maintenance table is outside the Core allowlist")
    table = core.catalog.load_table(identifier)
    table_prefix = f"warehouse/{identifier.split('.')[1]}/metadata/"
    original_snapshot = table.current_snapshot()
    original_rows = int(original_snapshot.summary["total-records"]) if original_snapshot else 0
    referenced_ids, referenced_metadata = _references(store, identifier)
    referenced_ids.update(protected_snapshot_ids or ())
    referenced_metadata.update(protected_metadata or ())
    keep = _keep_snapshots(table, referenced_ids, now)
    expire = sorted(snapshot.snapshot_id for snapshot in table.snapshots() if snapshot.snapshot_id not in keep)
    before_objects = store.objects(table_prefix)
    before = sum(int(item["size"]) for item in before_objects)

    if apply:
        if table.properties.get(METADATA_HISTORY) != "10":
            table.transaction().set_properties({METADATA_HISTORY: "10"}).commit_transaction()
            table = core.catalog.load_table(identifier)
        if expire:
            table.maintenance.expire_snapshots().by_ids(expire).commit()
            table = core.catalog.load_table(identifier)
        current_snapshot = table.current_snapshot()
        current_rows = int(current_snapshot.summary["total-records"]) if current_snapshot else 0
        if current_rows != original_rows:
            raise RuntimeError("financials row count changed during snapshot maintenance")
        actual_ids, actual_metadata = _references(store, identifier)
        if (actual_ids | set(protected_snapshot_ids or ()), actual_metadata | set(protected_metadata or ())) != (referenced_ids, referenced_metadata):
            raise RuntimeError("Core manifest references changed during maintenance")
        for snapshot_id in referenced_ids:
            table.scan(snapshot_id=snapshot_id, limit=1).to_arrow()

    protected = _protected_metadata(table, store.bucket, referenced_metadata, identifier)
    cutoff = now - timedelta(days=7)
    objects = store.objects(table_prefix) if apply else before_objects
    candidates = [item for item in objects
                  if item["name"].endswith(".metadata.json")
                  and item["name"] not in protected
                  and datetime.fromisoformat(item["updated"].replace("Z", "+00:00")) < cutoff]
    if apply:
        current = table.metadata_location
        for index, item in enumerate(candidates):
            if index % 50 == 0 and core.catalog.load_table(identifier).metadata_location != current:
                raise RuntimeError("financials catalog changed during metadata cleanup")
            store.delete(item["name"], generation=item["generation"])
        remaining = store.objects(table_prefix)
        if {item["name"] for item in candidates} & {item["name"] for item in remaining}:
            raise RuntimeError("metadata deletion readback mismatch")
        after = sum(int(item["size"]) for item in remaining)
        for snapshot_id in referenced_ids:
            table.scan(snapshot_id=snapshot_id, limit=1).to_arrow()
    else:
        after = before

    return {
        "component": "iceberg-maintenance", "table": identifier, "mode": "apply" if apply else "dry-run",
        "referenced_snapshots": len(referenced_ids), "kept_snapshots": len(keep),
        "expired_snapshots": len(expire) if apply else 0, "planned_expiration": len(expire),
        "deleted_metadata_json": len(candidates) if apply else 0,
        "planned_metadata_json": len(candidates), "active_metadata_bytes_before": before,
        "active_metadata_bytes_after": after,
        "active_bytes_reclaimed": before - after,
        "row_count": original_rows,
    }


def _integer_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _data_file_health(table: Any, *, target_bytes: int, small_bytes: int) -> dict[str, Any]:
    files = table.inspect.files().to_pylist()
    sizes = sorted(int(row.get("file_size_in_bytes") or 0) for row in files)
    manifests = table.inspect.manifests().to_pylist()
    current_spec = table.spec().spec_id
    legacy = sum(int(row.get("spec_id", current_spec)) != current_spec for row in files)
    snapshot = table.current_snapshot()
    return {
        "snapshot_id": snapshot.snapshot_id if snapshot else None,
        "row_count": int(snapshot.summary["total-records"]) if snapshot else 0,
        "spec_id": current_spec,
        "partition_fields": [field.name for field in table.spec().fields],
        "data_files": len(files),
        "legacy_spec_files": legacy,
        "small_files": sum(size < small_bytes for size in sizes),
        "total_data_bytes": sum(sizes),
        "min_file_bytes": sizes[0] if sizes else 0,
        "median_file_bytes": sizes[len(sizes) // 2] if sizes else 0,
        "max_file_bytes": sizes[-1] if sizes else 0,
        "manifest_files": len(manifests),
        "target_file_bytes": target_bytes,
        "small_file_threshold_bytes": small_bytes,
    }


def _time_partition_fields(table: Any, source_name: str, transform_name: str) -> dict[str, Any]:
    source = table.schema().find_field(source_name)
    fields: dict[str, Any] = {}
    for spec in table.specs().values():
        for field in spec.fields:
            if field.source_id == source.field_id and str(field.transform) == transform_name:
                fields[field.name] = field.transform
    return fields


def _logical_periods(table: Any, source_name: str, transform_name: str) -> list[dict[str, Any]]:
    partition_fields = _time_partition_fields(table, source_name, transform_name)
    if not partition_fields:
        return []
    source_type = table.schema().find_field(source_name).field_type
    grouped: dict[str, dict[str, int]] = {}
    for row in table.inspect.partitions().to_pylist():
        partition = row.get("partition") or {}
        label = None
        for name, transform in partition_fields.items():
            value = partition.get(name)
            if value is not None:
                label = transform.to_human_string(source_type, value)
                break
        if not label or label == "null":
            continue
        item = grouped.setdefault(label, {"file_count": 0, "bytes": 0, "record_count": 0})
        item["file_count"] += int(row.get("file_count") or 0)
        item["bytes"] += int(row.get("total_data_file_size_in_bytes") or 0)
        item["record_count"] += int(row.get("record_count") or 0)
    return [{"period": period, **values} for period, values in sorted(grouped.items())]


def _period_filter(table: Any, source_name: str, transform_name: str, period: str) -> Any:
    from pyiceberg.expressions import And, GreaterThanOrEqual, LessThan
    from pyiceberg.types import DateType

    source_type = table.schema().find_field(source_name).field_type
    is_date = isinstance(source_type, DateType)
    if transform_name == "month":
        year, month = (int(part) for part in period.split("-"))
        start_date = date(year, month, 1)
        end_date = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    elif transform_name == "year":
        year = int(period)
        start_date = date(year, 1, 1)
        end_date = date(year + 1, 1, 1)
    else:
        raise ValueError("compaction only supports month/year partitions")
    if is_date:
        start, end = start_date, end_date
    else:
        start = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
        end = datetime(end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc)
    return And(GreaterThanOrEqual(source_name, start), LessThan(source_name, end))


def _compaction_plan(table: Any, *, source_name: str, transform_name: str,
                     target_bytes: int, small_bytes: int, min_files: int,
                     max_partition_bytes: int, max_rewrite_bytes: int,
                     max_periods: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    del small_bytes  # Average size guards against compacting already healthy target-sized files.
    candidates = []
    oversized = []
    for period in _logical_periods(table, source_name, transform_name):
        count = period["file_count"]
        total = period["bytes"]
        average = total // count if count else 0
        if count < min_files or average >= target_bytes // 2:
            continue
        if total > max_partition_bytes:
            oversized.append(period)
            continue
        candidates.append(period)
    candidates.sort(key=lambda item: (-item["file_count"], item["period"]))
    planned = []
    planned_bytes = 0
    for item in candidates:
        if len(planned) >= max_periods or planned_bytes + item["bytes"] > max_rewrite_bytes:
            continue
        planned.append(item)
        planned_bytes += item["bytes"]
    return planned, oversized


def compact_core(*, core: Any, apply: bool) -> dict[str, Any]:
    """Compact fragmented time partitions without deleting retained snapshots.

    PyIceberg 0.11 does not expose a native rewrite-data-files action. We therefore
    rewrite one bounded logical month/year at a time through an Iceberg overwrite.
    The old snapshot remains addressable until normal snapshot retention expires it.
    """
    target_bytes = _integer_env("ICEBERG_TARGET_FILE_SIZE_BYTES", DEFAULT_TARGET_FILE_SIZE,
                                minimum=32 * 1024 * 1024, maximum=512 * 1024 * 1024)
    small_bytes = _integer_env("ICEBERG_SMALL_FILE_THRESHOLD_BYTES", DEFAULT_SMALL_FILE_SIZE,
                               minimum=1024 * 1024, maximum=target_bytes)
    max_partition_bytes = _integer_env("ICEBERG_COMPACTION_MAX_PARTITION_BYTES", DEFAULT_MAX_PARTITION_BYTES,
                                       minimum=target_bytes, maximum=2 * 1024 * 1024 * 1024)
    max_rewrite_bytes = _integer_env("ICEBERG_COMPACTION_MAX_REWRITE_BYTES", DEFAULT_MAX_REWRITE_BYTES,
                                     minimum=max_partition_bytes, maximum=8 * 1024 * 1024 * 1024)
    max_periods = _integer_env("ICEBERG_COMPACTION_MAX_PERIODS", DEFAULT_MAX_PERIODS, minimum=1, maximum=120)
    min_files = _integer_env("ICEBERG_COMPACTION_MIN_FILES", DEFAULT_MIN_FILES, minimum=2, maximum=1000)

    reports = []
    total_planned_bytes = 0
    total_rewritten_bytes = 0
    for dataset_id in core.IDENTIFIERS:
        if not core.table_exists(dataset_id):
            continue
        identifier = core.table_identifier(dataset_id)
        # Planning must never mutate the canonical catalog. Partition evolution
        # itself creates new Iceberg metadata and billable GCS operations.
        table = core.catalog.load_table(identifier)
        source_name, transform_name = core.PARTITIONS[dataset_id][0]
        before = _data_file_health(table, target_bytes=target_bytes, small_bytes=small_bytes)
        plan, oversized = _compaction_plan(
            table, source_name=source_name, transform_name=transform_name,
            target_bytes=target_bytes, small_bytes=small_bytes, min_files=min_files,
            max_partition_bytes=max_partition_bytes,
            max_rewrite_bytes=max(0, max_rewrite_bytes - total_planned_bytes),
            max_periods=max_periods,
        )
        total_planned_bytes += sum(item["bytes"] for item in plan)
        rewritten = []
        skipped_stale = []
        original_row_count = before["row_count"]

        if apply and plan:
            # Only evolve layout when an actual rewrite is required; health and
            # dry-run remain strictly read-only even on legacy partition specs.
            table = core._ensure_layout(table, dataset_id)
            for candidate in plan:
                table = core.catalog.load_table(identifier)
                row_filter = _period_filter(table, source_name, transform_name, candidate["period"])
                tasks = list(table.scan(row_filter=row_filter).plan_files())
                actual_bytes = sum(int(task.file.file_size_in_bytes) for task in tasks)
                if len(tasks) < min_files or actual_bytes > max_partition_bytes:
                    skipped_stale.append(candidate["period"])
                    continue
                old_snapshot = table.current_snapshot()
                data = table.scan(row_filter=row_filter).to_arrow()
                period_rows = len(data)
                if period_rows != candidate["record_count"]:
                    raise RuntimeError(f"{identifier} partition row count changed before compaction")
                table.overwrite(
                    data,
                    overwrite_filter=row_filter,
                    snapshot_properties={"janus.maintenance": "bounded-compaction-v1",
                                         "janus.compaction-period": candidate["period"]},
                )
                table = core.catalog.load_table(identifier)
                current = table.current_snapshot()
                if (int(current.summary["total-records"]) if current else 0) != original_row_count:
                    raise RuntimeError(f"{identifier} row count changed during compaction")
                if len(table.scan(row_filter=row_filter).to_arrow()) != period_rows:
                    raise RuntimeError(f"{identifier} compacted partition readback mismatch")
                if old_snapshot:
                    table.scan(snapshot_id=old_snapshot.snapshot_id, limit=1).to_arrow()
                rewritten.append({"period": candidate["period"], "old_files": len(tasks),
                                  "rows": period_rows, "bytes": actual_bytes,
                                  "old_snapshot_id": old_snapshot.snapshot_id if old_snapshot else None,
                                  "new_snapshot_id": current.snapshot_id if current else None})
                total_rewritten_bytes += actual_bytes

        if apply and plan:
            # No new snapshot was produced when the bounded plan is empty.
            # Reuse the already inspected state instead of reloading the table
            # and rescanning manifests solely to report identical "after".
            table = core.catalog.load_table(identifier)
            after = _data_file_health(table, target_bytes=target_bytes, small_bytes=small_bytes)
        else:
            after = before
        if apply and after["row_count"] != original_row_count:
            raise RuntimeError(f"{identifier} final row count changed during compaction")
        reports.append({
            "dataset_id": dataset_id,
            "table": identifier,
            "source_partition": f"{transform_name}({source_name})",
            "before": before,
            "planned_periods": plan,
            "oversized_periods": oversized,
            "rewritten_periods": rewritten,
            "skipped_stale_periods": skipped_stale,
            "after": after,
        })

    return {
        "component": "iceberg-compaction",
        "mode": "compact-apply" if apply else "compact-dry-run",
        "target_file_bytes": target_bytes,
        "small_file_threshold_bytes": small_bytes,
        "max_partition_bytes": max_partition_bytes,
        "max_rewrite_bytes": max_rewrite_bytes,
        "planned_rewrite_bytes": total_planned_bytes,
        "rewritten_bytes": total_rewritten_bytes,
        "tables": reports,
    }



def compact_batch_events(*, core: Any, apply: bool) -> dict[str, Any]:
    """Bounded unpartitioned controller audit compaction; no snapshot expiration."""
    identifier = "ops.batch_events_v1"
    if not core.catalog.table_exists(identifier):
        return {"table": identifier, "status": "missing", "planned_files": 0}
    table = core.catalog.load_table(identifier)
    if table.spec().fields:
        raise RuntimeError("audit table partition schema changed")
    files = table.inspect.files().to_pylist()
    before_files = len(files)
    before_bytes = sum(int(item.get("file_size_in_bytes") or 0) for item in files)
    eligible = 4 <= before_files <= 1000 and before_bytes <= 32 * 1024 * 1024
    result = {"table": identifier, "mode": "apply" if apply else "dry-run",
              "status": "eligible" if eligible else "skipped_bounds",
              "before_files": before_files, "before_bytes": before_bytes,
              "planned_files": before_files if eligible else 0}
    if not eligible or not apply:
        return result
    pointer = table.metadata_location
    old_snapshot = table.current_snapshot()
    source = table.scan().to_arrow()
    if len(source) > 100000:
        raise RuntimeError("audit compaction row limit exceeded")
    rows = source.to_pylist()
    original = {row["event_id"]: row for row in rows}
    if len(original) != len(rows):
        raise RuntimeError("audit event IDs not unique")
    if core.catalog.load_table(identifier).metadata_location != pointer:
        raise RuntimeError("audit catalog changed during compaction preflight")
    table.overwrite(source, snapshot_properties={"janus.maintenance": "bounded-audit-compaction-v1"})
    updated = core.catalog.load_table(identifier)
    actual = updated.scan().to_arrow().to_pylist()
    if len(actual) != len(rows) or {row["event_id"]: row for row in actual} != original:
        raise RuntimeError("audit compaction readback mismatch")
    if old_snapshot:
        updated.scan(snapshot_id=old_snapshot.snapshot_id, limit=1).to_arrow()
    result.update(status="rewritten", after_files=len(updated.inspect.files().to_pylist()),
                  row_count=len(rows), old_snapshot_id=old_snapshot.snapshot_id if old_snapshot else None)
    return result


def verify_compaction_eod_fence(*, core: Any) -> dict[str, Any]:
    """Recheck the controller's immutable EOD receipt against the live Core catalog.

    A single manifest GET is permitted; full-bucket inventory is not. Old daily
    executions have no FINOPS_SOURCE_* overrides and retain their old behavior.
    Any partially supplied weekly tuple fails closed before an Iceberg rewrite.
    """
    from hashlib import sha256
    import re

    names = ("FINOPS_SOURCE_CORE_SNAPSHOT_ID", "FINOPS_SOURCE_CORE_SNAPSHOT_URI",
             "FINOPS_SOURCE_EOD_DATE")
    values = [os.environ.get(name, "").strip() for name in names]
    if not any(values):
        return {"status": "legacy_daily_no_weekly_fence"}
    if not all(values):
        raise RuntimeError("weekly_eod_core_fence_incomplete")
    expected, uri, day = values
    bucket = os.environ.get("CORE_BUCKET", "")
    prefix = f"gs://{bucket}/executions/"
    if (bucket != "gen-lang-client-0593591102-dev-core"
            or re.fullmatch(r"sha256:[0-9a-f]{64}", expected) is None
            or re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", day) is None
            or not uri.startswith(prefix)
            or re.fullmatch(r"[A-Za-z0-9._-]+/core-snapshot[.]json", uri[len(prefix):]) is None):
        raise RuntimeError("weekly_eod_core_fence_invalid")
    manifest = json.loads(GcsObjectStore(bucket).read(uri.removeprefix(f"gs://{bucket}/")))
    tables = manifest.get("iceberg_tables")
    if (manifest.get("artifact_kind") != "core_snapshot_v1"
            or manifest.get("analysis_as_of") != day
            or not isinstance(tables, dict) or not tables):
        raise RuntimeError("weekly_eod_core_manifest_invalid")
    canonical = json.dumps(tables, sort_keys=True, separators=(",", ":")).encode()
    actual_hash = "sha256:" + sha256(canonical).hexdigest()
    if manifest.get("snapshot_id") != expected or actual_hash != expected:
        raise RuntimeError("weekly_eod_core_snapshot_digest_mismatch")
    for identifier, item in tables.items():
        if (identifier not in {core.table_identifier(name) for name in core.IDENTIFIERS}
                or not isinstance(item, dict)
                or not isinstance(item.get("snapshot_id"), int)):
            raise RuntimeError("weekly_eod_core_manifest_table_invalid")
        snapshot = core.catalog.load_table(identifier).current_snapshot()
        if snapshot is None or snapshot.snapshot_id != item["snapshot_id"]:
            raise RuntimeError("weekly_eod_core_catalog_changed")
    return {"status": "verified", "core_snapshot_id": expected,
            "source_date": day, "verified_tables": len(tables)}


def compact_nightly(*, core: Any) -> dict[str, Any]:
    """Plan canonical Core once; skip no-op writes and the retired audit mirror.

    D06 already stopped all batch-event Iceberg exports. Its historical table is
    handled by the separate reference-protected audit cleanup, not rewritten or
    repeatedly scanned on each ordinary Core maintenance occurrence.
    """
    source_fence = verify_compaction_eod_fence(core=core)
    core_plan = compact_core(core=core, apply=False)
    audit_disabled = {"table": "ops.batch_events_v1", "status": "disabled",
                      "planned_files": 0, "rewritten_files": 0}
    candidates = sum(len(t["planned_periods"]) for t in core_plan["tables"])
    print(json.dumps({
        "component": "iceberg-nightly-preflight",
        "mode": "compact-dry-run",
        "core_candidate_periods": candidates,
        "planned_rewrite_bytes": core_plan["planned_rewrite_bytes"],
        "audit_planned_files": 0,
        "audit_status": "disabled",
    }, sort_keys=True), flush=True)
    if candidates:
        core_result = compact_core(core=core, apply=True)
        mode = "dry-run-then-apply"
    else:
        # Dry-run is already a read-only health snapshot. No second load/scan,
        # metadata commit or compaction write when there are no dirty periods.
        core_result = {**core_plan, "mode": "skipped_no_work",
                       "reason": "no_fragmented_periods"}
        mode = "skipped_no_work"
    return {"component": "iceberg-nightly-compaction", "mode": mode,
            "source_fence": source_fence,
            "preflight": {"core": core_plan, "audit": audit_disabled},
            "apply": {"core": core_result, "audit": audit_disabled}}



def cleanup_controller_audit_only(*, core: Any, store: GcsObjectStore) -> dict[str, Any]:
    """Expire unreferenced historical audit snapshots, never Core market data.

    The PostgreSQL controller outbox is authoritative; this table is a
    reproducible, delayed journal mirror. Immutable PIT/model Core manifests
    are neither modified nor retired by this operation.
    """
    identifier = "ops.batch_events_v1"
    if store.bucket != "gen-lang-client-0593591102-dev-core":
        raise ValueError("audit cleanup outside existing dev Core bucket")
    if not core.catalog.table_exists(identifier):
        return {"component": "iceberg-audit-only-cleanup", "mode": "audit-cleanup",
                "status": "no-audit-table", "table": identifier,
                "deleted_objects": 0, "expired_snapshots": 0}
    from .retention import clean_orphans
    prefix = "warehouse/batch_events_v1/"
    before_objects = store.objects(prefix)
    before_bytes = sum(int(obj["size"]) for obj in before_objects)
    maintenance = maintain_financials(core=core, store=store, apply=True,
                                      identifier=identifier)
    orphans = clean_orphans(core, store, identifier, apply=True,
                            now=datetime.now(timezone.utc))
    remaining = store.objects(prefix)
    after_bytes = sum(int(obj["size"]) for obj in remaining)
    return {"component": "iceberg-audit-only-cleanup", "mode": "audit-cleanup",
            "status": "PASS", "table": identifier,
            "maintenance": maintenance, "orphans": orphans,
            "before": {"objects": len(before_objects), "bytes": before_bytes},
            "after": {"objects": len(remaining), "bytes": after_bytes},
            "deleted_objects": len(before_objects) - len(remaining),
            "expired_snapshots": maintenance["expired_snapshots"],
            "canonical_tables_modified": 0, "core_execution_manifests_deleted": 0}


def core_health(*, core: Any) -> dict[str, Any]:
    target_bytes = _integer_env("ICEBERG_TARGET_FILE_SIZE_BYTES", DEFAULT_TARGET_FILE_SIZE,
                                minimum=32 * 1024 * 1024, maximum=512 * 1024 * 1024)
    small_bytes = _integer_env("ICEBERG_SMALL_FILE_THRESHOLD_BYTES", DEFAULT_SMALL_FILE_SIZE,
                               minimum=1024 * 1024, maximum=target_bytes)
    tables = []
    for dataset_id in core.IDENTIFIERS:
        if not core.table_exists(dataset_id):
            continue
        table = core.catalog.load_table(core.table_identifier(dataset_id))
        tables.append({"dataset_id": dataset_id, "table": core.table_identifier(dataset_id),
                       **_data_file_health(table, target_bytes=target_bytes, small_bytes=small_bytes)})
    return {"component": "iceberg-health", "tables": tables,
            "data_files": sum(item["data_files"] for item in tables),
            "small_files": sum(item["small_files"] for item in tables),
            "legacy_spec_files": sum(item["legacy_spec_files"] for item in tables),
            "total_data_bytes": sum(item["total_data_bytes"] for item in tables)}


def run(mode: str) -> dict[str, Any]:
    supported = {"dry-run", "apply", "retention-dry-run", "retention-apply",
                 "health", "compact-dry-run", "compact-apply", "compact-nightly", "cost-inventory", "audit-cleanup"}
    if mode not in supported:
        raise ValueError("unsupported Iceberg maintenance mode")
    bucket = os.environ.get("CORE_BUCKET", "").strip()
    if bucket != "gen-lang-client-0593591102-dev-core":
        raise ValueError("Iceberg maintenance is restricted to the existing dev Core bucket")
    if mode == "cost-inventory":
        # No catalog access, mutation lock, snapshots, or per-object GET calls.
        return {"component": "iceberg-cost-inventory", "mode": "read-only",
                **GcsObjectStore(bucket).bounded_inventory(max_pages=_integer_env(
                    "ICEBERG_INVENTORY_MAX_PAGES", 10, minimum=1, maximum=25))}
    from .__main__ import _iceberg_core

    core = _iceberg_core(bucket)
    try:
        with core.mutation_lock():
            if mode.startswith("retention-"):
                from .retention import maintain_public_data
                return maintain_public_data(core=core, apply=mode == "retention-apply")
            if mode == "health":
                return core_health(core=core)
            if mode == "audit-cleanup":
                return cleanup_controller_audit_only(core=core, store=GcsObjectStore(bucket))
            if mode == "compact-nightly":
                return compact_nightly(core=core)
            if mode.startswith("compact-"):
                return compact_core(core=core, apply=mode == "compact-apply")
            return maintain_financials(core=core, store=GcsObjectStore(bucket), apply=mode == "apply")
    except Exception as error:
        frame = traceback.extract_tb(error.__traceback__)[-1]
        print(json.dumps({"component": "iceberg-maintenance", "status": "failed",
                          "error_code": type(error).__name__.upper(),
                          "error_location": f"{Path(frame.filename).name}:{frame.lineno}"}), file=sys.stderr)
        raise
    finally:
        core.close()
