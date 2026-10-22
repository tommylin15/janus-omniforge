"""Risk XGBoost first-release serving, fenced to an ACTIVE registry pointer.

Research shadow remains immutable and non-publishable. New Risk product values
are written only for the de-identified target union (ordinary shares only)
and are never copied to all-market screening or canonical OHLCV.
"""
from __future__ import annotations

from hashlib import sha256
from urllib.error import HTTPError
import json

from scripts.gcp.risk_registry_cas import (ACTIVE_OBJECT, MODEL_SHA256, MODEL_VERSION,
                                           FEATURE_VERSION, MODEL_OBJECT, BUCKET,
                                           validate_pointer)
from .risk_shadow import load_model_from_pinned_store, predict_core_shadow
from .specialists import digest


def load_active_pointer(store, *, bucket: str):
    try:
        raw = store.read(ACTIVE_OBJECT)
    except (FileNotFoundError, HTTPError) as error:
        if isinstance(error, HTTPError) and error.code != 404:
            raise
        return None
    pointer = json.loads(raw)
    if bucket != BUCKET:
        raise ValueError("Risk ACTIVE dev bucket identity mismatch")
    validate_pointer(pointer)
    return pointer if pointer["mode"] == "ACTIVE" else None


def build_risk_active_artifact(rows, *, targets, ordinary_symbols,
                               as_of, core_snapshot_id, core_manifest_hash,
                               model, active_pointer):
    """Pure immutable Risk product receipt. Returns only eligible selected shares."""
    validate_pointer(active_pointer)
    if active_pointer is None or active_pointer["mode"] != "ACTIVE":
        raise ValueError("Risk ACTIVE pointer required")
    target_set = set(targets)
    ordinary = target_set.intersection(ordinary_symbols)
    if len(target_set) != len(targets) or len(ordinary_symbols) != len(set(ordinary_symbols)):
        raise ValueError("Risk targets and ordinary membership must be unique")
    result = predict_core_shadow(rows, as_of, model,
        core_snapshot_id=core_snapshot_id, target_symbols=ordinary)
    predictions = []
    for item in result["predictions"]:
        if item["symbol"] not in ordinary or item["model_sha256"] != MODEL_SHA256:
            raise ValueError("model predicted a non-target or non-pinned model")
        predictions.append({
            "symbol": item["symbol"], "market": item["market"],
            "analysis_as_of": as_of, "core_snapshot_id": core_snapshot_id,
            "future_20d_volatility_annualized": item["future_20d_volatility_annualized"],
            "recent_20d_volatility_annualized": item["recent_20d_volatility_annualized"],
            "model_sha256": MODEL_SHA256,
        })
    if len({row["symbol"] for row in predictions}) != len(predictions):
        raise ValueError("duplicate Risk active predictions")
    excluded_nonordinary = len(target_set - ordinary)
    excluded = len(ordinary) - len(predictions)
    if excluded != result["excluded_target_symbols_count"]:
        raise ValueError("Risk active exclusion count mismatch")
    payload = {
        "artifact_kind": "mart_risk_active_predictions_v1", "schema_version": "1.0.0",
        "publication_status": "FIRST_RELEASE_APPROVED",
        "model_version": MODEL_VERSION, "model_sha256": MODEL_SHA256,
        "feature_version": FEATURE_VERSION,
        "active_registry_source_git_sha": active_pointer["source_git_sha"],
        "analysis_as_of": as_of, "core_snapshot_id": core_snapshot_id,
        "source_manifest_hash": core_manifest_hash,
        "scope": "HELD_AND_WATCHLISTED_ORDINARY_SHARES",
        "target_count": len(target_set),
        "ordinary_target_count": len(ordinary),
        "excluded_nonordinary_target_count": excluded_nonordinary,
        "excluded_ordinary_target_count": excluded,
        "excluded_reasons": {
            **result.get("excluded_target_reasons", {}),
            "NOT_IN_ORDINARY_STOCK_UNIVERSE_INCLUDING_ETF": excluded_nonordinary,
        },
        "calendar_evidence": result.get("calendar_evidence"),
        "rows": sorted(predictions, key=lambda row: row["symbol"]),
    }
    if sum(payload["excluded_reasons"].values()) != len(target_set) - len(predictions):
        raise ValueError("Risk active accounting mismatch")
    payload["output_hash"] = digest(payload)
    return payload


def materialize_active_predictions(store, *, bucket, rows, targets,
                                    ordinary_symbols, as_of, core_snapshot_id,
                                    core_manifest_hash, active_pointer, model=None):
    if active_pointer is None:
        return None
    if model is None:
        model = load_model_from_pinned_store(store)
    artifact = build_risk_active_artifact(rows, targets=targets,
        ordinary_symbols=ordinary_symbols, as_of=as_of,
        core_snapshot_id=core_snapshot_id, core_manifest_hash=core_manifest_hash,
        model=model, active_pointer=active_pointer)
    from .runtime import _write_immutable_json
    name = f"risk-active/{artifact['output_hash'][7:]}.json"
    ref = _write_immutable_json(store, bucket, name, artifact)
    if json.loads(store.read(name)) != artifact:
        raise RuntimeError("Risk ACTIVE artifact readback mismatch")
    return ref


def validate_risk_active_artifact(artifact, manifest):
    """Verify the exact immutable snapshot and owner-safe serving boundary."""
    if (artifact.get("artifact_kind") != "mart_risk_active_predictions_v1"
            or artifact.get("publication_status") != "FIRST_RELEASE_APPROVED"
            or artifact.get("model_version") != MODEL_VERSION
            or artifact.get("model_sha256") != MODEL_SHA256
            or artifact.get("feature_version") != FEATURE_VERSION
            or artifact.get("analysis_as_of") != manifest["analysis_as_of"]
            or artifact.get("core_snapshot_id") != manifest["core_snapshot_id"]
            or artifact.get("source_manifest_hash") != manifest["source_core_manifest_hash"]
            or artifact.get("scope") != "HELD_AND_WATCHLISTED_ORDINARY_SHARES"
            or artifact.get("output_hash") != digest({k: v for k, v in artifact.items() if k != "output_hash"})):
        raise ValueError("Risk ACTIVE provenance or identity mismatch")
    items = artifact["rows"]
    if len({r["symbol"] for r in items}) != len(items) or len(items) > artifact["ordinary_target_count"]:
        raise ValueError("invalid Risk ACTIVE target scope")
    if (len(items) + artifact["excluded_ordinary_target_count"]
            + artifact["excluded_nonordinary_target_count"] != artifact["target_count"]):
        raise ValueError("Risk ACTIVE target count invalid")
    for item in items:
        if any(item.get(key) != artifact[key] for key in ("analysis_as_of", "core_snapshot_id", "model_sha256")):
            raise ValueError("Risk ACTIVE row provenance mismatch")
    return {item["symbol"]: item for item in items}
