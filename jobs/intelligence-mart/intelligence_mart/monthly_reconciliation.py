"""Read-only monthly reconciliation of current specialist and ML/OOS derived cache.

Never deletes historical artifacts, recomputes canonical data or promotes a model.
An unreferenced pointer is only a retention candidate, not proof of an orphan.
"""
from __future__ import annotations

from hashlib import sha256
import json

from .specialists import DEPENDENCIES, FEATURE_VERSION, MODEL_VERSION, VERSION


def reconcile_monthly_cache(store, bucket: str, target_symbols, references, core_snapshot_id: str) -> dict:
    from .specialist_runtime import _cached_specialist_reference

    expected = {(str(symbol), role) for symbol in target_symbols for role in DEPENDENCIES}
    observed = [(str(ref["symbol"]), ref["role"]) for ref in references]
    if set(observed) != expected or len(observed) != len(expected):
        raise RuntimeError("monthly reconciliation specialist target/role coverage mismatch")
    active_pointers: set[str] = set()
    reused = 0
    for ref in references:
        symbol, role = str(ref["symbol"]), ref["role"]
        verified, identity, name = _cached_specialist_reference(
            store, bucket, symbol, role, ref["input_hash"])
        if verified is None or verified["artifact_uri"] != ref["artifact_uri"] or verified["artifact_hash"] != ref["artifact_hash"]:
            raise RuntimeError("monthly reconciliation detected missed invalidation or cache mismatch")
        if ref["cache_identity"] != identity or ref["source_core_snapshot_id"] != verified["source_core_snapshot_id"]:
            raise RuntimeError("monthly reconciliation provenance mismatch")
        active_pointers.add(name)
        reused += bool(ref["reused"])
    # B4 cache history is immutable: an inactive key may still be referenced by
    # a historical execution. Report candidates but never delete/declare orphan.
    pointer_names = set(store.list("specialist-cache/v1/"))
    if len(pointer_names) > 4096:
        pointer_inventory = {"status": "bounded_incomplete", "observed": len(pointer_names),
                             "unreferenced_candidates": None}
    else:
        pointer_inventory = {"status": "enumerated", "observed": len(pointer_names),
                             "unreferenced_candidates": len(pointer_names - active_pointers)}
    if not active_pointers <= pointer_names:
        raise RuntimeError("monthly reconciliation active cache pointer missing from inventory")

    # Inspect newest B6 immutable training input in place, without BigQuery reads,
    # mutation or materializing it in an ML model. Do not pretend a historical
    # dataset belongs to this month's pinned Core snapshot.
    manifest_items = [item for item in store.objects("ml-oos-data/v1/")
                      if str(item["name"]).endswith("/manifest.json")]
    if len(manifest_items) > 128:
        ml = {"status": "bounded_incomplete", "manifest_count": len(manifest_items)}
    elif not manifest_items:
        ml = {"status": "missing", "manifest_count": 0}
    else:
        from .ml_oos_data import inspect_dataset
        item = max(manifest_items, key=lambda entry: (entry.get("updated", ""), entry["name"]))
        raw = store.read(item["name"])
        manifest = json.loads(raw)
        checked = inspect_dataset(manifest, store)
        expected_model = str(MODEL_VERSION)
        ml = {"status": "current" if checked["core_snapshot_id"] == core_snapshot_id
              and str(manifest.get("model_version")) == expected_model else "historical",
              "manifest_count": len(manifest_items),
              "manifest_uri": f"gs://{bucket}/{item['name']}",
              "manifest_sha256": "sha256:" + sha256(raw).hexdigest(),
              "core_snapshot_id": checked["core_snapshot_id"],
              "row_count": checked["row_count"],
              "content_hash": checked["dataset_content_hash"],
              "model_version": manifest.get("model_version"),
              "storage_read_api_used": False}
    complete = pointer_inventory["status"] == "enumerated" and ml["status"] == "current"
    return {"artifact_kind": "mart_monthly_cache_reconciliation_v1", "schema_version": "1.0.0",
            "status": "pass" if complete else "partial",
            "core_snapshot_id": core_snapshot_id, "model_version": MODEL_VERSION,
            "feature_version": FEATURE_VERSION, "engine_version": VERSION,
            "active_specialist_refs_verified": len(active_pointers),
            "reused_specialist_refs_verified": reused,
            "missed_invalidation_detected": False,
            "pointer_inventory": pointer_inventory,
            "orphan_classification": "unverified_retention_candidates_no_deletion",
            "ml_oos_derived_cache": ml,
            "event_classifier_retrain": "not_triggered_without_labeled_data_or_drift_gate",
            "champion_promotion": False, "llm_api_tokens": 0, "ceo_triggered": False}
