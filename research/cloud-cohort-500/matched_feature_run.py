from __future__ import annotations

import hashlib
import io
import json
import math
import tempfile
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import cohort_build
import eventize_run

PRIMARY_HORIZON = 60
SEED_FRACTION = 0.10
NEGATIVE_RANK_FLOOR = 0.20
CONTAMINATION_GAP_TD = 10
CONTROLS_PER_EVENT = 3

FEATURES = [
    "ret_5", "ret_20", "ret_60",
    "vol_20", "vol_60",
    "max_drawdown_20", "max_drawdown_60",
    "close_to_high_20", "close_to_high_60",
    "close_to_low_20", "close_to_low_60",
    "range_mean_20",
    "turnover_med_20", "turnover_med_60", "turnover_ratio_5_20",
    "volume_med_20", "volume_ratio_5_20",
    "turnover_z_20", "volume_z_20",
    "up_day_share_20",
    "overnight_gap_t", "intraday_return_t",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_date(v: Any) -> date | None:
    return cohort_build.d(v)


def _finite(x: Any) -> float | None:
    try:
        y = float(x)
    except (TypeError, ValueError):
        return None
    return y if math.isfinite(y) else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_prices(z: zipfile.ZipFile, base: str, sid: str) -> pd.DataFrame:
    name = f"{base}ohlcv/symbol={sid}.parquet"
    if name not in z.namelist():
        raise RuntimeError(f"missing OHLCV artifact: {name}")
    q = pd.read_parquet(io.BytesIO(z.read(name)))
    need = ["trade_date", "open", "high", "low", "close", "volume_shares", "turnover_twd"]
    miss = [c for c in need if c not in q.columns]
    if miss:
        raise RuntimeError(f"OHLCV schema missing {miss} for {sid}")
    q = q[need].copy()
    q["trade_date"] = pd.to_datetime(q["trade_date"], errors="coerce").dt.date
    for c in need[1:]:
        q[c] = pd.to_numeric(q[c], errors="coerce")
    q = q[q["trade_date"].notna()].sort_values("trade_date").reset_index(drop=True)
    if q["trade_date"].duplicated().any():
        dup = set(q.loc[q["trade_date"].duplicated(keep=False), "trade_date"])
        q = q[~q["trade_date"].isin(dup)].reset_index(drop=True)
    return q


def _view(q: pd.DataFrame) -> dict[str, Any]:
    dates = q["trade_date"].tolist()
    return {
        "pos": {d: i for i, d in enumerate(dates)},
        "dates": dates,
        "open": q["open"].to_numpy(dtype=float),
        "high": q["high"].to_numpy(dtype=float),
        "low": q["low"].to_numpy(dtype=float),
        "close": q["close"].to_numpy(dtype=float),
        "volume": q["volume_shares"].to_numpy(dtype=float),
        "turnover": q["turnover_twd"].to_numpy(dtype=float),
    }


def _turnover_med20(vw: dict[str, Any], t: date) -> float | None:
    p = vw["pos"].get(t)
    if p is None or p + 1 < 20:
        return None
    a = vw["turnover"][p-19:p+1]
    good = a[np.isfinite(a) & (a >= 0)]
    return float(np.median(good)) if len(good) >= 18 else None


def _z_last(a: np.ndarray) -> float | None:
    if len(a) == 0 or not math.isfinite(float(a[-1])):
        return None
    x = a[np.isfinite(a)]
    if len(x) < 2:
        return None
    sd = float(np.std(x, ddof=1))
    if sd <= 0:
        return None
    return float((a[-1] - np.mean(x)) / sd)


def _max_drawdown(close: np.ndarray) -> float | None:
    if len(close) < 2 or not np.all(np.isfinite(close)) or np.any(close <= 0):
        return None
    peak = np.maximum.accumulate(close)
    return float(np.min(close / peak - 1.0))


def feature_at_view(vw: dict[str, Any], t: date) -> dict[str, Any] | None:
    p = vw["pos"].get(t)
    if p is None:
        return None
    o, h, l, c = vw["open"], vw["high"], vw["low"], vw["close"]
    vol, turn = vw["volume"], vw["turnover"]
    if not (math.isfinite(c[p]) and c[p] > 0 and math.isfinite(o[p]) and o[p] > 0):
        return None
    out: dict[str, Any] = {}

    for n in (5, 20, 60):
        out[f"ret_{n}"] = float(c[p] / c[p-n] - 1.0) if p >= n and math.isfinite(c[p-n]) and c[p-n] > 0 else None

    for n in (20, 60):
        if p >= n:
            cr = c[p-n:p+1]
            if np.all(np.isfinite(cr)) and np.all(cr > 0):
                rr = cr[1:] / cr[:-1] - 1.0
                out[f"vol_{n}"] = float(np.std(rr, ddof=1)) if len(rr) >= 2 else None
            else:
                out[f"vol_{n}"] = None
        else:
            out[f"vol_{n}"] = None

        if p + 1 >= n:
            sl = slice(p-n+1, p+1)
            cw, hw, lw = c[sl], h[sl], l[sl]
            out[f"max_drawdown_{n}"] = _max_drawdown(cw)
            out[f"close_to_high_{n}"] = float(c[p] / np.max(hw) - 1.0) if np.all(np.isfinite(hw)) and np.min(hw) > 0 else None
            out[f"close_to_low_{n}"] = float(c[p] / np.min(lw) - 1.0) if np.all(np.isfinite(lw)) and np.min(lw) > 0 else None
            tv = turn[sl]
            good_t = tv[np.isfinite(tv) & (tv >= 0)]
            out[f"turnover_med_{n}"] = float(np.median(good_t)) if len(good_t) >= math.ceil(n * 0.9) else None
            if n == 20:
                vv = vol[sl]
                good_v = vv[np.isfinite(vv) & (vv >= 0)]
                out["volume_med_20"] = float(np.median(good_v)) if len(good_v) >= 18 else None
                out["range_mean_20"] = float(np.mean((hw - lw) / cw)) if np.all(np.isfinite(hw)) and np.all(np.isfinite(lw)) and np.all(np.isfinite(cw)) and np.all(cw > 0) else None
                out["turnover_z_20"] = _z_last(tv)
                out["volume_z_20"] = _z_last(vv)
        else:
            out[f"max_drawdown_{n}"] = None
            out[f"close_to_high_{n}"] = None
            out[f"close_to_low_{n}"] = None
            out[f"turnover_med_{n}"] = None
            if n == 20:
                out["volume_med_20"] = None
                out["range_mean_20"] = None
                out["turnover_z_20"] = None
                out["volume_z_20"] = None

    if p + 1 >= 20 and p >= 4:
        t20, t5 = turn[p-19:p+1], turn[p-4:p+1]
        v20, v5 = vol[p-19:p+1], vol[p-4:p+1]
        gt20, gt5 = t20[np.isfinite(t20) & (t20 >= 0)], t5[np.isfinite(t5) & (t5 >= 0)]
        gv20, gv5 = v20[np.isfinite(v20) & (v20 >= 0)], v5[np.isfinite(v5) & (v5 >= 0)]
        tm20 = float(np.median(gt20)) if len(gt20) >= 18 else None
        tm5 = float(np.median(gt5)) if len(gt5) >= 5 else None
        vm20 = float(np.median(gv20)) if len(gv20) >= 18 else None
        vm5 = float(np.median(gv5)) if len(gv5) >= 5 else None
        out["turnover_ratio_5_20"] = tm5 / tm20 - 1.0 if tm5 is not None and tm20 is not None and tm20 > 0 else None
        out["volume_ratio_5_20"] = vm5 / vm20 - 1.0 if vm5 is not None and vm20 is not None and vm20 > 0 else None
    else:
        out["turnover_ratio_5_20"] = None
        out["volume_ratio_5_20"] = None

    if p >= 20:
        c21 = c[p-20:p+1]
        if np.all(np.isfinite(c21)) and np.all(c21 > 0):
            rr = c21[1:] / c21[:-1] - 1.0
            out["up_day_share_20"] = float(np.mean(rr > 0))
        else:
            out["up_day_share_20"] = None
    else:
        out["up_day_share_20"] = None

    out["overnight_gap_t"] = float(o[p] / c[p-1] - 1.0) if p >= 1 and math.isfinite(c[p-1]) and c[p-1] > 0 else None
    out["intraday_return_t"] = float(c[p] / o[p] - 1.0)
    return out


def feature_at(q: pd.DataFrame, t: date) -> dict[str, Any] | None:
    return feature_at_view(_view(q), t)


def _descriptive_auc(event_vals: np.ndarray, control_vals: np.ndarray) -> float | None:
    e = event_vals[np.isfinite(event_vals)]
    c = control_vals[np.isfinite(control_vals)]
    if len(e) == 0 or len(c) == 0:
        return None
    x = np.concatenate([e, c])
    ranks = pd.Series(x).rank(method="average").to_numpy(dtype=float)
    n1, n0 = len(e), len(c)
    u = float(np.sum(ranks[:n1]) - n1 * (n1 + 1) / 2)
    return float(u / (n1 * n0))


def _contaminated(sid: str, t: date, seed_pos: dict[str, list[int]], cal_pos: dict[date, int]) -> bool:
    p = cal_pos.get(t)
    if p is None:
        return True
    return any(abs(p - s) <= CONTAMINATION_GAP_TD for s in seed_pos.get(sid, []))


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    outcome_run_id = str(request.get("outcome_run_id", "")).strip()
    event_run_id = str(request.get("event_run_id", "")).strip()
    source_obj = str(request.get("source_gcs_object", "")).strip()
    expected_sha = str(request.get("source_sha256", "")).strip().lower()
    expected_size = int(request.get("source_size_bytes", 0))
    materialized_revision = str(request.get("materialized_revision", "20260917T025906Z"))
    if not outcome_run_id or not event_run_id:
        raise RuntimeError("outcome_run_id and event_run_id are required")
    if not source_obj or len(expected_sha) != 64 or expected_size <= 0:
        raise RuntimeError("immutable source identity missing")

    from google.cloud import storage
    client = storage.Client()
    buck = client.bucket(bucket)
    root = f"{prefix}/revisions/{run_id}"
    outcome_obj = f"{prefix}/revisions/{outcome_run_id}/outcomes/observations.parquet"
    event_obj = f"{prefix}/revisions/{event_run_id}/events/event_manifest.csv"

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        obs_path = td_path / "observations.parquet"
        source_path = td_path / "source.zip"
        buck.blob(outcome_obj).download_to_filename(obs_path)
        buck.blob(source_obj).download_to_filename(source_path)
        if source_path.stat().st_size != expected_size or _sha256(source_path) != expected_sha:
            raise RuntimeError("staged source identity mismatch")

        events = pd.read_csv(io.BytesIO(buck.blob(event_obj).download_as_bytes()), dtype={"stock_id": str})
        if events.empty:
            raise RuntimeError("event manifest is empty")
        events["anchor_t"] = pd.to_datetime(events["anchor_t"], errors="raise").dt.date

        obs = pd.read_parquet(obs_path, columns=["stock_id", "t", "horizon", "status", "mfe"])
        obs["stock_id"] = obs["stock_id"].astype(str)
        obs["t"] = pd.to_datetime(obs["t"], errors="raise").dt.date
        obs["horizon"] = pd.to_numeric(obs["horizon"], errors="raise").astype(int)
        rank = eventize_run.rank_seed_frame(obs, PRIMARY_HORIZON, SEED_FRACTION)
        rank = rank[["stock_id", "t", "mfe", "rank_fraction", "is_seed"]].copy()

        base = f"janus_step2a_materialized/{materialized_revision}/"
        with zipfile.ZipFile(source_path) as z:
            anchors = sorted(set(events["anchor_t"]))
            calendar, calendar_meta = cohort_build.calendar(z, base, min(anchors), max(anchors))
            cal_pos = {d: i for i, d in enumerate(calendar)}

            seed_pos: dict[str, list[int]] = defaultdict(list)
            for r in events.itertuples(index=False):
                for ts in str(r.seed_ts).split("|"):
                    d = parse_date(ts)
                    if d is not None and d in cal_pos:
                        seed_pos[str(r.stock_id)].append(cal_pos[d])

            candidates = rank[(rank["t"].isin(set(anchors))) & (rank["rank_fraction"] > NEGATIVE_RANK_FLOOR)].copy()
            keep = []
            for r in candidates.itertuples(index=False):
                keep.append(not _contaminated(str(r.stock_id), r.t, seed_pos, cal_pos))
            candidates = candidates[np.asarray(keep, dtype=bool)].copy()

            need_liq: dict[str, set[date]] = defaultdict(set)
            for r in events.itertuples(index=False):
                need_liq[str(r.stock_id)].add(r.anchor_t)
            for r in candidates.itertuples(index=False):
                need_liq[str(r.stock_id)].add(r.t)

            liq_map: dict[tuple[str, date], float] = {}
            for sid, dates in sorted(need_liq.items()):
                vw = _view(_load_prices(z, base, sid))
                for t in dates:
                    x = _turnover_med20(vw, t)
                    if x is not None:
                        liq_map[(sid, t)] = x

            cand_by_t: dict[date, list[tuple[str, float, float]]] = defaultdict(list)
            for r in candidates.itertuples(index=False):
                liq = liq_map.get((str(r.stock_id), r.t))
                if liq is not None:
                    cand_by_t[r.t].append((str(r.stock_id), liq, float(r.mfe)))

            assignments: list[dict[str, Any]] = []
            unmatched: list[dict[str, Any]] = []
            used_by_t: dict[date, set[str]] = defaultdict(set)
            for r in events.sort_values(["anchor_t", "event_id"]).itertuples(index=False):
                sid, t = str(r.stock_id), r.anchor_t
                eli = liq_map.get((sid, t))
                if eli is None:
                    unmatched.append({"event_id": r.event_id, "stock_id": sid, "anchor_t": t.isoformat(), "reason": "missing_event_turnover_med_20"})
                    continue
                pool = []
                for csid, cliq, cmfe in cand_by_t.get(t, []):
                    if csid == sid or csid in used_by_t[t]:
                        continue
                    pool.append((abs(math.log1p(eli) - math.log1p(cliq)), csid, cliq, cmfe))
                pool.sort(key=lambda x: (x[0], x[1]))
                chosen = pool[:CONTROLS_PER_EVENT]
                if len(chosen) < CONTROLS_PER_EVENT:
                    unmatched.append({"event_id": r.event_id, "stock_id": sid, "anchor_t": t.isoformat(), "reason": "fewer_than_3_exact_date_controls"})
                    continue
                for rank_i, (dist, csid, cliq, cmfe) in enumerate(chosen, start=1):
                    used_by_t[t].add(csid)
                    assignments.append({
                        "event_id": r.event_id,
                        "event_stock_id": sid,
                        "anchor_t": t.isoformat(),
                        "control_rank": rank_i,
                        "control_stock_id": csid,
                        "event_turnover_med_20": eli,
                        "control_turnover_med_20": cliq,
                        "abs_log_turnover_distance": dist,
                        "control_mfe60": cmfe,
                    })

            matched_event_ids = sorted({a["event_id"] for a in assignments})
            match_rate = len(matched_event_ids) / len(events)
            if match_rate < 0.90:
                raise RuntimeError(f"matched-event coverage below 90%: {match_rate:.4f}")

            event_lookup = {str(r.event_id): r for r in events.itertuples(index=False)}
            by_event_assign: dict[str, list[dict[str, Any]]] = defaultdict(list)
            full_need: dict[str, set[date]] = defaultdict(set)
            for a in assignments:
                by_event_assign[a["event_id"]].append(a)
                full_need[str(a["control_stock_id"])].add(parse_date(a["anchor_t"]))
            for eid in matched_event_ids:
                er = event_lookup[eid]
                full_need[str(er.stock_id)].add(er.anchor_t)

            feature_map: dict[tuple[str, date], dict[str, Any]] = {}
            for sid, dates in sorted(full_need.items()):
                vw = _view(_load_prices(z, base, sid))
                for t in sorted(d for d in dates if d is not None):
                    f = feature_at_view(vw, t)
                    if f is not None:
                        feature_map[(sid, t)] = f

        paired_rows: list[dict[str, Any]] = []
        for eid in matched_event_ids:
            er = event_lookup[eid]
            t = er.anchor_t
            ef = feature_map.get((str(er.stock_id), t), {})
            controls = by_event_assign[eid]
            rec: dict[str, Any] = {
                "event_id": eid,
                "event_stock_id": str(er.stock_id),
                "anchor_t": t.isoformat(),
                "anchor_year": int(er.anchor_year),
                "anchor_mfe60": float(er.anchor_mfe60),
                "max_mfe60": float(er.max_mfe60),
                "control_count": len(controls),
            }
            for feat in FEATURES:
                ev = _finite(ef.get(feat))
                cvs = []
                for a in controls:
                    cf = feature_map.get((str(a["control_stock_id"]), t), {})
                    x = _finite(cf.get(feat))
                    if x is not None:
                        cvs.append(x)
                cm = float(np.median(cvs)) if cvs else None
                rec[f"event__{feat}"] = ev
                rec[f"control_median__{feat}"] = cm
                rec[f"diff__{feat}"] = ev - cm if ev is not None and cm is not None else None
                rec[f"control_n__{feat}"] = len(cvs)
            paired_rows.append(rec)

        paired = pd.DataFrame(paired_rows)
        assignments_df = pd.DataFrame(assignments)
        unmatched_df = pd.DataFrame(unmatched)
        comp_rows: list[dict[str, Any]] = []
        year_rows: list[dict[str, Any]] = []

        for feat in FEATURES:
            ec, cc, dc = f"event__{feat}", f"control_median__{feat}", f"diff__{feat}"
            good = paired[[ec, cc, dc]].apply(pd.to_numeric, errors="coerce").dropna()
            if good.empty:
                continue
            all_e, all_c = [], []
            for eid in paired.loc[good.index, "event_id"].tolist():
                er = event_lookup[eid]
                t = er.anchor_t
                ev = _finite(feature_map.get((str(er.stock_id), t), {}).get(feat))
                if ev is not None:
                    all_e.append(ev)
                for a in by_event_assign[eid]:
                    cv = _finite(feature_map.get((str(a["control_stock_id"]), t), {}).get(feat))
                    if cv is not None:
                        all_c.append(cv)
            diffs = good[dc].to_numpy(dtype=float)
            auc = _descriptive_auc(np.asarray(all_e, dtype=float), np.asarray(all_c, dtype=float))
            comp_rows.append({
                "feature": feat,
                "paired_event_count": int(len(good)),
                "paired_event_coverage": float(len(good) / len(paired)),
                "event_median": float(good[ec].median()),
                "control_median": float(good[cc].median()),
                "median_paired_diff": float(np.median(diffs)),
                "mean_paired_diff": float(np.mean(diffs)),
                "event_greater_share": float(np.mean(diffs > 0)),
                "event_less_share": float(np.mean(diffs < 0)),
                "descriptive_auc": auc,
                "auc_distance_from_0_5": None if auc is None else float(abs(auc - 0.5)),
            })
            for yr, idxs in paired.groupby("anchor_year").groups.items():
                g = paired.loc[idxs, [dc]].apply(pd.to_numeric, errors="coerce").dropna()
                if not g.empty:
                    dd = g[dc].to_numpy(dtype=float)
                    year_rows.append({
                        "feature": feat,
                        "anchor_year": int(yr),
                        "paired_event_count": int(len(g)),
                        "median_paired_diff": float(np.median(dd)),
                        "event_greater_share": float(np.mean(dd > 0)),
                    })

        comp = pd.DataFrame(comp_rows)
        if not comp.empty:
            comp = comp.sort_values(["auc_distance_from_0_5", "paired_event_count"], ascending=[False, False])
        yrdf = pd.DataFrame(year_rows)
        summary = {
            "schema_version": "janus.research.big-move.matched-antecedent.v1",
            "status": "ok",
            "action": "matched_antecedent_features",
            "run_id": run_id,
            "generated_at": now(),
            "input": {"outcome_run_id": outcome_run_id, "event_run_id": event_run_id, "source_gcs_object": source_obj},
            "design": {
                "case": "primary G7 H60 top-decile wave anchor",
                "control_timing": "exact same anchor T",
                "negative_pool": "valid H60 observations with global H60 MFE rank fraction > 0.20; top 10% seed and 10-20% grey zone excluded",
                "contamination_exclusion": f"control stock excluded if any primary seed is within +/-{CONTAMINATION_GAP_TD} trading days",
                "matching_key": "nearest log1p(anchor-pre20 median turnover_twd)",
                "controls_per_event": CONTROLS_PER_EVENT,
                "control_reuse": "not allowed within same anchor T; allowed across different dates",
                "features": FEATURES,
                "feature_information_cutoff": "anchor T close or earlier only",
                "inference": "descriptive only; no p-values, no ML, no predictive claim",
            },
            "matching": {
                "event_count": int(len(events)),
                "matched_event_count": int(len(matched_event_ids)),
                "matched_event_rate": float(match_rate),
                "control_assignment_count": int(len(assignments_df)),
                "unmatched_event_count": int(len(unmatched_df)),
                "median_abs_log_turnover_distance": None if assignments_df.empty else float(assignments_df["abs_log_turnover_distance"].median()),
            },
            "feature_gate": {
                "matched_event_rate_ge_90pct": bool(match_rate >= 0.90),
                "features_with_ge_90pct_paired_coverage": int(sum(float(r["paired_event_coverage"]) >= 0.90 for r in comp_rows)),
                "feature_count": len(FEATURES),
                "decision": "DESCRIPTIVE_READY" if match_rate >= 0.90 else "BLOCKED",
            },
            "calendar": calendar_meta,
            "isolation": {
                "postgresql_used": False,
                "database_used": False,
                "existing_janus_iceberg_catalog_used": False,
                "janus_core_written": False,
                "janus_mart_written": False,
                "janus_private_mart_written": False,
                "runtime_secret_used": False,
            },
            "next_gate": "interpret_feature_stability_then_define_validation_protocol",
        }

        outputs = {
            f"{root}/matched/summary.json": (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
            f"{root}/matched/control_assignments.csv": assignments_df.to_csv(index=False).encode("utf-8-sig"),
            f"{root}/matched/unmatched_events.csv": unmatched_df.to_csv(index=False).encode("utf-8-sig"),
            f"{root}/matched/paired_features.csv": paired.to_csv(index=False).encode("utf-8-sig"),
            f"{root}/matched/feature_comparison.csv": comp.to_csv(index=False).encode("utf-8-sig"),
            f"{root}/matched/feature_by_year.csv": yrdf.to_csv(index=False).encode("utf-8-sig"),
        }
        for obj, body in outputs.items():
            buck.blob(obj).upload_from_string(body, content_type="application/json" if obj.endswith(".json") else "text/csv")
        return summary


def self_test() -> None:
    q = pd.DataFrame({
        "trade_date": pd.date_range("2026-01-01", periods=70, freq="D").date,
        "open": np.linspace(10, 12, 70),
        "high": np.linspace(10.2, 12.2, 70),
        "low": np.linspace(9.8, 11.8, 70),
        "close": np.linspace(10.1, 12.1, 70),
        "volume_shares": np.linspace(1000, 2000, 70),
        "turnover_twd": np.linspace(10000, 25000, 70),
    })
    vw = _view(q)
    t = q.iloc[-1]["trade_date"]
    assert _turnover_med20(vw, t) is not None
    f = feature_at_view(vw, t)
    assert f is not None and f["ret_60"] is not None and f["close_to_high_20"] <= 0
    assert _descriptive_auc(np.array([3.0, 4.0]), np.array([1.0, 2.0])) == 1.0
