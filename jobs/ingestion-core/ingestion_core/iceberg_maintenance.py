"""Bounded dev maintenance for the Core financials table."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any

from .stage import GcsObjectStore


TABLE = "core.financials_v1"
TABLE_PREFIX = "warehouse/financials_v1/metadata/"
METADATA_HISTORY = "write.metadata.previous-versions-max"


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
    latest_by_day: dict[str, Any] = {}
    keep = set(referenced)
    recent_ms = int((now - timedelta(days=1)).timestamp() * 1000)
    for snapshot in snapshots:
        day = datetime.fromtimestamp(snapshot.timestamp_ms / 1000, timezone.utc).date().isoformat()
        previous = latest_by_day.get(day)
        if previous is None or snapshot.timestamp_ms > previous.timestamp_ms:
            latest_by_day[day] = snapshot
        if snapshot.timestamp_ms >= recent_ms:
            keep.add(snapshot.snapshot_id)
    daily_ms = int((now - timedelta(days=90)).timestamp() * 1000)
    keep.update(snapshot.snapshot_id for snapshot in latest_by_day.values() if snapshot.timestamp_ms >= daily_ms)
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
    if identifier not in {core.table_identifier(name) for name in core.IDENTIFIERS}:
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
        if int(table.current_snapshot().summary["total-records"]) != original_rows:
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
        after = sum(int(item["size"]) for item in store.objects(table_prefix))
        if candidates and after >= before:
            raise RuntimeError("financials GCS active metadata bytes did not decrease")
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


def run(mode: str) -> dict[str, Any]:
    if mode not in {"dry-run", "apply", "retention-dry-run", "retention-apply"}:
        raise ValueError("unsupported Iceberg maintenance mode")
    bucket = os.environ.get("CORE_BUCKET", "").strip()
    if bucket != "gen-lang-client-0593591102-dev-core":
        raise ValueError("Iceberg maintenance is restricted to the existing dev Core bucket")
    from .__main__ import _iceberg_core

    core = _iceberg_core(bucket)
    try:
        with core.mutation_lock():
            if mode.startswith("retention-"):
                from .retention import maintain_public_data
                return maintain_public_data(core=core, apply=mode == "retention-apply")
            return maintain_financials(core=core, store=GcsObjectStore(bucket), apply=mode == "apply")
    finally:
        core.close()
