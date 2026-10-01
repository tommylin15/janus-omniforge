from __future__ import annotations

import io
import json
import math
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import storage

import matched_feature_run as feature_impl
import outcome_run
import prospective_registry_run as base
import validation_run

FEATURES = list(validation_run.FEATURES)
HIGHER_SIGNAL = set(validation_run.HIGHER_SIGNAL)
MIN_FEATURES = int(validation_run.MIN_FEATURES)
STATE_OBJECT_SUFFIX = "prospective/pv1/state/latest_registry.json"


def _state_object(prefix: str) -> str:
    return f"{prefix}/{STATE_OBJECT_SUFFIX}"


def _revision_root(prefix: str, run_id: str) -> str:
    return f"{prefix}/prospective/pv1/revisions/{run_id}"


def _load_parquet(buck: Any, object_name: str) -> pd.DataFrame:
    raw = buck.blob(object_name).download_as_bytes()
    return pd.read_parquet(io.BytesIO(raw))


def _load_state_or_initial(buck: Any, prefix: str, request: dict[str, Any]) -> dict[str, Any]:
    obj = _state_object(prefix)
    blob = buck.blob(obj)
    if blob.exists():
        state = json.loads(blob.download_as_bytes().decode("utf-8"))
        if state.get("pv1_id") != base.PV1_ID:
            raise RuntimeError("prospective state pv1_id mismatch")
        return state
    initial = str(request.get("initial_base_registry_run_id", "")).strip()
    if not initial:
        raise RuntimeError("no prospective state and no initial_base_registry_run_id")
    root = _revision_root(prefix, initial)
    return {
        "schema_version": "janus.research.big-move.prospective-state.v1",
        "pv1_id": base.PV1_ID,
        "latest_registry_run_id": initial,
        "latest_registry_object": f"{root}/registry/pre_outcome_registry.parquet",
        "latest_ledger_object": f"{root}/ledger/maturity_outcome_ledger.parquet",
        "latest_dq_object": f"{root}/dq/dq_summary.csv",
        "latest_observation_T": str(request.get("initial_latest_observation_T", "2026-09-29")),
        "calendar_checked_through": str(request.get("initial_calendar_checked_through", "2026-09-30")),
        "initialized_from_request": True,
    }


def _write_state(buck: Any, prefix: str, run_id: str, state: dict[str, Any]) -> None:
    payload = {**state, "updated_at": base.now(), "state_update_run_id": run_id}
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    history = f"{prefix}/prospective/pv1/state/history/{run_id}.json"
    buck.blob(history).upload_from_string(raw, content_type="application/json")
    buck.blob(_state_object(prefix)).upload_from_string(raw, content_type="application/json")


def _json_scalar(v: Any) -> Any:
    return base._json_scalar(v)


def _compute_new_rows(
    *,
    panels: list[pd.DataFrame],
    source_path: Path,
    post_by_sid: dict[str, list[dict[str, Any]]],
    new_obs: list[date],
    historical_cutoff: date,
    materialized_revision: str,
    source_obj: str,
    source_sha: str,
    per_t_bundle: dict[date, tuple[str, str]],
    run_id: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    generated = base.now()
    scorer_revision = base._code_revision()
    hist_base = f"janus_step2a_materialized/{materialized_revision}/"
    with zipfile.ZipFile(source_path) as z:
        for panel in panels:
            panel_rows: list[dict[str, Any]] = []
            for p in panel.itertuples(index=False):
                sid = str(p.stock_id)
                hist = feature_impl._load_prices(z, hist_base, sid)
                hist = hist[hist["trade_date"] <= historical_cutoff].copy()
                post = pd.DataFrame(post_by_sid.get(sid, []))
                if post.empty:
                    post = pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume_shares", "turnover_twd"])
                combined = base._combine_price(hist, post)
                vw = feature_impl._view(combined)
                for t in new_obs:
                    ft = validation_run._feature8(vw, t)
                    rec: dict[str, Any] = {
                        "pv1_id": base.PV1_ID,
                        "panel_id": str(p.panel_id),
                        "cohort_revision": str(p.cohort_revision),
                        "observation_T": t.isoformat(),
                        "stock_id": sid,
                    }
                    for f in FEATURES:
                        rec[f"feature_{f}"] = _json_scalar(ft.get(f))
                    panel_rows.append(rec)

            frame = pd.DataFrame(panel_rows)
            for f in FEATURES:
                raw = pd.to_numeric(frame[f"feature_{f}"], errors="coerce")
                rank = raw.groupby(frame["observation_T"]).rank(pct=True, method="average")
                frame[f"oriented_rank_{f}"] = rank if f in HIGHER_SIGNAL else 1.0 - rank
            rank_cols = [f"oriented_rank_{f}" for f in FEATURES]
            frame["available_feature_count"] = frame[rank_cols].notna().sum(axis=1)
            frame["composite_score"] = frame[rank_cols].mean(axis=1, skipna=True)
            frame.loc[frame["available_feature_count"] < MIN_FEATURES, "composite_score"] = np.nan
            frame["s90_flag"] = frame["composite_score"] >= 0.90
            frame["s80_flag"] = frame["composite_score"] >= 0.80
            frame["s70_flag"] = frame["composite_score"] >= 0.70
            frame["scorer_revision"] = scorer_revision
            frame["runner_revision"] = run_id
            frame["generated_at"] = generated
            frame["registry_revision"] = run_id
            frame["supersedes_row_hash"] = None
            frame["correction_reason"] = None
            for t in new_obs:
                obj, bh = per_t_bundle[t]
                mask = frame["observation_T"] == t.isoformat()
                frame.loc[mask, "source_evidence_manifest_object"] = obj
                frame.loc[mask, "source_bundle_hash"] = bh
                frame.loc[mask, "source_evidence_refs"] = json.dumps([source_obj, obj], ensure_ascii=False, separators=(",", ":"))
                frame.loc[mask, "source_content_hashes"] = json.dumps([source_sha, bh], ensure_ascii=False, separators=(",", ":"))
            for r in frame.to_dict("records"):
                normalized = {k: _json_scalar(v) for k, v in r.items()}
                normalized["row_hash"] = base.stable_hash(base._row_hash_payload(normalized))
                rows.append(normalized)
    return pd.DataFrame(rows)


def _dq_summary(registry: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    ledger_status = ledger.groupby(["panel_id", "observation_T"])["maturity_status"].value_counts().unstack(fill_value=0)
    rows: list[dict[str, Any]] = []
    for (panel_id, t), g in registry.groupby(["panel_id", "observation_T"], sort=True):
        key = (panel_id, t)
        row: dict[str, Any] = {
            "panel_id": panel_id,
            "observation_T": t,
            "frozen_panel_size": 500,
            "registry_rows_expected": 500,
            "registry_rows_materialized": int(len(g)),
            "registry_rows_late_materialization": int((ledger.loc[(ledger.panel_id == panel_id) & (ledger.observation_T == t), "maturity_status"] == "late_materialization").sum()),
            "score_eligible_rows": int(g["composite_score"].notna().sum()),
            "score_ineligible_rows": int(g["composite_score"].isna().sum()),
            "duplicate_primary_key_count": int(g.duplicated(["stock_id"]).sum()),
            "conflicting_row_hash_count": int(g["row_hash"].duplicated().sum()),
            "superseding_correction_count": int(g["supersedes_row_hash"].notna().sum()) if "supersedes_row_hash" in g else 0,
            "s90_rows": int(g["s90_flag"].fillna(False).sum()),
            "s80_rows": int(g["s80_flag"].fillna(False).sum()),
            "s70_rows": int(g["s70_flag"].fillna(False).sum()),
            "maturity_pending": int(ledger_status.loc[key].get("pending_maturity", 0)) if key in ledger_status.index else 0,
            "maturity_mature": int(ledger_status.loc[key].get("mature", 0)) if key in ledger_status.index else 0,
            "maturity_excluded": int(ledger_status.loc[key].get("excluded", 0)) if key in ledger_status.index else 0,
            "maturity_unknown": int(ledger_status.loc[key].get("unknown", 0)) if key in ledger_status.index else 0,
        }
        for f in FEATURES:
            miss = int(g[f"feature_{f}"].isna().sum())
            row[f"missing_{f}_count"] = miss
            row[f"missing_{f}_rate"] = miss / len(g) if len(g) else None
        rows.append(row)
    return pd.DataFrame(rows)


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    if str(request.get("action", "")) != "extend_prospective_registry":
        raise RuntimeError("unexpected action")
    if request.get("database_allowed") is not False or request.get("existing_janus_iceberg_allowed") is not False or request.get("canonical_core_mart_writes_allowed") is not False:
        raise RuntimeError("research isolation contract not fail-closed")
    if request.get("outcome_evaluation_allowed") is not False or request.get("event_label_materialization_allowed") is not False:
        raise RuntimeError("PV1 pre-outcome embargo not fail-closed")
    if request.get("score_bands") != {"S90": 0.9, "S80": 0.8, "S70": 0.7}:
        raise RuntimeError("frozen score bands changed")

    start = base.parse_date(request.get("prospective_observation_start")) or date(2026, 9, 17)
    pv1_end = base.parse_date(request.get("pv1_observation_end")) or date(2026, 12, 31)
    through = base.parse_date(request.get("materialize_through"))
    cutoff = base.parse_date(request.get("historical_cutoff_inclusive")) or date(2026, 9, 16)
    if start != date(2026, 9, 17) or cutoff != date(2026, 9, 16) or pv1_end != date(2026, 12, 31):
        raise RuntimeError("PV1 frozen date identity changed")
    if through is None or through < start or through > pv1_end:
        raise RuntimeError("invalid materialize_through")

    client = storage.Client()
    buck = client.bucket(bucket)
    state = _load_state_or_initial(buck, prefix, request)
    base_run = str(state["latest_registry_run_id"])
    base_registry = _load_parquet(buck, str(state["latest_registry_object"]))
    base_ledger = _load_parquet(buck, str(state["latest_ledger_object"]))
    if any(c in base_registry.columns for c in ["mfe60", "future_return", "event_seed", "wave_event", "lift", "capture"]):
        raise RuntimeError("base pre-outcome registry already contaminated with future/outcome fields")
    if base_ledger["mfe60"].notna().any() or base_ledger["event_seed"].notna().any():
        raise RuntimeError("base maturity ledger contains outcome/event data before PV1 embargo release")

    existing_obs = sorted({base.parse_date(x) for x in base_registry["observation_T"].astype(str)})
    existing_obs = [x for x in existing_obs if x is not None]
    if not existing_obs:
        raise RuntimeError("base registry has no observations")

    hp, _, _ = base._http_json(base.HOLIDAY)
    holidays = base._holiday_dates(hp, start.year)
    realized_calendar: list[date] = []
    d = start
    while d <= through:
        if d.weekday() < 5 and d not in holidays:
            realized_calendar.append(d)
        d = date.fromordinal(d.toordinal() + 1)
    candidate_obs = outcome_run.weekly_first_trading_days(realized_calendar)
    new_obs = [d for d in candidate_obs if d not in set(existing_obs)]

    if not new_obs:
        new_state = {
            **state,
            "latest_observation_T": max(existing_obs).isoformat(),
            "calendar_checked_through": through.isoformat(),
        }
        _write_state(buck, prefix, run_id, new_state)
        return {
            "schema_version": "janus.research.big-move.prospective-extension.v1",
            "status": "noop_no_new_observation",
            "action": "extend_prospective_registry",
            "run_id": run_id,
            "generated_at": base.now(),
            "base_registry_run_id": base_run,
            "materialize_through": through.isoformat(),
            "existing_observation_dates": [d.isoformat() for d in existing_obs],
            "appended_observation_dates": [],
            "registry_rewritten": False,
            "registry_row_count": int(len(base_registry)),
            "ledger_row_count": int(len(base_ledger)),
            "embargo": {"mfe60_computed": False, "event_seed_computed": False, "lift_computed": False, "pass_fail_evaluated": False},
            "isolation": {"postgresql_used": False, "database_used": False, "existing_janus_iceberg_catalog_used": False, "janus_core_written": False, "janus_mart_written": False, "janus_private_mart_written": False, "runtime_secret_used": False},
            "next_gate": "wait for next frozen weekly observation; do not evaluate H60 outcome",
        }

    primary_run = str(request.get("primary_cohort_run_id", "")).strip()
    independent_run = str(request.get("independent_cohort_run_id", "")).strip()
    source_obj = str(request.get("source_gcs_object", "")).strip()
    source_sha = str(request.get("source_sha256", "")).strip().lower()
    source_size = int(request.get("source_size_bytes", 0))
    materialized_revision = str(request.get("materialized_revision", "20260917T025906Z"))
    if not primary_run or not independent_run or not source_obj or len(source_sha) != 64 or source_size <= 0:
        raise RuntimeError("immutable panel/source identity missing")

    primary = base._read_panel(buck, prefix, primary_run, "primary_500")
    independent = base._read_panel(buck, prefix, independent_run, "independent_500")
    if set(primary.stock_id) & set(independent.stock_id):
        raise RuntimeError("frozen panel overlap is not zero")

    root = _revision_root(prefix, run_id)
    with tempfile.TemporaryDirectory() as td:
        source_path = Path(td) / "source.zip"
        buck.blob(source_obj).download_to_filename(source_path)
        if source_path.stat().st_size != source_size or base.file_sha(source_path) != source_sha:
            raise RuntimeError("staged historical source identity mismatch")

        trading_dates, day_frames, source_evidence, holiday_evidence = base._official_calendar(start, max(new_obs))
        realized_obs = outcome_run.weekly_first_trading_days(trading_dates)
        if not set(new_obs).issubset(set(realized_obs)):
            raise RuntimeError("new observation calendar disagrees with live TWSE realization")

        hraw, hmeta = holiday_evidence
        holiday_obj = f"{root}/raw/twse_holiday_schedule-{hmeta['sha256']}.json"
        buck.blob(holiday_obj).upload_from_string(hraw, content_type="application/json")
        evidence_rows: list[dict[str, Any]] = []
        for e in source_evidence:
            row = {k: v for k, v in e.items() if k != "raw_bytes"}
            if e.get("status") == "trading_day":
                raw = e["raw_bytes"]
                obj = f"{root}/raw/mi_index/date={e['date']}/sha256={e['sha256']}.json"
                buck.blob(obj).upload_from_string(raw, content_type="application/json")
                row["gcs_object"] = obj
            evidence_rows.append(row)

        trading_evidence = [r for r in evidence_rows if r.get("status") == "trading_day"]
        per_t_bundle: dict[date, tuple[str, str]] = {}
        for t in new_obs:
            used = [r for r in trading_evidence if base.parse_date(r.get("date")) and base.parse_date(r.get("date")) <= t]
            bundle = {
                "historical_source": {"gcs_object": source_obj, "sha256": source_sha, "materialized_revision": materialized_revision},
                "holiday_schedule": {"gcs_object": holiday_obj, "sha256": hmeta["sha256"]},
                "prospective_daily": [{"date": r["date"], "gcs_object": r["gcs_object"], "sha256": r["sha256"]} for r in used],
            }
            raw = (json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            bh = base.sha_bytes(raw)
            obj = f"{root}/source_manifests/observation_T={t.isoformat()}-sha256={bh}.json"
            buck.blob(obj).upload_from_string(raw, content_type="application/json")
            per_t_bundle[t] = (obj, bh)

        post_by_sid: dict[str, list[dict[str, Any]]] = {}
        for dt in trading_dates:
            for r in day_frames[dt].to_dict("records"):
                post_by_sid.setdefault(str(r["stock_id"]), []).append(r)

        new_rows = _compute_new_rows(
            panels=[primary, independent], source_path=source_path, post_by_sid=post_by_sid,
            new_obs=new_obs, historical_cutoff=cutoff, materialized_revision=materialized_revision,
            source_obj=source_obj, source_sha=source_sha, per_t_bundle=per_t_bundle, run_id=run_id,
        )
        expected_add = 2 * 500 * len(new_obs)
        if len(new_rows) != expected_add or new_rows.duplicated(["panel_id", "observation_T", "stock_id"]).any():
            raise RuntimeError("incremental registry new-row count/key mismatch")

        common_cols = list(base_registry.columns)
        missing = [c for c in common_cols if c not in new_rows.columns]
        extra = [c for c in new_rows.columns if c not in common_cols]
        if missing or extra:
            raise RuntimeError(f"registry schema drift: missing={missing} extra={extra}")
        new_rows = new_rows[common_cols]
        registry = pd.concat([base_registry, new_rows], ignore_index=True)
        if registry.duplicated(["panel_id", "observation_T", "stock_id"]).any():
            raise RuntimeError("combined registry duplicate panel/T/stock")
        base_hashes = base_registry.set_index(["panel_id", "observation_T", "stock_id"])["row_hash"].to_dict()
        combined_old_hashes = registry[registry["observation_T"].isin(base_registry["observation_T"].unique())].set_index(["panel_id", "observation_T", "stock_id"])["row_hash"].to_dict()
        if base_hashes != combined_old_hashes:
            raise RuntimeError("existing immutable registry row hashes changed")

        ledger_new: list[dict[str, Any]] = []
        for r in new_rows.to_dict("records"):
            ledger_new.append({
                "pv1_id": base.PV1_ID,
                "panel_id": r["panel_id"],
                "observation_T": r["observation_T"],
                "stock_id": r["stock_id"],
                "registry_row_hash": r["row_hash"],
                "entry_E": "",
                "maturity_status": "pending_maturity",
                "exclusion_reason": "",
                "corporate_action_evidence_refs": "",
                "corporate_action_hashes": "",
                "h60_completion_evidence": "",
                "maturity_updated_at": base.now(),
                "mfe60": None,
                "event_seed": None,
                "wave_event_id": None,
                "outcome_revision": "",
                "outcome_row_hash": "",
            })
        ledger_new_df = pd.DataFrame(ledger_new)[list(base_ledger.columns)]
        ledger = pd.concat([base_ledger, ledger_new_df], ignore_index=True)
        if ledger["mfe60"].notna().any() or ledger["event_seed"].notna().any():
            raise RuntimeError("future/outcome data appeared in incremental ledger")

        dq = _dq_summary(registry, ledger)
        if not (dq["registry_rows_materialized"] == 500).all() or dq["duplicate_primary_key_count"].sum() != 0 or dq["conflicting_row_hash_count"].sum() != 0:
            raise RuntimeError("incremental DQ failed")

        calendar = pd.DataFrame([{
            "trade_date": d.isoformat(),
            "is_realized_trading_day": True,
            "is_weekly_observation_T": d in set(outcome_run.weekly_first_trading_days(trading_dates)),
            "materialized_through": through.isoformat(),
            "pv1_window_end": pv1_end.isoformat(),
        } for d in trading_dates])

        registry_obj = f"{root}/registry/pre_outcome_registry.parquet"
        ledger_obj = f"{root}/ledger/maturity_outcome_ledger.parquet"
        dq_obj = f"{root}/dq/dq_summary.csv"
        calendar_obj = f"{root}/calendar/realized_observation_calendar.csv"
        source_index_obj = f"{root}/source_manifests/source_evidence_index.json"
        with tempfile.TemporaryDirectory() as outdir:
            out = Path(outdir)
            regp, ledp = out / "registry.parquet", out / "ledger.parquet"
            registry.to_parquet(regp, index=False)
            ledger.to_parquet(ledp, index=False)
            buck.blob(registry_obj).upload_from_filename(regp, content_type="application/octet-stream")
            buck.blob(ledger_obj).upload_from_filename(ledp, content_type="application/octet-stream")
        buck.blob(dq_obj).upload_from_string(dq.to_csv(index=False).encode("utf-8-sig"), content_type="text/csv")
        buck.blob(calendar_obj).upload_from_string(calendar.to_csv(index=False).encode("utf-8-sig"), content_type="text/csv")
        buck.blob(source_index_obj).upload_from_string((json.dumps({"dates": [{k:v for k,v in r.items() if k != "raw_bytes"} for r in evidence_rows]}, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(), content_type="application/json")

    new_state = {
        "schema_version": "janus.research.big-move.prospective-state.v1",
        "pv1_id": base.PV1_ID,
        "latest_registry_run_id": run_id,
        "latest_registry_object": registry_obj,
        "latest_ledger_object": ledger_obj,
        "latest_dq_object": dq_obj,
        "latest_observation_T": max(existing_obs + new_obs).isoformat(),
        "calendar_checked_through": through.isoformat(),
        "previous_registry_run_id": base_run,
    }
    _write_state(buck, prefix, run_id, new_state)

    return {
        "schema_version": "janus.research.big-move.prospective-extension.v1",
        "status": "ok",
        "action": "extend_prospective_registry",
        "run_id": run_id,
        "generated_at": base.now(),
        "base_registry_run_id": base_run,
        "materialize_through": through.isoformat(),
        "existing_observation_dates": [d.isoformat() for d in existing_obs],
        "appended_observation_dates": [d.isoformat() for d in new_obs],
        "registry_rewritten": True,
        "existing_row_hashes_preserved": True,
        "added_registry_rows": int(len(new_rows)),
        "registry_row_count": int(len(registry)),
        "ledger_row_count": int(len(ledger)),
        "late_materialization_count": int((ledger["maturity_status"] == "late_materialization").sum()),
        "dq_rows": int(len(dq)),
        "duplicate_primary_key_count": int(dq["duplicate_primary_key_count"].sum()),
        "conflicting_row_hash_count": int(dq["conflicting_row_hash_count"].sum()),
        "registry_object": registry_obj,
        "ledger_object": ledger_obj,
        "dq_object": dq_obj,
        "calendar_object": calendar_obj,
        "embargo": {"mfe60_computed": False, "event_seed_computed": False, "lift_computed": False, "pass_fail_evaluated": False},
        "isolation": {"postgresql_used": False, "database_used": False, "existing_janus_iceberg_catalog_used": False, "janus_core_written": False, "janus_mart_written": False, "janus_private_mart_written": False, "runtime_secret_used": False, "official_public_twse_http_used": True},
        "next_gate": "continue weekly pre-outcome append until frozen PV1 window complete; keep H60 outcome embargo",
    }


def self_test() -> None:
    assert _state_object("a/b") == "a/b/prospective/pv1/state/latest_registry.json"
    assert _revision_root("a/b", "r1") == "a/b/prospective/pv1/revisions/r1"
    q = pd.DataFrame([{c: None for c in ["panel_id", "observation_T", "stock_id", "row_hash", "composite_score", "s90_flag", "s80_flag", "s70_flag", "supersedes_row_hash"] + [f"feature_{f}" for f in FEATURES]}])
    q.loc[0, ["panel_id", "observation_T", "stock_id", "row_hash"]] = ["p", "2026-09-17", "2330", "h"]
    assert len(q) == 1
