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
CLASS_ORDER = {
    "A_near_S90_converging": 0,
    "B_fast_converging": 1,
    "C_early_emergence": 2,
}


def _read_json(buck: Any, obj: str) -> dict[str, Any]:
    return json.loads(buck.blob(obj).download_as_bytes().decode("utf-8"))


def _read_parquet(buck: Any, obj: str) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(buck.blob(obj).download_as_bytes()))


def _watch_class(latest: float, delta_total: float, improving: int) -> str | None:
    if latest >= 0.80 and delta_total > 0 and improving >= 3:
        return "A_near_S90_converging"
    if latest >= 0.75 and delta_total >= 0.05 and improving >= 4:
        return "B_fast_converging"
    if latest >= 0.65 and delta_total >= 0.10 and improving >= 5:
        return "C_early_emergence"
    return None


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    if request.get("action") != "export_emerging_feature_watch":
        raise RuntimeError("unexpected action")
    if request.get("watch_horizon_end") != "2026-12-31":
        raise RuntimeError("watch horizon changed")
    if int(request.get("minimum_available_features", 0)) != 6:
        raise RuntimeError("minimum feature count changed")
    if float(request.get("minimum_latest_score", 0)) != 0.65:
        raise RuntimeError("minimum latest score changed")
    if int(request.get("minimum_observation_count", 0)) != 3:
        raise RuntimeError("minimum observation count changed")
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
    if (ledger["maturity_status"].astype(str) == "late_materialization").any():
        raise RuntimeError("late materialization present in PV1 ledger")

    obs_dates = sorted(registry["observation_T"].astype(str).unique().tolist())
    if len(obs_dates) < 3:
        raise RuntimeError("not enough blind observation dates for emergence trend")
    earliest_t, previous_t, latest_t = obs_dates[0], obs_dates[-2], obs_dates[-1]
    if latest_t != str(state["latest_observation_T"]):
        raise RuntimeError("state/latest observation mismatch")

    needed = ["panel_id", "observation_T", "stock_id", "composite_score", "available_feature_count"]
    for f in FEATURES:
        needed.append(f"oriented_rank_{f}")
    q = registry[needed].copy()
    q["composite_score"] = pd.to_numeric(q["composite_score"], errors="coerce")
    q["available_feature_count"] = pd.to_numeric(q["available_feature_count"], errors="coerce")
    for f in FEATURES:
        q[f"oriented_rank_{f}"] = pd.to_numeric(q[f"oriented_rank_{f}"], errors="coerce")

    by_key = {(str(r.panel_id), str(r.stock_id), str(r.observation_T)): r for r in q.itertuples(index=False)}
    latest_frame = q[q["observation_T"].astype(str) == latest_t].copy()
    if len(latest_frame) != 1000:
        raise RuntimeError("latest frozen panel shape invalid")

    rows: list[dict[str, Any]] = []
    for latest_row in latest_frame.itertuples(index=False):
        panel = str(latest_row.panel_id)
        sid = str(latest_row.stock_id)
        prev = by_key.get((panel, sid, previous_t))
        first = by_key.get((panel, sid, earliest_t))
        if prev is None or first is None:
            continue
        latest_score = float(latest_row.composite_score) if pd.notna(latest_row.composite_score) else None
        prev_score = float(prev.composite_score) if pd.notna(prev.composite_score) else None
        first_score = float(first.composite_score) if pd.notna(first.composite_score) else None
        if latest_score is None or prev_score is None or first_score is None:
            continue
        if int(latest_row.available_feature_count) < 6 or latest_score >= 0.90 or latest_score < 0.65:
            continue

        deltas: dict[str, float | None] = {}
        latest_ranks: dict[str, float | None] = {}
        improving = 0
        strong = 0
        near_strong = 0
        for f in FEATURES:
            col = f"oriented_rank_{f}"
            lv = getattr(latest_row, col)
            fv = getattr(first, col)
            latest_rank = float(lv) if pd.notna(lv) else None
            first_rank = float(fv) if pd.notna(fv) else None
            latest_ranks[f] = latest_rank
            delta = (latest_rank - first_rank) if latest_rank is not None and first_rank is not None else None
            deltas[f] = delta
            if delta is not None and delta >= 0.10:
                improving += 1
            if latest_rank is not None and latest_rank >= 0.80:
                strong += 1
            if latest_rank is not None and latest_rank >= 0.70:
                near_strong += 1

        delta_total = latest_score - first_score
        delta_recent = latest_score - prev_score
        cls = _watch_class(latest_score, delta_total, improving)
        if cls is None:
            continue
        rising = first_score < prev_score < latest_score
        top_improving = [
            f for f, d in sorted(
                ((f, d) for f, d in deltas.items() if d is not None),
                key=lambda x: (-x[1], x[0]),
            )[:3]
        ]
        top_current = [
            f for f, r in sorted(
                ((f, r) for f, r in latest_ranks.items() if r is not None),
                key=lambda x: (-x[1], x[0]),
            )[:3]
        ]
        rec: dict[str, Any] = {
            "panel_id": panel,
            "stock_id": sid,
            "earliest_T": earliest_t,
            "previous_T": previous_t,
            "latest_T": latest_t,
            "earliest_score": first_score,
            "previous_score": prev_score,
            "latest_score": latest_score,
            "score_delta_total": delta_total,
            "score_delta_recent": delta_recent,
            "distance_to_S90": 0.90 - latest_score,
            "two_step_rising_score": rising,
            "improving_feature_count": improving,
            "strong_feature_count_latest": strong,
            "near_strong_feature_count_latest": near_strong,
            "watch_class": cls,
            "top_improving_features": "|".join(top_improving),
            "top_current_features": "|".join(top_current),
        }
        for f in FEATURES:
            rec[f"latest_rank_{f}"] = latest_ranks[f]
            rec[f"delta_{f}"] = deltas[f]
        rows.append(rec)

    watch = pd.DataFrame(rows)
    if watch.empty:
        raise RuntimeError("emerging feature watch produced no candidates")
    watch["_class_order"] = watch["watch_class"].map(CLASS_ORDER)
    watch = watch.sort_values(
        ["_class_order", "latest_score", "improving_feature_count", "score_delta_total", "stock_id"],
        ascending=[True, False, False, False, True],
    ).head(20).drop(columns=["_class_order"])

    root = f"{prefix}/prospective/pv1/emerging-feature-watch/{run_id}"
    watch_obj = f"{root}/emerging_feature_watch.csv"
    buck.blob(watch_obj).upload_from_string(watch.to_csv(index=False).encode("utf-8-sig"), content_type="text/csv")

    result = {
        "schema_version": "janus.research.big-move.emerging-feature-watch-result.v1",
        "status": "ok",
        "action": "export_emerging_feature_watch",
        "run_id": run_id,
        "generated_at": base.now(),
        "research_only": True,
        "watch_horizon_end": "2026-12-31",
        "earliest_T": earliest_t,
        "previous_T": previous_t,
        "latest_T": latest_t,
        "registry_run_id": str(state["latest_registry_run_id"]),
        "candidate_rows": int(len(watch)),
        "counts_by_class": {str(k): int(v) for k, v in watch.groupby("watch_class").size().to_dict().items()},
        "watch_object": watch_obj,
        "forecast_target": "future appearance/persistence of frozen antecedent feature constellation; not return",
        "probability_calibrated": False,
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
    result_obj = f"{root}/watch_result.json"
    buck.blob(result_obj).upload_from_string(
        (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        content_type="application/json",
    )
    result["watch_result_object"] = result_obj
    return result


def self_test() -> None:
    assert _watch_class(0.85, 0.05, 3) == "A_near_S90_converging"
    assert _watch_class(0.77, 0.08, 4) == "B_fast_converging"
    assert _watch_class(0.68, 0.12, 5) == "C_early_emergence"
    assert _watch_class(0.72, 0.02, 2) is None
