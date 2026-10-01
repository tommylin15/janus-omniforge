from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import tempfile
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from google.cloud import storage

import cohort_build
import matched_feature_run as feature_impl
import outcome_run
import validation_run

MI_INDEX = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
HOLIDAY = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
UA = "janus-research-cloud-cohort-500-prospective/1.0 (+research-only)"
FEATURES = list(validation_run.FEATURES)
HIGHER_SIGNAL = set(validation_run.HIGHER_SIGNAL)
MIN_FEATURES = int(validation_run.MIN_FEATURES)
PV1_ID = "cloud-cohort-500-pv1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return sha_bytes(body)


def parse_date(v: Any) -> date | None:
    return cohort_build.d(v)


def iso(v: date | None) -> str:
    return v.isoformat() if v else ""


def truthy(v: Any) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def _clean_number(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s in {"--", "---", "-", "N/A", "nan", "None"}:
        return None
    s = re.sub(r"^[A-Za-z]+", "", s)
    try:
        x = float(s)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def _http_json(url: str, params: dict[str, Any] | None = None) -> tuple[Any, bytes, dict[str, Any]]:
    r = requests.get(url, params=params, timeout=60, headers={"User-Agent": UA, "Accept": "application/json"})
    r.raise_for_status()
    raw = r.content
    payload = r.json()
    meta = {"url": r.url, "fetched_at": now(), "size_bytes": len(raw), "sha256": sha_bytes(raw)}
    return payload, raw, meta


def _holiday_dates(payload: Any, year: int) -> set[date]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = [r for r in payload if isinstance(r, dict)]
    elif isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                rows.extend(v)
    out: set[date] = set()
    for r in rows:
        dt = None
        for k, v in r.items():
            lk = str(k).lower()
            if "date" in lk or "日期" in str(k):
                dt = parse_date(v)
                if dt:
                    break
        if not dt or dt.year != year:
            continue
        text = " ".join(str(v) for k, v in r.items() if "date" not in str(k).lower() and "日期" not in str(k))
        if "開始交易" in text or "最後交易" in text:
            continue
        if any(token in text for token in ("放假", "無交易", "休市")):
            out.add(dt)
    return out


def _find_ohlc_table(payload: dict[str, Any]) -> tuple[list[str], list[list[Any]]] | None:
    if str(payload.get("stat", "")).upper() != "OK":
        return None
    for t in payload.get("tables", []):
        fields = [str(x).strip() for x in t.get("fields", [])]
        data = t.get("data", [])
        required = {"證券代號", "開盤價", "最高價", "最低價", "收盤價"}
        if required.issubset(set(fields)) and isinstance(data, list):
            return fields, data
    return None


def _parse_mi_index(payload: dict[str, Any], trade_date: date) -> pd.DataFrame:
    table = _find_ohlc_table(payload)
    if table is None:
        raise RuntimeError(f"MI_INDEX missing OHLC table for expected trading day {trade_date}: stat={payload.get('stat')!r}")
    fields, data = table
    idx = {name: fields.index(name) for name in fields}
    vol_col = next((x for x in ("成交股數", "成交單位") if x in idx), None)
    turn_col = next((x for x in ("成交金額",) if x in idx), None)
    rows: list[dict[str, Any]] = []
    for r in data:
        if not isinstance(r, list) or len(r) < len(fields):
            continue
        sid = str(r[idx["證券代號"]]).strip()
        if not re.fullmatch(r"\d{4}", sid):
            continue
        o = _clean_number(r[idx["開盤價"]])
        h = _clean_number(r[idx["最高價"]])
        l = _clean_number(r[idx["最低價"]])
        c = _clean_number(r[idx["收盤價"]])
        vol = _clean_number(r[idx[vol_col]]) if vol_col else None
        turn = _clean_number(r[idx[turn_col]]) if turn_col else None
        rows.append({
            "stock_id": sid,
            "trade_date": trade_date,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume_shares": vol,
            "turnover_twd": turn,
        })
    q = pd.DataFrame(rows)
    if q.empty or q["stock_id"].nunique() < 500:
        raise RuntimeError(f"MI_INDEX parsed too few 4-digit securities for {trade_date}: {q['stock_id'].nunique() if not q.empty else 0}")
    if q["stock_id"].duplicated().any():
        raise RuntimeError(f"MI_INDEX duplicate stock_id on {trade_date}")
    return q


def _read_panel(buck: Any, prefix: str, run_id: str, panel_id: str) -> pd.DataFrame:
    obj = f"{prefix}/revisions/{run_id}/cohort/cohort_manifest.csv"
    raw = buck.blob(obj).download_as_bytes()
    q = pd.read_csv(io.BytesIO(raw), dtype=str).fillna("")
    need = {"stock_id", "selected", "effective_start", "effective_end_exclusive"}
    miss = sorted(need - set(q.columns))
    if miss:
        raise RuntimeError(f"{panel_id} cohort manifest missing columns: {miss}")
    q = q[q["selected"].map(truthy)].copy()
    q["stock_id"] = q["stock_id"].astype(str)
    if len(q) != 500:
        raise RuntimeError(f"{panel_id} frozen panel size must be 500; got {len(q)}")
    if q["stock_id"].duplicated().any():
        raise RuntimeError(f"{panel_id} frozen panel has duplicate stock_id")
    q["panel_id"] = panel_id
    q["cohort_revision"] = run_id
    return q.sort_values("stock_id").reset_index(drop=True)


def _official_calendar(start: date, end: date) -> tuple[list[date], dict[date, pd.DataFrame], list[dict[str, Any]], tuple[bytes, dict[str, Any]]]:
    if end < start:
        raise RuntimeError("prospective materialize end before start")
    hp, hraw, hmeta = _http_json(HOLIDAY)
    holidays = _holiday_dates(hp, start.year)
    if not holidays:
        raise RuntimeError("TWSE holiday schedule produced no parseable dates")

    trading: list[date] = []
    frames: dict[date, pd.DataFrame] = {}
    evidence: list[dict[str, Any]] = []
    dt = start
    while dt <= end:
        if dt.weekday() >= 5:
            evidence.append({"date": iso(dt), "status": "weekend", "source": "calendar"})
            dt += timedelta(days=1)
            continue
        if dt in holidays:
            evidence.append({"date": iso(dt), "status": "official_holiday", "source": hmeta["url"]})
            dt += timedelta(days=1)
            continue
        payload, raw, meta = _http_json(MI_INDEX, {"response": "json", "date": dt.strftime("%Y%m%d"), "type": "ALL"})
        q = _parse_mi_index(payload, dt)
        trading.append(dt)
        frames[dt] = q
        evidence.append({"date": iso(dt), "status": "trading_day", **meta, "raw_bytes": raw})
        dt += timedelta(days=1)
    return trading, frames, evidence, (hraw, hmeta)


def _combine_price(hist: pd.DataFrame, post: pd.DataFrame) -> pd.DataFrame:
    cols = ["trade_date", "open", "high", "low", "close", "volume_shares", "turnover_twd"]
    q = pd.concat([hist[cols], post[cols]], ignore_index=True)
    q = q.sort_values("trade_date", kind="mergesort").reset_index(drop=True)
    if q["trade_date"].duplicated().any():
        dup = q.loc[q["trade_date"].duplicated(keep=False), "trade_date"].astype(str).unique().tolist()
        raise RuntimeError(f"historical/prospective OHLC overlap or duplicate: {dup[:5]}")
    return q


def _json_scalar(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        return None if not math.isfinite(float(v)) else float(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, date):
        return v.isoformat()
    return v


def _row_hash_payload(row: dict[str, Any]) -> dict[str, Any]:
    skip = {"row_hash", "registry_revision", "generated_at", "supersedes_row_hash", "correction_reason"}
    return {k: _json_scalar(v) for k, v in row.items() if k not in skip}


def _code_revision() -> str:
    parts = []
    for mod in (validation_run, feature_impl):
        p = Path(mod.__file__)
        parts.append(f"{p.name}:{file_sha(p)}")
    return "|".join(parts)


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    if str(request.get("action", "")) != "materialize_prospective_registry":
        raise RuntimeError("unexpected action")
    if request.get("database_allowed") is not False or request.get("existing_janus_iceberg_allowed") is not False or request.get("canonical_core_mart_writes_allowed") is not False:
        raise RuntimeError("research isolation contract not fail-closed")
    if request.get("outcome_evaluation_allowed") is not False or request.get("event_label_materialization_allowed") is not False:
        raise RuntimeError("PV1 pre-outcome embargo not fail-closed")
    bands = request.get("score_bands") or {}
    if bands != {"S90": 0.9, "S80": 0.8, "S70": 0.7}:
        raise RuntimeError(f"frozen score bands changed: {bands!r}")
    if float(request.get("event_seed_fraction", 0.0)) != 0.10 or int(request.get("event_gap_trading_days", 0)) != 7:
        raise RuntimeError("frozen event definition changed")

    start = parse_date(request.get("prospective_observation_start")) or date(2026, 9, 17)
    materialize_through = parse_date(request.get("materialize_through"))
    pv1_end = parse_date(request.get("pv1_observation_end")) or date(2026, 12, 31)
    historical_cutoff = parse_date(request.get("historical_cutoff_inclusive")) or date(2026, 9, 16)
    if materialize_through is None:
        raise RuntimeError("materialize_through required")
    if start != date(2026, 9, 17) or historical_cutoff != date(2026, 9, 16):
        raise RuntimeError("PV1 frozen start/cutoff changed")
    if materialize_through > pv1_end:
        raise RuntimeError("materialize_through exceeds PV1 observation end")

    primary_run = str(request.get("primary_cohort_run_id", "")).strip()
    independent_run = str(request.get("independent_cohort_run_id", "")).strip()
    source_obj = str(request.get("source_gcs_object", "")).strip()
    source_sha = str(request.get("source_sha256", "")).strip().lower()
    source_size = int(request.get("source_size_bytes", 0))
    materialized_revision = str(request.get("materialized_revision", "20260917T025906Z"))
    if not primary_run or not independent_run or not source_obj or len(source_sha) != 64 or source_size <= 0:
        raise RuntimeError("immutable panel/source identity missing")

    client = storage.Client()
    buck = client.bucket(bucket)
    primary = _read_panel(buck, prefix, primary_run, "primary_500")
    independent = _read_panel(buck, prefix, independent_run, "independent_500")
    overlap = sorted(set(primary.stock_id) & set(independent.stock_id))
    if overlap:
        raise RuntimeError(f"frozen panel overlap is not zero: {overlap[:10]}")

    root = f"{prefix}/prospective/pv1/revisions/{run_id}"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        source_path = td_path / "source.zip"
        buck.blob(source_obj).download_to_filename(source_path)
        if source_path.stat().st_size != source_size or file_sha(source_path) != source_sha:
            raise RuntimeError("staged historical source identity mismatch")

        trading_dates, day_frames, source_evidence, holiday_evidence = _official_calendar(start, materialize_through)
        if not trading_dates:
            raise RuntimeError("no realized prospective trading days")
        obs_dates = outcome_run.weekly_first_trading_days(trading_dates)
        if not obs_dates or obs_dates[0] != start:
            raise RuntimeError(f"frozen weekly sampler mismatch: first T={obs_dates[0] if obs_dates else None} expected={start}")

        evidence_rows: list[dict[str, Any]] = []
        hraw, hmeta = holiday_evidence
        holiday_obj = f"{root}/raw/twse_holiday_schedule-{hmeta['sha256']}.json"
        buck.blob(holiday_obj).upload_from_string(hraw, content_type="application/json")
        for e in source_evidence:
            row = {k: v for k, v in e.items() if k != "raw_bytes"}
            if e.get("status") == "trading_day":
                raw = e["raw_bytes"]
                obj = f"{root}/raw/mi_index/date={e['date']}/sha256={e['sha256']}.json"
                buck.blob(obj).upload_from_string(raw, content_type="application/json")
                row["gcs_object"] = obj
            evidence_rows.append(row)

        per_t_bundle: dict[date, tuple[str, str]] = {}
        trading_evidence = [r for r in evidence_rows if r.get("status") == "trading_day"]
        for t in obs_dates:
            used = [r for r in trading_evidence if parse_date(r.get("date")) and parse_date(r.get("date")) <= t]
            bundle = {
                "historical_source": {"gcs_object": source_obj, "sha256": source_sha, "materialized_revision": materialized_revision},
                "holiday_schedule": {"gcs_object": holiday_obj, "sha256": hmeta["sha256"]},
                "prospective_daily": [{"date": r["date"], "gcs_object": r["gcs_object"], "sha256": r["sha256"]} for r in used],
            }
            body = (json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            bh = sha_bytes(body)
            obj = f"{root}/source_manifests/observation_T={t.isoformat()}-sha256={bh}.json"
            buck.blob(obj).upload_from_string(body, content_type="application/json")
            per_t_bundle[t] = (obj, bh)

        post_by_sid: dict[str, list[dict[str, Any]]] = {}
        for dt in trading_dates:
            for r in day_frames[dt].to_dict("records"):
                post_by_sid.setdefault(str(r["stock_id"]), []).append(r)

        panels = [primary, independent]
        all_rows: list[dict[str, Any]] = []
        generated = now()
        scorer_revision = _code_revision()
        base = f"janus_step2a_materialized/{materialized_revision}/"
        with zipfile.ZipFile(source_path) as z:
            for panel in panels:
                panel_rows: list[dict[str, Any]] = []
                for p in panel.itertuples(index=False):
                    sid = str(p.stock_id)
                    hist = feature_impl._load_prices(z, base, sid)
                    hist = hist[hist["trade_date"] <= historical_cutoff].copy()
                    post = pd.DataFrame(post_by_sid.get(sid, []))
                    if post.empty:
                        post = pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume_shares", "turnover_twd"])
                    combined = _combine_price(hist, post)
                    vw = feature_impl._view(combined)
                    for t in obs_dates:
                        ft = validation_run._feature8(vw, t)
                        rec: dict[str, Any] = {
                            "pv1_id": PV1_ID,
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
                    oriented = rank if f in HIGHER_SIGNAL else 1.0 - rank
                    frame[f"oriented_rank_{f}"] = oriented
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
                for t in obs_dates:
                    obj, bh = per_t_bundle[t]
                    mask = frame["observation_T"] == t.isoformat()
                    frame.loc[mask, "source_evidence_manifest_object"] = obj
                    frame.loc[mask, "source_bundle_hash"] = bh
                    frame.loc[mask, "source_evidence_refs"] = json.dumps([source_obj, obj], ensure_ascii=False, separators=(",", ":"))
                    frame.loc[mask, "source_content_hashes"] = json.dumps([source_sha, bh], ensure_ascii=False, separators=(",", ":"))
                records = frame.to_dict("records")
                for r in records:
                    normalized = {k: _json_scalar(v) for k, v in r.items()}
                    normalized["row_hash"] = stable_hash(_row_hash_payload(normalized))
                    all_rows.append(normalized)

        registry = pd.DataFrame(all_rows)
        expected_rows = 2 * 500 * len(obs_dates)
        if len(registry) != expected_rows:
            raise RuntimeError(f"registry row count mismatch: {len(registry)} != {expected_rows}")
        pk = ["panel_id", "observation_T", "stock_id"]
        if registry.duplicated(pk).any():
            raise RuntimeError("registry duplicate panel/T/stock primary key")
        if any(c in registry.columns for c in ["mfe60", "future_return", "event_seed", "wave_event", "lift", "capture"]):
            raise RuntimeError("future/outcome field leaked into pre-outcome registry")

        pos = {d: i for i, d in enumerate(trading_dates)}
        ledger_rows: list[dict[str, Any]] = []
        for r in registry.to_dict("records"):
            t = parse_date(r["observation_T"])
            p = pos.get(t) if t else None
            entry = trading_dates[p + 1] if p is not None and p + 1 < len(trading_dates) else None
            realized_after_entry = 0
            if entry is not None:
                ep = pos[entry]
                realized_after_entry = len(trading_dates[ep:])
            late = realized_after_entry >= 60
            ledger_rows.append({
                "pv1_id": PV1_ID,
                "panel_id": r["panel_id"],
                "observation_T": r["observation_T"],
                "stock_id": r["stock_id"],
                "registry_row_hash": r["row_hash"],
                "entry_E": iso(entry),
                "maturity_status": "late_materialization" if late else "pending_maturity",
                "exclusion_reason": "",
                "corporate_action_evidence_refs": "",
                "corporate_action_hashes": "",
                "h60_completion_evidence": "",
                "maturity_updated_at": generated,
                "mfe60": None,
                "event_seed": None,
                "wave_event_id": None,
                "outcome_revision": "",
                "outcome_row_hash": "",
            })
        ledger = pd.DataFrame(ledger_rows)
        if (ledger["maturity_status"] == "late_materialization").any():
            raise RuntimeError("pre-outcome registry contains late-materialized observations; blind PV1 evidence invalid")

        dq_rows: list[dict[str, Any]] = []
        for (panel_id, t), g in registry.groupby(["panel_id", "observation_T"], sort=True):
            row = {
                "panel_id": panel_id,
                "observation_T": t,
                "frozen_panel_size": 500,
                "registry_rows_expected": 500,
                "registry_rows_materialized": int(len(g)),
                "registry_rows_late_materialization": 0,
                "score_eligible_rows": int(g["composite_score"].notna().sum()),
                "score_ineligible_rows": int(g["composite_score"].isna().sum()),
                "duplicate_primary_key_count": int(g.duplicated(["stock_id"]).sum()),
                "conflicting_row_hash_count": int(g["row_hash"].duplicated().sum()),
                "superseding_correction_count": 0,
                "s90_rows": int(g["s90_flag"].fillna(False).sum()),
                "s80_rows": int(g["s80_flag"].fillna(False).sum()),
                "s70_rows": int(g["s70_flag"].fillna(False).sum()),
                "maturity_pending": int(len(g)),
                "maturity_mature": 0,
                "maturity_excluded": 0,
                "maturity_unknown": 0,
            }
            for f in FEATURES:
                miss = int(g[f"feature_{f}"].isna().sum())
                row[f"missing_{f}_count"] = miss
                row[f"missing_{f}_rate"] = miss / len(g) if len(g) else None
            dq_rows.append(row)
        dq = pd.DataFrame(dq_rows)

        calendar_rows = []
        obs_set = set(obs_dates)
        for dt in trading_dates:
            calendar_rows.append({
                "trade_date": dt.isoformat(),
                "is_realized_trading_day": True,
                "is_weekly_observation_T": dt in obs_set,
                "materialized_through": materialize_through.isoformat(),
                "pv1_window_end": pv1_end.isoformat(),
            })
        calendar_df = pd.DataFrame(calendar_rows)

        registry_obj = f"{root}/registry/pre_outcome_registry.parquet"
        ledger_obj = f"{root}/ledger/maturity_outcome_ledger.parquet"
        dq_obj = f"{root}/dq/dq_summary.csv"
        calendar_obj = f"{root}/calendar/realized_observation_calendar.csv"
        source_index_obj = f"{root}/source_manifests/source_evidence_index.json"

        with tempfile.TemporaryDirectory() as outdir:
            outdir = Path(outdir)
            regp = outdir / "registry.parquet"
            ledp = outdir / "ledger.parquet"
            registry.to_parquet(regp, index=False)
            ledger.to_parquet(ledp, index=False)
            buck.blob(registry_obj).upload_from_filename(regp, content_type="application/octet-stream")
            buck.blob(ledger_obj).upload_from_filename(ledp, content_type="application/octet-stream")
        buck.blob(dq_obj).upload_from_string(dq.to_csv(index=False).encode("utf-8-sig"), content_type="text/csv")
        buck.blob(calendar_obj).upload_from_string(calendar_df.to_csv(index=False).encode("utf-8-sig"), content_type="text/csv")
        source_index = {
            "holiday_schedule": {"gcs_object": holiday_obj, **hmeta},
            "dates": [{k: v for k, v in r.items() if k != "raw_bytes"} for r in evidence_rows],
        }
        buck.blob(source_index_obj).upload_from_string((json.dumps(source_index, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(), content_type="application/json")

        summary = {
            "schema_version": "janus.research.big-move.prospective-registry.v1",
            "status": "ok",
            "action": "materialize_prospective_registry",
            "run_id": run_id,
            "generated_at": generated,
            "pv1": {
                "pv1_id": PV1_ID,
                "historical_cutoff_inclusive": historical_cutoff.isoformat(),
                "observation_start": start.isoformat(),
                "observation_end_frozen": pv1_end.isoformat(),
                "materialized_through": materialize_through.isoformat(),
                "realized_trading_days": len(trading_dates),
                "realized_observation_dates": [x.isoformat() for x in obs_dates],
                "initial_partial_week_behavior": "calendar clipped to prospective start before weekly_first_trading_days; first T is 2026-09-17, matching historical runner semantics",
                "future_calendar_status": "pending_realization",
            },
            "panels": {
                "primary_500": {"cohort_run_id": primary_run, "size": 500},
                "independent_500": {"cohort_run_id": independent_run, "size": 500},
                "stock_overlap": 0,
            },
            "score": {
                "features": FEATURES,
                "minimum_available_features": MIN_FEATURES,
                "aggregation": "same-T panel-separated oriented percentile ranks, equal-weight mean",
                "bands": {"S90": 0.90, "S80": 0.80, "S70": 0.70},
                "scorer_revision": scorer_revision,
            },
            "registry": {
                "row_count": int(len(registry)),
                "expected_row_count": int(expected_rows),
                "late_materialization_count": 0,
                "outcome_fields_present": False,
                "object": registry_obj,
            },
            "ledger": {"status": "pending_maturity_only", "row_count": int(len(ledger)), "object": ledger_obj, "mfe60_populated_count": 0},
            "dq": {
                "rows": int(len(dq)),
                "all_panel_t_rows_equal_500": bool((dq["registry_rows_materialized"] == 500).all()),
                "duplicate_primary_key_count": int(dq["duplicate_primary_key_count"].sum()),
                "conflicting_row_hash_count": int(dq["conflicting_row_hash_count"].sum()),
                "object": dq_obj,
            },
            "calendar_object": calendar_obj,
            "source_evidence_index_object": source_index_obj,
            "embargo": {
                "event_seed_computed": False,
                "mfe60_computed": False,
                "event_rate_computed": False,
                "lift_computed": False,
                "capture_computed": False,
                "spearman_computed": False,
                "pass_fail_evaluated": False,
            },
            "isolation": {
                "postgresql_used": False,
                "database_used": False,
                "existing_janus_iceberg_catalog_used": False,
                "janus_core_written": False,
                "janus_mart_written": False,
                "janus_private_mart_written": False,
                "runtime_secret_used": False,
                "official_public_twse_http_used": True,
            },
            "next_gate": "append future weekly pre-outcome rows before maturity; do not evaluate PV1 outcome until full frozen window matures",
        }
        result_obj = f"{root}/registry_result.json"
        buck.blob(result_obj).upload_from_string((json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(), content_type="application/json")
        return summary


def self_test() -> None:
    assert _clean_number("1,234.50") == 1234.5
    assert _clean_number("--") is None
    assert _clean_number("X123.00") == 123.0
    hp = [{"Date": "2026-09-25", "Name": "中秋節", "Description": "依規定放假1日。"}, {"Date": "115/09/28", "Name": "孔子誕辰紀念日", "Description": "依規定放假1日。"}]
    assert _holiday_dates(hp, 2026) == {date(2026, 9, 25), date(2026, 9, 28)}
    payload = {
        "stat": "OK",
        "tables": [{
            "fields": ["證券代號", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
            "data": [[f"{1000+i}", "1,000", "10,000", "10", "11", "9", "10.5"] for i in range(600)],
        }],
    }
    q = _parse_mi_index(payload, date(2026, 9, 17))
    assert len(q) == 600 and q.iloc[0]["close"] == 10.5
    cal = [date(2026, 9, 17), date(2026, 9, 18), date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 29)]
    assert outcome_run.weekly_first_trading_days(cal) == [date(2026, 9, 17), date(2026, 9, 21), date(2026, 9, 29)]


def main() -> int:
    bucket = os.environ["RESEARCH_BUCKET"].strip()
    prefix = os.environ["RESEARCH_PREFIX"].strip("/")
    request_object = os.environ["RESEARCH_REQUEST_OBJECT"].strip()
    run_id = os.environ["RESEARCH_RUN_ID"].strip()
    if not bucket or not prefix or not request_object or not run_id:
        raise RuntimeError("missing prospective registry environment")
    client = storage.Client()
    buck = client.bucket(bucket)
    request = json.loads(buck.blob(request_object).download_as_bytes().decode("utf-8"))
    result = run(request, bucket, prefix, run_id)
    execution_obj = f"{prefix}/executions/{run_id}/prospective_registry_result.json"
    buck.blob(execution_obj).upload_from_string((json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(), content_type="application/json")
    print(json.dumps({"status": result["status"], "action": result["action"], "run_id": run_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
