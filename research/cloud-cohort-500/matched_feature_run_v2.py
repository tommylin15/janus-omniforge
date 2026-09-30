from __future__ import annotations

import gc
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
import matched_feature_run as legacy

PRIMARY_HORIZON = 60
SEED_FRACTION = 0.10
NEGATIVE_RANK_FLOOR = 0.20
CONTAMINATION_GAP_TD = 10
CONTROLS_PER_EVENT = 3
FEATURES = legacy.FEATURES


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_date(v: Any) -> date | None:
    return cohort_build.d(v)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_h60_valid_compact(obs_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read only valid H60 rows in bounded Arrow batches.

    Returns stock_id object array, T as int64 ns, and MFE float64.
    The full two-horizon observations frame is never materialized.
    """
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(obs_path)
    sid_parts: list[np.ndarray] = []
    t_parts: list[np.ndarray] = []
    mfe_parts: list[np.ndarray] = []
    for batch in pf.iter_batches(
        batch_size=65536,
        columns=["stock_id", "t", "horizon", "status", "mfe"],
    ):
        df = batch.to_pandas()
        h = pd.to_numeric(df["horizon"], errors="coerce").to_numpy(dtype=float)
        status = df["status"].astype(str).to_numpy(dtype=object)
        mfe = pd.to_numeric(df["mfe"], errors="coerce").to_numpy(dtype=float)
        mask = (h == PRIMARY_HORIZON) & (status == "valid") & np.isfinite(mfe)
        if np.any(mask):
            sid_parts.append(df.loc[mask, "stock_id"].astype(str).to_numpy(dtype=object))
            ts = pd.to_datetime(df.loc[mask, "t"], errors="raise").to_numpy(dtype="datetime64[ns]").astype(np.int64)
            t_parts.append(ts)
            mfe_parts.append(mfe[mask].astype(np.float64, copy=False))
        del df, h, status, mfe, mask, batch
    if not sid_parts:
        raise RuntimeError("no valid H60 observations")
    sid = np.concatenate(sid_parts)
    t_ns = np.concatenate(t_parts).astype(np.int64, copy=False)
    mfe = np.concatenate(mfe_parts).astype(np.float64, copy=False)
    return sid, t_ns, mfe


def _rank_candidates(
    sid: np.ndarray,
    t_ns: np.ndarray,
    mfe: np.ndarray,
    anchor_ns: np.ndarray,
) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray, int]:
    """Reproduce deterministic global H60 ranking and keep negative-pool anchor rows."""
    symbols = sorted({str(x) for x in sid.tolist()})
    sid_to_code = {s: i for i, s in enumerate(symbols)}
    sid_code = np.fromiter((sid_to_code[str(x)] for x in sid), dtype=np.int32, count=len(sid))

    # np.lexsort uses the last key as primary: MFE desc, stock_id asc, T asc.
    order = np.lexsort((t_ns, sid_code, -mfe))
    n = len(order)
    rank_fraction = np.empty(n, dtype=np.float32)
    rank_fraction[order] = (np.arange(1, n + 1, dtype=np.float64) / n).astype(np.float32)

    at_anchor = np.isin(t_ns, anchor_ns)
    neg = (rank_fraction > NEGATIVE_RANK_FLOOR) & at_anchor
    c_sid = sid_code[neg]
    c_t = t_ns[neg]
    c_mfe = mfe[neg].astype(np.float32, copy=False)
    return symbols, c_sid, c_t, c_mfe, n


def _filter_contaminated(
    c_sid: np.ndarray,
    c_t: np.ndarray,
    seed_pos: dict[int, np.ndarray],
    cal_pos: dict[int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    keep = np.ones(len(c_sid), dtype=bool)
    order = np.argsort(c_sid, kind="mergesort")
    sorted_sid = c_sid[order]
    uniq, starts, counts = np.unique(sorted_sid, return_index=True, return_counts=True)
    for code, start, count in zip(uniq.tolist(), starts.tolist(), counts.tolist()):
        idx = order[start:start + count]
        sp = seed_pos.get(int(code))
        if sp is None or len(sp) == 0:
            continue
        pos = np.fromiter((cal_pos.get(int(x), -10**9) for x in c_t[idx]), dtype=np.int32, count=len(idx))
        j = np.searchsorted(sp, pos, side="left")
        left = np.where(j > 0, np.abs(pos - sp[np.maximum(j - 1, 0)]), 10**9)
        j2 = np.minimum(j, len(sp) - 1)
        right = np.where(j < len(sp), np.abs(pos - sp[j2]), 10**9)
        keep[idx] = np.minimum(left, right) > CONTAMINATION_GAP_TD
    return c_sid[keep], c_t[keep], keep


def _nearest_three(
    event_sid_code: int,
    event_liq: float,
    sid_codes: np.ndarray,
    liq: np.ndarray,
    used: set[int],
) -> np.ndarray:
    allowed = sid_codes != int(event_sid_code)
    if used:
        used_arr = np.fromiter(sorted(used), dtype=np.int32)
        allowed &= ~np.isin(sid_codes, used_arr)
    idx = np.flatnonzero(allowed)
    if len(idx) < CONTROLS_PER_EVENT:
        return np.asarray([], dtype=np.int64)
    dist = np.abs(np.log1p(liq[idx]) - math.log1p(event_liq))
    # sid code follows sorted symbol order, so tie-breaking matches stock_id asc.
    local_order = np.lexsort((sid_codes[idx], dist))
    return idx[local_order[:CONTROLS_PER_EVENT]]


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
        events["stock_id"] = events["stock_id"].astype(str)
        events["anchor_ts"] = pd.to_datetime(events["anchor_t"], errors="raise")
        events["anchor_ns"] = events["anchor_ts"].to_numpy(dtype="datetime64[ns]").astype(np.int64)
        anchor_ns = np.unique(events["anchor_ns"].to_numpy(dtype=np.int64))

        sid, t_ns, mfe = _read_h60_valid_compact(obs_path)
        symbols, c_sid, c_t, c_mfe, valid_h60_count = _rank_candidates(sid, t_ns, mfe, anchor_ns)
        sid_to_code = {s: i for i, s in enumerate(symbols)}
        del sid, t_ns, mfe
        gc.collect()

        missing_event_symbols = sorted(set(events["stock_id"]) - set(symbols))
        if missing_event_symbols:
            raise RuntimeError(f"event symbols missing from valid H60 universe: {missing_event_symbols[:10]}")
        events["sid_code"] = events["stock_id"].map(sid_to_code).astype(np.int32)

        base = f"janus_step2a_materialized/{materialized_revision}/"
        with zipfile.ZipFile(source_path) as z:
            anchor_dates = [pd.Timestamp(x).date() for x in events["anchor_ts"]]
            calendar, calendar_meta = cohort_build.calendar(z, base, min(anchor_dates), max(anchor_dates))
            cal_ns = np.asarray(calendar, dtype="datetime64[D]").astype("datetime64[ns]").astype(np.int64)
            cal_pos = {int(x): i for i, x in enumerate(cal_ns.tolist())}

            seed_pos: dict[int, list[int]] = defaultdict(list)
            for r in events.itertuples(index=False):
                code = int(r.sid_code)
                for ts in str(r.seed_ts).split("|"):
                    d = pd.Timestamp(ts).to_datetime64().astype("datetime64[ns]").astype(np.int64)
                    p = cal_pos.get(int(d))
                    if p is not None:
                        seed_pos[code].append(p)
            seed_pos_np = {k: np.asarray(sorted(set(v)), dtype=np.int32) for k, v in seed_pos.items()}
            c_sid, c_t, keep = _filter_contaminated(c_sid, c_t, seed_pos_np, cal_pos)
            c_mfe = c_mfe[keep]
            del keep, seed_pos, seed_pos_np
            gc.collect()

            # Stream per symbol: compute event liquidity and candidate liquidity without a giant tuple-key dict.
            event_liq: dict[str, float] = {}
            cand_t_chunks: list[np.ndarray] = []
            cand_sid_chunks: list[np.ndarray] = []
            cand_liq_chunks: list[np.ndarray] = []
            cand_mfe_chunks: list[np.ndarray] = []

            c_order = np.argsort(c_sid, kind="mergesort")
            c_sid_sorted = c_sid[c_order]
            c_t_sorted = c_t[c_order]
            c_mfe_sorted = c_mfe[c_order]
            c_uniq, c_starts, c_counts = np.unique(c_sid_sorted, return_index=True, return_counts=True)
            c_ranges = {int(code): (int(st), int(ct)) for code, st, ct in zip(c_uniq, c_starts, c_counts)}
            event_groups = {int(code): g.copy() for code, g in events.groupby("sid_code", sort=False)}
            needed_codes = sorted(set(c_ranges) | set(event_groups))

            for code in needed_codes:
                sid_str = symbols[code]
                vw = legacy._view(legacy._load_prices(z, base, sid_str))

                eg = event_groups.get(code)
                if eg is not None:
                    for er in eg.itertuples(index=False):
                        x = legacy._turnover_med20(vw, pd.Timestamp(er.anchor_ts).date())
                        if x is not None:
                            event_liq[str(er.event_id)] = float(x)

                rg = c_ranges.get(code)
                if rg is not None:
                    st, ct = rg
                    ts = c_t_sorted[st:st + ct]
                    mf = c_mfe_sorted[st:st + ct]
                    out_t: list[int] = []
                    out_liq: list[float] = []
                    out_mfe: list[float] = []
                    for tval, mval in zip(ts.tolist(), mf.tolist()):
                        x = legacy._turnover_med20(vw, pd.Timestamp(int(tval), unit="ns").date())
                        if x is not None:
                            out_t.append(int(tval))
                            out_liq.append(float(x))
                            out_mfe.append(float(mval))
                    if out_t:
                        n = len(out_t)
                        cand_t_chunks.append(np.asarray(out_t, dtype=np.int64))
                        cand_sid_chunks.append(np.full(n, code, dtype=np.int32))
                        cand_liq_chunks.append(np.asarray(out_liq, dtype=np.float64))
                        cand_mfe_chunks.append(np.asarray(out_mfe, dtype=np.float32))
                del vw

            if not cand_t_chunks:
                raise RuntimeError("no eligible exact-date control candidates with liquidity")
            cand_t = np.concatenate(cand_t_chunks)
            cand_sid_code = np.concatenate(cand_sid_chunks)
            cand_liq = np.concatenate(cand_liq_chunks)
            cand_mfe60 = np.concatenate(cand_mfe_chunks)
            del cand_t_chunks, cand_sid_chunks, cand_liq_chunks, cand_mfe_chunks
            del c_sid, c_t, c_mfe, c_sid_sorted, c_t_sorted, c_mfe_sorted, c_order, c_ranges, event_groups
            gc.collect()

            # Sort compact candidate arrays by date and keep only tiny date->slice metadata.
            order_t = np.argsort(cand_t, kind="mergesort")
            cand_t = cand_t[order_t]
            cand_sid_code = cand_sid_code[order_t]
            cand_liq = cand_liq[order_t]
            cand_mfe60 = cand_mfe60[order_t]
            uniq_t, starts, counts = np.unique(cand_t, return_index=True, return_counts=True)
            t_slices = {int(t): (int(st), int(ct)) for t, st, ct in zip(uniq_t, starts, counts)}

            assignments: list[dict[str, Any]] = []
            unmatched: list[dict[str, Any]] = []
            used_by_t: dict[int, set[int]] = defaultdict(set)
            event_rows = events.sort_values(["anchor_ns", "event_id"], kind="mergesort")
            for er in event_rows.itertuples(index=False):
                eid = str(er.event_id)
                eli = event_liq.get(eid)
                tval = int(er.anchor_ns)
                if eli is None:
                    unmatched.append({"event_id": eid, "stock_id": str(er.stock_id), "anchor_t": str(er.anchor_t), "reason": "missing_event_turnover_med_20"})
                    continue
                sl = t_slices.get(tval)
                if sl is None:
                    unmatched.append({"event_id": eid, "stock_id": str(er.stock_id), "anchor_t": str(er.anchor_t), "reason": "fewer_than_3_exact_date_controls"})
                    continue
                st, ct = sl
                local = _nearest_three(
                    int(er.sid_code),
                    float(eli),
                    cand_sid_code[st:st + ct],
                    cand_liq[st:st + ct],
                    used_by_t[tval],
                )
                if len(local) < CONTROLS_PER_EVENT:
                    unmatched.append({"event_id": eid, "stock_id": str(er.stock_id), "anchor_t": str(er.anchor_t), "reason": "fewer_than_3_exact_date_controls"})
                    continue
                for control_rank, j in enumerate(local.tolist(), start=1):
                    jj = st + int(j)
                    code = int(cand_sid_code[jj])
                    used_by_t[tval].add(code)
                    assignments.append({
                        "event_id": eid,
                        "event_stock_id": str(er.stock_id),
                        "anchor_t": str(er.anchor_t),
                        "control_rank": control_rank,
                        "control_stock_id": symbols[code],
                        "event_turnover_med_20": float(eli),
                        "control_turnover_med_20": float(cand_liq[jj]),
                        "abs_log_turnover_distance": float(abs(math.log1p(eli) - math.log1p(float(cand_liq[jj])))),
                        "control_mfe60": float(cand_mfe60[jj]),
                    })

            matched_event_ids = sorted({a["event_id"] for a in assignments})
            match_rate = len(matched_event_ids) / len(events)
            if match_rate < 0.90:
                raise RuntimeError(f"matched-event coverage below 90%: {match_rate:.4f}")

            # Candidate arrays are no longer needed before full feature calculation.
            del cand_t, cand_sid_code, cand_liq, cand_mfe60, order_t, uniq_t, starts, counts, t_slices, used_by_t
            gc.collect()

            event_lookup = {str(r.event_id): r for r in events.itertuples(index=False)}
            by_event_assign: dict[str, list[dict[str, Any]]] = defaultdict(list)
            full_need: dict[str, set[date]] = defaultdict(set)
            for a in assignments:
                by_event_assign[a["event_id"]].append(a)
                full_need[str(a["control_stock_id"])].add(pd.Timestamp(a["anchor_t"]).date())
            for eid in matched_event_ids:
                er = event_lookup[eid]
                full_need[str(er.stock_id)].add(pd.Timestamp(er.anchor_ts).date())

            feature_map: dict[tuple[str, date], dict[str, Any]] = {}
            for sid_str, dates in sorted(full_need.items()):
                vw = legacy._view(legacy._load_prices(z, base, sid_str))
                for t in sorted(dates):
                    f = legacy.feature_at_view(vw, t)
                    if f is not None:
                        feature_map[(sid_str, t)] = f
                del vw

        paired_rows: list[dict[str, Any]] = []
        for eid in matched_event_ids:
            er = event_lookup[eid]
            t = pd.Timestamp(er.anchor_ts).date()
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
                ev = legacy._finite(ef.get(feat))
                cvs: list[float] = []
                for a in controls:
                    cf = feature_map.get((str(a["control_stock_id"]), t), {})
                    x = legacy._finite(cf.get(feat))
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
            all_e: list[float] = []
            all_c: list[float] = []
            for eid in paired.loc[good.index, "event_id"].tolist():
                er = event_lookup[eid]
                t = pd.Timestamp(er.anchor_ts).date()
                ev = legacy._finite(feature_map.get((str(er.stock_id), t), {}).get(feat))
                if ev is not None:
                    all_e.append(ev)
                for a in by_event_assign[eid]:
                    cv = legacy._finite(feature_map.get((str(a["control_stock_id"]), t), {}).get(feat))
                    if cv is not None:
                        all_c.append(cv)
            diffs = good[dc].to_numpy(dtype=float)
            auc = legacy._descriptive_auc(np.asarray(all_e, dtype=float), np.asarray(all_c, dtype=float))
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
            "schema_version": "janus.research.big-move.matched-antecedent.v2",
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
                "execution_memory_strategy": "bounded H60 Arrow batches + compact numpy candidate arrays + per-symbol streaming; no full observation frame or candidate tuple-key liquidity map",
            },
            "matching": {
                "event_count": int(len(events)),
                "matched_event_count": int(len(matched_event_ids)),
                "matched_event_rate": float(match_rate),
                "control_assignment_count": int(len(assignments_df)),
                "unmatched_event_count": int(len(unmatched_df)),
                "median_abs_log_turnover_distance": None if assignments_df.empty else float(assignments_df["abs_log_turnover_distance"].median()),
                "valid_h60_count": int(valid_h60_count),
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
    sid = np.asarray([0, 1, 2, 3], dtype=np.int32)
    liq = np.asarray([100.0, 105.0, 300.0, 95.0], dtype=float)
    picked = _nearest_three(0, 100.0, sid, liq, set())
    assert picked.tolist() == [3, 1, 2]
    picked2 = _nearest_three(0, 100.0, sid, liq, {3})
    assert picked2.tolist() == [1, 2, 3] or len(picked2) == 0
    # Real feature arithmetic remains covered by legacy self-test in the same image build.
