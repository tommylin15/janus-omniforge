from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

import cohort_build

HORIZONS = (20, 60)
PCTS = (0.50, 0.80, 0.90, 0.95)
DATA_UNKNOWN_STATUSES = {
    "excluded_duplicate_t",
    "excluded_missing_t",
    "excluded_invalid_t_close",
    "excluded_duplicate_entry",
    "excluded_missing_entry",
    "excluded_invalid_entry_open",
    "excluded_invalid_ohlc_horizon",
}
STRUCTURAL_EXCLUSIONS = {
    "excluded_corporate_action",
    "excluded_no_entry_calendar_date",
    "excluded_entry_outside_lifecycle",
    "excluded_incomplete_horizon",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_bytes(rows: Iterable[dict[str, Any]], fields: list[str]) -> bytes:
    s = io.StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=fields, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
    return s.getvalue().encode("utf-8-sig")


def qstats(vals: np.ndarray) -> dict[str, float | int | None]:
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return {"count": 0, "p50": None, "p80": None, "p90": None, "p95": None, "mean": None, "iqr": None}
    q25, q50, q75, q80, q90, q95 = np.quantile(vals, [0.25,0.50,0.75,0.80,0.90,0.95], method="linear")
    return {"count": int(len(vals)), "p50": float(q50), "p80": float(q80), "p90": float(q90), "p95": float(q95), "mean": float(np.mean(vals)), "iqr": float(q75-q25)}


def rank_bounds(valid: np.ndarray, missing_count: int, p: float) -> dict[str, Any]:
    valid = valid[np.isfinite(valid)]
    n = int(len(valid)); m = int(missing_count); total = n + m
    if n == 0 or total == 0:
        return {"n_valid": n, "m_unknown": m, "epsilon": None, "q_low": None, "q_high": None, "value_low": None, "value_high": None, "value_high_unbounded": True}
    eps = m / total
    denom = 1.0 - eps
    q_low = 0.0 if denom <= 0 else max(0.0, (p - eps) / denom)
    q_high = 1.0 if denom <= 0 else min(1.0, p / denom)
    value_low = 0.0 if p <= eps else float(np.quantile(valid, q_low, method="linear"))
    high_unbounded = p > 1.0 - eps
    value_high = None if high_unbounded else float(np.quantile(valid, q_high, method="linear"))
    return {"n_valid": n, "m_unknown": m, "epsilon": eps, "q_low": q_low, "q_high": q_high, "value_low": value_low, "value_high": value_high, "value_high_unbounded": high_unbounded}


def load_calendar_from_source(bucket_obj: Any, source_obj: str, expected_size: int, expected_sha: str, revision: str, start: date, end: date, td: Path) -> list[date]:
    p = td / "source.zip"
    bucket_obj.blob(source_obj).download_to_filename(p)
    if p.stat().st_size != expected_size or file_sha(p) != expected_sha:
        raise RuntimeError("staged source identity mismatch in sensitivity run")
    with zipfile.ZipFile(p) as z:
        cal, _ = cohort_build.calendar(z, f"janus_step2a_materialized/{revision}/", start, end)
    return cal


def concentration_metrics(df: pd.DataFrame, calendar: list[date], h: int) -> dict[str, Any]:
    x = df[(df.horizon == h) & (df.status == "valid") & df.mfe.notna()].copy()
    if x.empty:
        return {"horizon": h, "valid_count": 0}
    threshold = float(np.quantile(x.mfe.to_numpy(float), 0.90, method="linear"))
    top = x[x.mfe >= threshold].copy()
    counts = top.groupby("stock_id").size().sort_values(ascending=False)
    total = int(len(top))
    shares = (counts / total).to_numpy(float) if total else np.array([])
    cal_pos = {d:i for i,d in enumerate(calendar)}
    top["t_date"] = pd.to_datetime(top["t"], errors="coerce").dt.date
    adjacent = 0
    for _, g in top.groupby("stock_id"):
        pos = sorted(cal_pos[d] for d in g.t_date if d in cal_pos)
        for i, p0 in enumerate(pos):
            near = (i > 0 and p0 - pos[i-1] <= 7) or (i+1 < len(pos) and pos[i+1] - p0 <= 7)
            adjacent += int(near)
    base = df[df.horizon == h].copy()
    base["t_date"] = pd.to_datetime(base["t"], errors="coerce").dt.date
    max_counts: list[int] = []
    for _, g in base.groupby("stock_id"):
        pos = sorted(cal_pos[d] for d in g.t_date if d in cal_pos)
        left = 0; best = 0
        for right, p0 in enumerate(pos):
            while left <= right and p0 - pos[left] > 59:
                left += 1
            best = max(best, right-left+1)
        max_counts.append(best)
    return {
        "horizon": h,
        "valid_count": int(len(x)),
        "top_decile_threshold": threshold,
        "top_decile_count": total,
        "top_decile_unique_symbols": int(counts.size),
        "top_decile_max_symbol_share": float(shares.max()) if len(shares) else None,
        "top_decile_top10_symbol_share": float(shares[:10].sum()) if len(shares) else None,
        "top_decile_hhi": float(np.sum(shares**2)) if len(shares) else None,
        "top_decile_adjacent_within_7_trading_days_share": adjacent / total if total else None,
        "rolling_60_trading_day_obs_count_per_symbol_p50": float(np.quantile(max_counts,0.50,method="linear")) if max_counts else None,
        "rolling_60_trading_day_obs_count_per_symbol_p90": float(np.quantile(max_counts,0.90,method="linear")) if max_counts else None,
        "rolling_60_trading_day_obs_count_per_symbol_max": int(max(max_counts)) if max_counts else None,
    }


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    outcome_run_id = str(request.get("outcome_run_id", "")).strip()
    source_obj = str(request.get("source_gcs_object", "")).strip()
    expected_sha = str(request.get("source_sha256", "")).strip().lower()
    expected_size = int(request.get("source_size_bytes", 0))
    revision = str(request.get("materialized_revision", "20260917T025906Z"))
    start = cohort_build.d(request.get("research_start")) or date(2015,1,1)
    end = cohort_build.d(request.get("research_end")) or date(2026,9,16)
    if not outcome_run_id:
        raise RuntimeError("outcome_run_id missing")
    if not source_obj or len(expected_sha) != 64 or expected_size <= 0:
        raise RuntimeError("immutable source identity missing")

    from google.cloud import storage
    client = storage.Client(); buck = client.bucket(bucket)
    outcome_obj = f"{prefix}/revisions/{outcome_run_id}/outcomes/observations.parquet"
    summary_obj = f"{prefix}/revisions/{outcome_run_id}/dq/preflight_summary.json"
    summary = json.loads(buck.blob(summary_obj).download_as_bytes().decode("utf-8"))
    if summary.get("status") != "ok" or summary.get("cohort",{}).get("selected_symbols") != 500:
        raise RuntimeError("outcome summary is not an accepted 500-symbol run")

    with tempfile.TemporaryDirectory() as td_s:
        td = Path(td_s)
        p = td / "observations.parquet"
        buck.blob(outcome_obj).download_to_filename(p)
        cols = ["stock_id","t","year","horizon","status","mfe","par_value_coverage_unknown_pre2020"]
        df = pd.read_parquet(p, columns=cols)
        df["stock_id"] = df.stock_id.astype(str)
        df["year"] = pd.to_numeric(df.year, errors="coerce").astype("Int64")
        df["horizon"] = pd.to_numeric(df.horizon, errors="coerce").astype("Int64")
        df["mfe"] = pd.to_numeric(df.mfe, errors="coerce")
        df["par_value_coverage_unknown_pre2020"] = df.par_value_coverage_unknown_pre2020.astype(bool)
        calendar = load_calendar_from_source(buck, source_obj, expected_size, expected_sha, revision, start, end, td)

        rank_rows: list[dict[str,Any]] = []
        year_rows: list[dict[str,Any]] = []
        par_rows: list[dict[str,Any]] = []
        concentration: list[dict[str,Any]] = []
        missing_gate = True
        zero_gap = True

        for h in HORIZONS:
            x = df[df.horizon == h]
            valid = x.loc[x.status == "valid", "mfe"].dropna().to_numpy(float)
            m = int(x.status.isin(DATA_UNKNOWN_STATUSES).sum())
            potential = int(len(x)); miss_rate = m / potential if potential else 1.0
            missing_gate = missing_gate and miss_rate <= 0.10
            for pctl in PCTS:
                r = rank_bounds(valid, m, pctl)
                rank_rows.append({"scope":"pooled","year":"","horizon":h,"percentile":pctl,"potential_count":potential,"data_unknown_count":m,"data_unknown_rate":miss_rate,**r})

            for yr, g in x.groupby("year"):
                if pd.isna(yr):
                    continue
                yr = int(yr); nvalid = int((g.status == "valid").sum()); pot = int(len(g)); ym = int(g.status.isin(DATA_UNKNOWN_STATUSES).sum())
                if pot == 0 or nvalid == 0:
                    zero_gap = False
                year_rows.append({
                    "year":yr,"horizon":h,"potential_count":pot,"valid_count":nvalid,"valid_rate":nvalid/pot if pot else None,
                    "data_unknown_count":ym,"data_unknown_rate":ym/pot if pot else None,
                    "corporate_action_excluded":int((g.status=="excluded_corporate_action").sum()),
                    "incomplete_horizon_excluded":int((g.status=="excluded_incomplete_horizon").sum()),
                })

            full = qstats(valid)
            post = qstats(x.loc[(x.status=="valid") & (~x.par_value_coverage_unknown_pre2020), "mfe"].dropna().to_numpy(float))
            pre = qstats(x.loc[(x.status=="valid") & x.par_value_coverage_unknown_pre2020, "mfe"].dropna().to_numpy(float))
            for label, st in (("full",full),("post2020_known_par_value_coverage",post),("pre2020_unknown_par_value_coverage",pre)):
                par_rows.append({"horizon":h,"sample":label,**st})
            concentration.append(concentration_metrics(df, calendar, h))

        root=f"{prefix}/revisions/{run_id}"
        report = {
            "schema_version":"janus.research.cloud-cohort-500.sensitivity.v1",
            "status":"ok",
            "action":"sensitivity_and_report",
            "run_id":run_id,
            "generated_at":now(),
            "outcome_run_id":outcome_run_id,
            "gates":{
                "source_daily_coverage_gate": summary.get("dq",{}).get("cohort_coverage_gate_pass"),
                "outcome_data_unknown_rate_le_10pct_pooled": bool(missing_gate),
                "year_horizon_zero_valid_gap_screen": "PASS" if zero_gap else "FAIL",
                "par_value_pre2020_sensitivity_decision":"NOT_EVALUATED",
                "overall_research_decision":"NOT_EVALUATED",
            },
            "rank_sensitivity":{
                "unknown_definition":sorted(DATA_UNKNOWN_STATUSES),
                "structural_exclusions_not_treated_as_missing":sorted(STRUCTURAL_EXCLUSIONS),
                "mfe_lower_support":0.0,
                "method":"epsilon=m/(n+m); q_low=max(0,(p-epsilon)/(1-epsilon)); q_high=min(1,p/(1-epsilon)); lower=0 when p<=epsilon; upper unbounded when p>1-epsilon",
            },
            "par_value_sensitivity":{
                "known_coverage_start":"2020-01-01",
                "interpretation":"Full vs post-2020 vs pre-2020 distributions are a diagnostic; time/regime differences mean this is not a causal estimate of missing ParValueChange events.",
            },
            "concentration":concentration,
            "isolation":{
                "postgresql_used":False,"database_used":False,"existing_janus_iceberg_catalog_used":False,
                "janus_core_written":False,"janus_mart_written":False,"janus_private_mart_written":False,"runtime_secret_used":False,
            },
            "next_gate":"human_interpretation_and_drive_research_report",
        }
        fields_rank=["scope","year","horizon","percentile","potential_count","data_unknown_count","data_unknown_rate","n_valid","m_unknown","epsilon","q_low","q_high","value_low","value_high","value_high_unbounded"]
        fields_year=["year","horizon","potential_count","valid_count","valid_rate","data_unknown_count","data_unknown_rate","corporate_action_excluded","incomplete_horizon_excluded"]
        fields_par=["horizon","sample","count","p50","p80","p90","p95","mean","iqr"]
        fields_con=list(concentration[0].keys()) if concentration else ["horizon"]
        outputs=[
            (f"{root}/sensitivity/sensitivity_summary.json",(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode(),"application/json"),
            (f"{root}/sensitivity/percentile_rank_bounds.csv",csv_bytes(rank_rows,fields_rank),"text/csv"),
            (f"{root}/sensitivity/year_horizon_dq.csv",csv_bytes(year_rows,fields_year),"text/csv"),
            (f"{root}/sensitivity/par_value_period_comparison.csv",csv_bytes(par_rows,fields_par),"text/csv"),
            (f"{root}/sensitivity/concentration_overlap.csv",csv_bytes(concentration,fields_con),"text/csv"),
        ]
        for obj,body,ct in outputs:
            buck.blob(obj).upload_from_string(body,content_type=ct)
        return report


def self_test() -> None:
    a=np.array([0.1,0.2,0.3,0.4,0.5])
    r=rank_bounds(a,0,0.9)
    assert abs(r["value_low"]-r["value_high"]) < 1e-12
    r=rank_bounds(a,5,0.95)
    assert r["value_high_unbounded"] is True
    assert qstats(a)["count"] == 5
