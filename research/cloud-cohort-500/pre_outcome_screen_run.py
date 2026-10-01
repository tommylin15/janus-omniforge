from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd
from google.cloud import storage

import prospective_registry_run as base

STATE_SUFFIX = "prospective/pv1/state/latest_registry.json"
FEATURES = [
    "range_mean_20",
    "vol_60",
    "vol_20",
    "close_to_high_20",
    "ret_5",
    "max_drawdown_20",
    "close_to_high_60",
    "max_drawdown_60",
]


def _read_json(buck: Any, obj: str) -> dict[str, Any]:
    return json.loads(buck.blob(obj).download_as_bytes().decode("utf-8"))


def _read_parquet(buck: Any, obj: str) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(buck.blob(obj).download_as_bytes()))


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    if request.get("action") != "export_pre_outcome_screen":
        raise RuntimeError("unexpected action")
    if request.get("latest_observation_only") is not True:
        raise RuntimeError("latest_observation_only must be true")
    if int(request.get("minimum_available_features", 0)) != 6:
        raise RuntimeError("frozen minimum feature count changed")
    if request.get("score_tiers") != {"S90_core": 0.9, "S80_watch": 0.8, "S70_observe": 0.7}:
        raise RuntimeError("frozen screen tiers changed")
    for k in ("outcome_evaluation_allowed", "event_label_materialization_allowed", "canonical_publication_allowed"):
        if request.get(k) is not False:
            raise RuntimeError(f"{k} must be false")

    client = storage.Client()
    buck = client.bucket(bucket)
    state = _read_json(buck, f"{prefix}/{STATE_SUFFIX}")
    if state.get("pv1_id") != base.PV1_ID:
        raise RuntimeError("PV1 state mismatch")

    registry = _read_parquet(buck, str(state["latest_registry_object"]))
    ledger = _read_parquet(buck, str(state["latest_ledger_object"]))
    forbidden = {"mfe60", "future_return", "future_high", "event_seed", "wave_event", "event_rate", "lift", "capture", "h60_label"}
    leaked = sorted(forbidden & {str(c).lower() for c in registry.columns})
    if leaked:
        raise RuntimeError(f"outcome field leaked into registry: {leaked}")
    if ledger["mfe60"].notna().any() or ledger["event_seed"].notna().any():
        raise RuntimeError("outcome/event data already present in ledger")

    latest = str(registry["observation_T"].astype(str).max())
    if latest != str(state["latest_observation_T"]):
        raise RuntimeError("state/latest observation mismatch")
    q = registry[registry["observation_T"].astype(str) == latest].copy()
    if len(q) != 1000 or q.duplicated(["panel_id", "stock_id"]).any():
        raise RuntimeError("latest-T frozen panel shape invalid")
    sizes = q.groupby("panel_id").size().to_dict()
    if sizes != {"independent_500": 500, "primary_500": 500}:
        raise RuntimeError(f"latest-T panel sizes invalid: {sizes}")

    l = ledger[ledger["observation_T"].astype(str) == latest].copy()
    if len(l) != 1000 or (l["maturity_status"].astype(str) == "late_materialization").any():
        raise RuntimeError("latest-T ledger invalid")

    q["composite_score"] = pd.to_numeric(q["composite_score"], errors="coerce")
    q["available_feature_count"] = pd.to_numeric(q["available_feature_count"], errors="coerce")
    for f in FEATURES:
        raw_col = f"feature_{f}"
        rank_col = f"oriented_rank_{f}"
        if raw_col not in q.columns or rank_col not in q.columns:
            raise RuntimeError(f"frozen feature attribution column missing: {f}")
        q[raw_col] = pd.to_numeric(q[raw_col], errors="coerce")
        q[rank_col] = pd.to_numeric(q[rank_col], errors="coerce")
        q[f"contribution_{f}"] = q[rank_col] / q["available_feature_count"]

    eligible = q[(q["available_feature_count"] >= 6) & q["composite_score"].notna()].copy()
    screen = eligible[eligible["composite_score"] >= 0.7].copy()
    screen["tier"] = screen["composite_score"].map(
        lambda x: "S90_core" if x >= 0.9 else ("S80_watch" if x >= 0.8 else "S70_observe")
    )
    order = {"S90_core": 0, "S80_watch": 1, "S70_observe": 2}
    screen["_tier_order"] = screen["tier"].map(order)

    base_cols = [
        "panel_id", "observation_T", "stock_id", "composite_score", "available_feature_count", "tier",
    ]
    attribution_cols: list[str] = []
    for f in FEATURES:
        attribution_cols.extend([f"feature_{f}", f"oriented_rank_{f}", f"contribution_{f}"])
    lineage_cols = ["row_hash", "registry_revision", "scorer_revision", "source_bundle_hash"]
    cols = base_cols + attribution_cols + lineage_cols
    screen = screen.sort_values(
        ["_tier_order", "composite_score", "panel_id", "stock_id"],
        ascending=[True, False, True, True],
    )[cols]

    # Verify attribution reconstructs the frozen composite score.
    contrib_cols = [f"contribution_{f}" for f in FEATURES]
    reconstructed = screen[contrib_cols].sum(axis=1, skipna=True)
    if ((reconstructed - screen["composite_score"]).abs() > 1e-10).any():
        raise RuntimeError("feature attribution does not reconstruct composite_score")

    root = f"{prefix}/prospective/pv1/screens/{run_id}"
    csv_bytes = screen.to_csv(index=False).encode("utf-8-sig")
    screen_obj = f"{root}/candidate_screen.csv"
    buck.blob(screen_obj).upload_from_string(csv_bytes, content_type="text/csv")

    counts = screen.groupby(["panel_id", "tier"]).size().unstack(fill_value=0).to_dict("index")
    totals = {str(k): int(v) for k, v in screen.groupby("tier").size().to_dict().items()}
    result = {
        "schema_version": "janus.research.big-move.pre-outcome-screen-result.v1.1",
        "status": "ok",
        "action": "export_pre_outcome_screen",
        "run_id": run_id,
        "generated_at": base.now(),
        "research_only": True,
        "observation_T": latest,
        "registry_run_id": str(state["latest_registry_run_id"]),
        "frozen_panel_rows": 1000,
        "score_eligible_rows": int(len(eligible)),
        "candidate_rows": int(len(screen)),
        "counts_by_panel_and_tier": counts,
        "counts_by_tier": totals,
        "tier_definition": {
            "S90_core": "score >= 0.90",
            "S80_watch": "0.80 <= score < 0.90",
            "S70_observe": "0.70 <= score < 0.80",
        },
        "feature_attribution": {
            "features": FEATURES,
            "raw_values_included": True,
            "oriented_percentile_ranks_included": True,
            "equal_weight_contributions_included": True,
            "contribution_formula": "oriented_rank / available_feature_count",
            "reconstructs_composite_score": True,
        },
        "candidate_screen_object": screen_obj,
        "embargo": {
            "mfe60_used": False,
            "event_seed_used": False,
            "lift_used": False,
            "capture_used": False,
            "spearman_used": False,
            "pv1_pass_fail_used": False,
        },
        "canonical_signal": False,
        "trading_recommendation": False,
        "isolation": {
            "postgresql_used": False,
            "database_used": False,
            "existing_janus_iceberg_catalog_used": False,
            "janus_core_written": False,
            "janus_mart_written": False,
            "janus_private_mart_written": False,
            "runtime_secret_used": False,
        },
    }
    result_obj = f"{root}/screen_result.json"
    buck.blob(result_obj).upload_from_string(
        (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        content_type="application/json",
    )
    result["screen_result_object"] = result_obj
    return result


def self_test() -> None:
    assert STATE_SUFFIX.endswith("latest_registry.json")
    assert len(FEATURES) == 8
    assert {"S90_core": 0.9, "S80_watch": 0.8, "S70_observe": 0.7}["S90_core"] == 0.9
