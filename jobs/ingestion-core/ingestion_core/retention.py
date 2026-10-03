"""Bounded public-data retention; referenced snapshots and unknown Stage objects stay protected."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from typing import Any

from .stage import GcsObjectStore
from .iceberg_maintenance import maintain_financials, _references

POLICY = {"stage_days": 7, "quarantine_days": 30, "mart_days": 90, "core_days": 365, "deep_price_days": 1096,
          "financial_quarters": 12, "orphan_days": 7, "target_bytes": 1_000_000_000, "alert_bytes": 2_000_000_000}


def retained_core_rows(core: Any, dataset: str, rows: list[dict[str, Any]], now: datetime,
                       deep_symbols: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    if dataset == "financials":
        periods = {}
        for row in rows:
            group = (row["symbol"], row["statement_type"], row["source_id"])
            periods.setdefault(group, set()).add((int(row["fiscal_year"]), int(row["fiscal_quarter"])))
        periods = {group: set(sorted(values, reverse=True)[:POLICY["financial_quarters"]]) for group, values in periods.items()}
        eligible = [row for row in rows if (int(row["fiscal_year"]), int(row["fiscal_quarter"]))
                    in periods[(row["symbol"], row["statement_type"], row["source_id"])]]
        observations = [{**row, "publication_time_authoritative": False}
                        if row.get("source_id") == "mops" and row.get("publication_time_authoritative") is not True else row
                        for row in eligible]
        retained, _ = core._financial_observations([], observations)
        originals = {id(observation): original for observation, original in zip(observations, eligible)}
        return [originals[id(row)] for row in retained]
    field = core.PARTITIONS[dataset][0][0]
    cutoff = (now - timedelta(days=POLICY["core_days"])).date()
    deep_cutoff = (now - timedelta(days=POLICY["deep_price_days"])).date()
    return [row for row in rows if not row.get(field) or date.fromisoformat(str(row[field])[:10]) >= (
        deep_cutoff if dataset == "benchmark" or dataset == "ohlcv" and row.get("symbol") in deep_symbols else cutoff)]


def clean_stage(store: Any, *, apply: bool, now: datetime) -> dict[str, Any]:
    objects = store.objects("")
    candidates, held = [], 0
    for marker in objects:
        name = marker["name"]
        if not name.startswith("executions/") or not name.endswith("/core-commit.json"):
            continue
        document = json.loads(store.read(name))
        execution_id = document["execution_id"]
        prefix = f"executions/{execution_id}/stage/"
        if name != f"executions/{execution_id}/core-commit.json":
            raise ValueError("Stage commit marker identity mismatch")
        committed = set(document.get("stage_objects", []))
        if any(not item.startswith(prefix + "raw/") for item in committed):
            raise ValueError("Stage commit marker escaped its execution")
        for item in objects:
            path = item["name"]
            age = now - datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
            if not path.startswith(prefix) or age < timedelta(days=POLICY["stage_days"]):
                continue
            # Keep provenance metadata and unresolved quarantine; only the committed payload is disposable.
            if path in committed:
                candidates.append(item)
            elif "/quarantine/" in path:
                held += 1
    if apply:
        for item in candidates: store.delete(item["name"], generation=item["generation"])
    return {"bucket": store.bucket, "planned_objects": len(candidates),
            "planned_bytes": sum(int(item["size"]) for item in candidates),
            "deleted_bytes": sum(int(item["size"]) for item in candidates) if apply else 0,
            "deleted_objects": len(candidates) if apply else 0, "held_quarantine_objects": held}


def clean_orphans(core: Any, store: Any, identifier: str, *, apply: bool, now: datetime) -> dict[str, Any]:
    table = core.catalog.load_table(identifier)
    referenced, _ = _references(store, identifier)
    available = {snapshot.snapshot_id for snapshot in table.snapshots()}
    if not referenced <= available: raise RuntimeError("retention would break a Core snapshot reference")
    live = set()
    for snapshot in table.snapshots():
        live.add(snapshot.manifest_list)
        for manifest in snapshot.manifests(table.io):
            live.add(manifest.manifest_path)
            for entry in manifest.fetch_manifest_entry(table.io, discard_deleted=True):
                live.add(entry.data_file.file_path)
    prefix = f"warehouse/{identifier.split('.')[1]}/"
    candidates = [item for item in store.objects(prefix)
                  if item["name"].endswith((".avro", ".parquet"))
                  and f"gs://{store.bucket}/{item['name']}" not in live
                  and datetime.fromisoformat(item["updated"].replace("Z", "+00:00")) < now - timedelta(days=7)]
    if apply:
        current = table.metadata_location
        for index, item in enumerate(candidates):
            if index % 50 == 0 and core.catalog.load_table(identifier).metadata_location != current:
                raise RuntimeError("catalog changed during orphan cleanup")
            store.delete(item["name"], generation=item["generation"])
    return {"table": identifier, "planned_objects": len(candidates),
            "planned_bytes": sum(int(item["size"]) for item in candidates),
            "deleted_bytes": sum(int(item["size"]) for item in candidates) if apply else 0,
            "deleted_objects": len(candidates) if apply else 0}


def maintain_public_data(*, core: Any, apply: bool, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    store = GcsObjectStore(os.environ["CORE_BUCKET"])
    stage_bucket = os.environ.get("STAGE_BUCKET", "")
    if stage_bucket != "gen-lang-client-0593591102-dev-stage":
        raise ValueError("retention requires the existing dev Stage bucket")
    stage_store = GcsObjectStore(stage_bucket)
    from .__main__ import _control_plane, TAIPEI
    with _control_plane() as control, control.connection.cursor() as cursor:
        cursor.execute("SELECT symbol FROM control.mart_ai_target_symbols(%s::date)", (now.astimezone(TAIPEI).date(),))
        deep_symbols = frozenset(row[0] for row in cursor.fetchall())
    def capacity(object_store):
        objects = object_store.objects("")
        return {"objects": len(objects), "bytes": sum(int(item["size"]) for item in objects)}
    before = {"core": capacity(store), "stage": capacity(stage_store)}
    tables, orphans = [], []
    for dataset in core.IDENTIFIERS:
        identifier = core.table_identifier(dataset)
        if not core.catalog.table_exists(identifier): continue
        table = core.catalog.load_table(identifier)
        rows = table.scan().to_arrow().to_pylist()
        retained = retained_core_rows(core, dataset, rows, now, deep_symbols)
        removed = len(rows) - len(retained)
        if apply and removed:
            import pyarrow as pa
            table.overwrite(pa.Table.from_pylist(retained, schema=table.schema().as_arrow()),
                            snapshot_properties={"janus.retention-policy": "public-data-retention-v1"})
            actual = core.catalog.load_table(identifier).scan().to_arrow().to_pylist()
            if len(actual) != len(retained): raise RuntimeError("retention row-count verification failed")
        del rows, retained
        result = maintain_financials(core=core, store=store, apply=apply, now=now, identifier=identifier)
        result["planned_rows_removed"] = removed
        result["rows_removed"] = removed if apply else 0
        tables.append(result)
        orphans.append(clean_orphans(core, store, identifier, apply=apply, now=now))
    stage = clean_stage(stage_store, apply=apply, now=now)
    after = {"core": capacity(store), "stage": capacity(stage_store)} if apply else before
    storage = {layer: {"before": before[layer], "after": after[layer],
                       "active_bytes_reduced": before[layer]["bytes"] - after[layer]["bytes"]}
               for layer in before}
    result = {"component": "data-retention", "policy_version": "public-data-retention-v1",
            "mode": "apply" if apply else "dry-run", "policy": POLICY, "tables": tables, "orphans": orphans,
            "stage": stage, "model_calls": 0, "publication_writes": 0,
            "storage": storage, "storage_scope": "live_objects_only",
            "billable_bytes_reclaimed": None,
            "mart_retention_status": "requires_mart_catalog_worker", "quarantine_status": "unresolved_held"}
    from hashlib import sha256
    payload = json.dumps(result, sort_keys=True, default=str).encode()
    name = "maintenance/retention/" + now.strftime("%Y-%m-%dT%H%M%SZ") + "-" + sha256(payload).hexdigest() + ".json"
    if not store.create(name, payload, "application/json") and store.read(name) != payload:
        raise RuntimeError("retention report conflict")
    if store.read(name) != payload:
        raise RuntimeError("retention report readback mismatch")
    return {**result, "artifact_uri": f"gs://{store.bucket}/{name}"}
