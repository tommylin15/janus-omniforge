from __future__ import annotations

import hashlib
import json
import math
import tempfile
import zipfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import cohort_build

PRIMARY_HORIZON = 60
SECONDARY_HORIZON = 20
DEFAULT_SEED_FRACTION = 0.10
DEFAULT_PRIMARY_GAP = 7
DEFAULT_GAP_SENSITIVITY = (5, 7, 10)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_date(v: Any) -> date | None:
    return cohort_build.d(v)


def rank_seed_frame(obs: pd.DataFrame, horizon: int, fraction: float) -> pd.DataFrame:
    q = obs[(obs["horizon"] == horizon) & (obs["status"] == "valid")].copy()
    if q.empty:
        raise RuntimeError(f"no valid H{horizon} observations")
    q["mfe"] = pd.to_numeric(q["mfe"], errors="coerce")
    q = q[np.isfinite(q["mfe"].to_numpy(dtype=float))].copy()
    q["t"] = pd.to_datetime(q["t"], errors="raise").dt.date
    q["stock_id"] = q["stock_id"].astype(str)
    q = q.sort_values(["mfe", "stock_id", "t"], ascending=[False, True, True], kind="mergesort").reset_index(drop=True)
    n = len(q)
    k = max(1, int(math.ceil(n * float(fraction))))
    q["rank_1based"] = np.arange(1, n + 1, dtype=int)
    q["rank_fraction"] = q["rank_1based"] / n
    q["is_seed"] = q["rank_1based"] <= k
    return q


def _calendar_positions(calendar: list[date]) -> dict[date, int]:
    return {d: i for i, d in enumerate(calendar)}


def eventize_symbol_seeds(g: pd.DataFrame, cal_pos: dict[date, int], max_gap: int) -> list[list[int]]:
    idxs = list(g.index)
    if not idxs:
        return []
    components: list[list[int]] = [[idxs[0]]]
    prev_t = g.loc[idxs[0], "t"]
    if prev_t not in cal_pos:
        raise RuntimeError(f"seed T not in trading calendar: {prev_t}")
    for idx in idxs[1:]:
        t = g.loc[idx, "t"]
        if t not in cal_pos:
            raise RuntimeError(f"seed T not in trading calendar: {t}")
        gap = cal_pos[t] - cal_pos[prev_t]
        if gap <= max_gap:
            components[-1].append(idx)
        else:
            components.append([idx])
        prev_t = t
    return components


def build_events(primary_seeds: pd.DataFrame, secondary_seeds: pd.DataFrame, all_h20_valid: pd.DataFrame, calendar: list[date], max_gap: int) -> pd.DataFrame:
    cal_pos = _calendar_positions(calendar)
    p = primary_seeds[primary_seeds["is_seed"]].copy()
    p = p.sort_values(["stock_id", "t", "mfe"], ascending=[True, True, False], kind="mergesort")
    s = secondary_seeds[secondary_seeds["is_seed"]].copy()
    s_key = {(str(r.stock_id), r.t): float(r.mfe) for r in s.itertuples(index=False)}
    h20 = all_h20_valid.copy()
    h20["t"] = pd.to_datetime(h20["t"], errors="raise").dt.date
    h20["stock_id"] = h20["stock_id"].astype(str)
    h20["mfe"] = pd.to_numeric(h20["mfe"], errors="coerce")

    events: list[dict[str, Any]] = []
    event_seq_by_symbol: Counter = Counter()
    for sid, g in p.groupby("stock_id", sort=True):
        g = g.sort_values("t", kind="mergesort")
        for comp in eventize_symbol_seeds(g, cal_pos, max_gap):
            x = g.loc[comp].sort_values(["t", "mfe"], ascending=[True, False], kind="mergesort")
            event_seq_by_symbol[str(sid)] += 1
            seq = event_seq_by_symbol[str(sid)]
            anchor = x.iloc[0]
            last = x.iloc[-1]
            peak = x.sort_values(["mfe", "t"], ascending=[False, True], kind="mergesort").iloc[0]
            a = anchor["t"]
            b = last["t"]
            local20 = h20[(h20["stock_id"] == str(sid)) & (h20["t"] >= a) & (h20["t"] <= b)]
            fast_seed_mfes = [s_key[(str(sid), t)] for t in x["t"].tolist() if (str(sid), t) in s_key]
            events.append({
                "event_id": f"EV60-G{max_gap:02d}-{sid}-{seq:04d}",
                "stock_id": str(sid),
                "event_seq": seq,
                "gap_trading_days": int(max_gap),
                "anchor_t": a.isoformat(),
                "last_seed_t": b.isoformat(),
                "wave_span_trading_days": int(cal_pos[b] - cal_pos[a]),
                "seed_count_h60": int(len(x)),
                "anchor_mfe60": float(anchor["mfe"]),
                "max_mfe60": float(peak["mfe"]),
                "peak_seed_t": peak["t"].isoformat(),
                "anchor_days_to_peak60": None if pd.isna(anchor.get("days_to_peak")) else int(anchor.get("days_to_peak")),
                "fast_h20_at_anchor": bool((str(sid), a) in s_key),
                "fast_h20_any_seed": bool(fast_seed_mfes),
                "max_seed_mfe20_same_t": max(fast_seed_mfes) if fast_seed_mfes else None,
                "max_valid_mfe20_within_seed_span": None if local20.empty else float(local20["mfe"].max()),
                "anchor_year": int(a.year),
                "anchor_par_value_coverage_unknown_pre2020": bool(anchor.get("par_value_coverage_unknown_pre2020", a < date(2020, 1, 1))),
                "seed_ts": "|".join(t.isoformat() for t in x["t"].tolist()),
            })
    return pd.DataFrame(events)


def validate_events(primary_seeds: pd.DataFrame, events: pd.DataFrame, calendar: list[date], max_gap: int) -> dict[str, Any]:
    seeds = primary_seeds[primary_seeds["is_seed"]].copy()
    expected = {(str(r.stock_id), r.t.isoformat()) for r in seeds.itertuples(index=False)}
    assigned: list[tuple[str, str]] = []
    for r in events.itertuples(index=False):
        for t in str(r.seed_ts).split("|"):
            if t:
                assigned.append((str(r.stock_id), t))
    counts = Counter(assigned)
    dup = [k for k, v in counts.items() if v != 1]
    missing = sorted(expected - set(assigned))
    extra = sorted(set(assigned) - expected)
    cal_pos = _calendar_positions(calendar)
    inter_event_violations = 0
    for _, g in events.groupby("stock_id", sort=False):
        g = g.sort_values("anchor_t")
        prev_last = None
        for r in g.itertuples(index=False):
            a = parse_date(r.anchor_t)
            b = parse_date(r.last_seed_t)
            if prev_last is not None and a is not None and cal_pos[a] - cal_pos[prev_last] <= max_gap:
                inter_event_violations += 1
            prev_last = b
    ok = not dup and not missing and not extra and inter_event_violations == 0
    return {
        "seed_count": int(len(expected)),
        "event_count": int(len(events)),
        "duplicate_assignment_count": len(dup),
        "missing_seed_assignment_count": len(missing),
        "extra_assignment_count": len(extra),
        "inter_event_gap_violation_count": int(inter_event_violations),
        "pass": bool(ok),
    }


def _summary_for_gap(events: pd.DataFrame, seed_count: int, gap: int) -> dict[str, Any]:
    if events.empty:
        raise RuntimeError(f"no events for gap={gap}")
    counts = events["seed_count_h60"].to_numpy(dtype=float)
    per_symbol = events.groupby("stock_id").size().sort_values(ascending=False)
    top10_symbols = max(1, int(math.ceil(per_symbol.size * 0.10)))
    return {
        "gap_trading_days": int(gap),
        "seed_count_h60": int(seed_count),
        "event_count": int(len(events)),
        "seed_to_event_reduction_rate": float(1.0 - len(events) / seed_count),
        "median_seeds_per_event": float(np.median(counts)),
        "mean_seeds_per_event": float(np.mean(counts)),
        "singleton_event_share": float(np.mean(counts == 1)),
        "symbols_with_events": int(events["stock_id"].nunique()),
        "top_10pct_symbol_event_concentration": float(per_symbol.iloc[:top10_symbols].sum() / len(events)),
        "fast_h20_at_anchor_share": float(events["fast_h20_at_anchor"].mean()),
        "fast_h20_any_seed_share": float(events["fast_h20_any_seed"].mean()),
    }


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    outcome_run_id = str(request.get("outcome_run_id", "")).strip()
    source_obj = str(request.get("source_gcs_object", "")).strip()
    expected_sha = str(request.get("source_sha256", "")).strip().lower()
    expected_size = int(request.get("source_size_bytes", 0))
    materialized_revision = str(request.get("materialized_revision", "20260917T025906Z"))
    primary_gap = int(request.get("event_gap_trading_days", DEFAULT_PRIMARY_GAP))
    gaps = tuple(int(x) for x in request.get("event_gap_sensitivity", list(DEFAULT_GAP_SENSITIVITY)))
    fraction = float(request.get("event_seed_fraction", DEFAULT_SEED_FRACTION))
    if not outcome_run_id:
        raise RuntimeError("outcome_run_id missing")
    if not source_obj or len(expected_sha) != 64 or expected_size <= 0:
        raise RuntimeError("immutable source identity missing")
    if not (0 < fraction < 0.5):
        raise RuntimeError("event_seed_fraction must be between 0 and 0.5")
    if primary_gap not in gaps:
        gaps = tuple(sorted(set(gaps + (primary_gap,))))

    from google.cloud import storage
    client = storage.Client()
    buck = client.bucket(bucket)
    outcome_obj = f"{prefix}/revisions/{outcome_run_id}/outcomes/observations.parquet"
    root = f"{prefix}/revisions/{run_id}"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        obs_path = td_path / "observations.parquet"
        source_path = td_path / "source.zip"
        buck.blob(outcome_obj).download_to_filename(obs_path)
        buck.blob(source_obj).download_to_filename(source_path)
        h = hashlib.sha256()
        with source_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        if source_path.stat().st_size != expected_size or h.hexdigest() != expected_sha:
            raise RuntimeError("staged source identity mismatch")

        obs = pd.read_parquet(obs_path, columns=[
            "stock_id", "t", "year", "horizon", "status", "mfe", "days_to_peak",
            "par_value_coverage_unknown_pre2020",
        ])
        obs["horizon"] = pd.to_numeric(obs["horizon"], errors="raise").astype(int)
        p_rank = rank_seed_frame(obs, PRIMARY_HORIZON, fraction)
        s_rank = rank_seed_frame(obs, SECONDARY_HORIZON, fraction)
        p_seeds = p_rank[p_rank["is_seed"]].copy()
        s_seeds = s_rank[s_rank["is_seed"]].copy()
        valid20 = obs[(obs["horizon"] == SECONDARY_HORIZON) & (obs["status"] == "valid")].copy()

        base = f"janus_step2a_materialized/{materialized_revision}/"
        with zipfile.ZipFile(source_path) as z:
            calendar, calendar_meta = cohort_build.calendar(z, base, min(p_seeds["t"]), max(p_seeds["t"]))

        gap_rows = []
        validations = {}
        primary_events = None
        year_rows: list[dict[str, Any]] = []
        for gap in sorted(set(gaps)):
            events = build_events(p_seeds, s_seeds, valid20, calendar, gap)
            val = validate_events(p_seeds, events, calendar, gap)
            if not val["pass"]:
                raise RuntimeError(f"eventization validation failed gap={gap}: {val}")
            validations[str(gap)] = val
            gap_rows.append(_summary_for_gap(events, len(p_seeds), gap))
            for yr, g in events.groupby("anchor_year"):
                year_rows.append({
                    "gap_trading_days": gap,
                    "anchor_year": int(yr),
                    "event_count": int(len(g)),
                    "symbols_with_events": int(g["stock_id"].nunique()),
                    "median_seeds_per_event": float(g["seed_count_h60"].median()),
                    "fast_h20_at_anchor_share": float(g["fast_h20_at_anchor"].mean()),
                })
            if gap == primary_gap:
                primary_events = events
        assert primary_events is not None

        event_fields = [
            "event_id", "stock_id", "event_seq", "gap_trading_days", "anchor_t", "last_seed_t",
            "wave_span_trading_days", "seed_count_h60", "anchor_mfe60", "max_mfe60", "peak_seed_t",
            "anchor_days_to_peak60", "fast_h20_at_anchor", "fast_h20_any_seed",
            "max_seed_mfe20_same_t", "max_valid_mfe20_within_seed_span", "anchor_year",
            "anchor_par_value_coverage_unknown_pre2020", "seed_ts",
        ]
        primary_events = primary_events[event_fields].sort_values(["anchor_t", "stock_id", "event_seq"]).reset_index(drop=True)
        summary = {
            "schema_version": "janus.research.big-move.eventization.v1",
            "status": "ok",
            "action": "eventize_waves",
            "run_id": run_id,
            "generated_at": now(),
            "input": {
                "outcome_run_id": outcome_run_id,
                "outcome_object": outcome_obj,
                "source_gcs_object": source_obj,
                "materialized_revision": materialized_revision,
            },
            "event_contract": {
                "primary_horizon": PRIMARY_HORIZON,
                "primary_seed_rule": f"exact top {fraction:.0%} by valid MFE60 rank; ties resolved deterministically by stock_id then T",
                "secondary_horizon": SECONDARY_HORIZON,
                "secondary_seed_rule": f"exact top {fraction:.0%} by valid MFE20 rank; used only as speed tag",
                "primary_gap_trading_days": primary_gap,
                "gap_sensitivity": list(sorted(set(gaps))),
                "merge_rule": "same stock; consecutive primary seeds with trading-calendar gap <= max_gap; transitive connected components",
                "anchor_rule": "earliest primary-seed T in wave; downstream antecedent features must not use post-anchor information",
            },
            "rank_seed_counts": {
                "valid_h60": int(len(p_rank)),
                "seed_h60": int(len(p_seeds)),
                "valid_h20": int(len(s_rank)),
                "seed_h20": int(len(s_seeds)),
                "h60_seed_floor_mfe_observed": float(p_seeds["mfe"].min()),
                "h20_seed_floor_mfe_observed": float(s_seeds["mfe"].min()),
            },
            "calendar": calendar_meta,
            "primary_gap_summary": next(x for x in gap_rows if x["gap_trading_days"] == primary_gap),
            "gap_sensitivity": gap_rows,
            "validation": validations[str(primary_gap)],
            "isolation": {
                "postgresql_used": False,
                "database_used": False,
                "existing_janus_iceberg_catalog_used": False,
                "janus_core_written": False,
                "janus_mart_written": False,
                "janus_private_mart_written": False,
                "runtime_secret_used": False,
            },
            "next_gate": "matched_controls_and_antecedent_feature_pack",
            "note": "Eventization is label construction only. It does not claim predictive features or set a canonical absolute-return threshold.",
        }
        buck.blob(f"{root}/events/event_manifest.csv").upload_from_string(primary_events.to_csv(index=False).encode("utf-8-sig"), content_type="text/csv")
        buck.blob(f"{root}/events/gap_sensitivity.csv").upload_from_string(pd.DataFrame(gap_rows).to_csv(index=False).encode("utf-8-sig"), content_type="text/csv")
        buck.blob(f"{root}/events/event_counts_by_year.csv").upload_from_string(pd.DataFrame(year_rows).to_csv(index=False).encode("utf-8-sig"), content_type="text/csv")
        buck.blob(f"{root}/events/eventization_summary.json").upload_from_string((json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"), content_type="application/json")
        return summary


def self_test() -> None:
    cal = [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8), date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 13), date(2026, 1, 14), date(2026, 1, 15), date(2026, 1, 16)]
    obs = pd.DataFrame([
        {"stock_id": "1101", "t": "2026-01-02", "horizon": 60, "status": "valid", "mfe": 0.50, "days_to_peak": 10, "par_value_coverage_unknown_pre2020": False},
        {"stock_id": "1101", "t": "2026-01-09", "horizon": 60, "status": "valid", "mfe": 0.45, "days_to_peak": 8, "par_value_coverage_unknown_pre2020": False},
        {"stock_id": "1101", "t": "2026-01-16", "horizon": 60, "status": "valid", "mfe": 0.40, "days_to_peak": 6, "par_value_coverage_unknown_pre2020": False},
        {"stock_id": "2330", "t": "2026-01-02", "horizon": 60, "status": "valid", "mfe": 0.35, "days_to_peak": 7, "par_value_coverage_unknown_pre2020": False},
        {"stock_id": "1101", "t": "2026-01-02", "horizon": 20, "status": "valid", "mfe": 0.20, "days_to_peak": 5, "par_value_coverage_unknown_pre2020": False},
        {"stock_id": "1101", "t": "2026-01-09", "horizon": 20, "status": "valid", "mfe": 0.10, "days_to_peak": 5, "par_value_coverage_unknown_pre2020": False},
        {"stock_id": "2330", "t": "2026-01-02", "horizon": 20, "status": "valid", "mfe": 0.15, "days_to_peak": 5, "par_value_coverage_unknown_pre2020": False},
    ])
    p = rank_seed_frame(obs, 60, 0.75)
    s = rank_seed_frame(obs, 20, 0.67)
    ev7 = build_events(p, s, obs[(obs.horizon == 20) & (obs.status == "valid")], cal, 7)
    assert len(ev7[ev7.stock_id == "1101"]) == 1
    assert int(ev7[ev7.stock_id == "1101"].iloc[0].seed_count_h60) == 3
    assert validate_events(p, ev7, cal, 7)["pass"] is True
