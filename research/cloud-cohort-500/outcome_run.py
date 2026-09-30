from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

import cohort_build

ACTION_DATASETS = (
    "TaiwanStockDividendResult",
    "TaiwanStockCapitalReductionReferencePrice",
    "TaiwanStockSplitPrice",
    "TaiwanStockParValueChange",
)
HORIZONS = (20, 60)
PAR_VALUE_KNOWN_START = date(2020, 1, 1)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def truthy(v: Any) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def parse_date(v: Any) -> date | None:
    return cohort_build.d(v)


def iso(v: date | None) -> str:
    return v.isoformat() if v else ""


def csv_bytes(rows: Iterable[dict[str, Any]], fields: list[str]) -> bytes:
    s = io.StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return s.getvalue().encode("utf-8-sig")


def weekly_first_trading_days(calendar: list[date]) -> list[date]:
    out: list[date] = []
    seen: set[tuple[int, int]] = set()
    for dt in sorted(calendar):
        i = dt.isocalendar()
        key = (int(i.year), int(i.week))
        if key not in seen:
            seen.add(key)
            out.append(dt)
    return out


def _date_column(df: pd.DataFrame) -> str | None:
    if df.empty and not len(df.columns):
        return None
    exact = ["date", "trade_date", "ex_dividend_date", "effective_date", "change_date"]
    for c in exact:
        if c in df.columns:
            return c
    for c in df.columns:
        lc = str(c).lower()
        if "date" in lc or "日期" in str(c):
            return str(c)
    return None


def load_marketwide_par_value_dates(z: zipfile.ZipFile, base: str) -> dict[str, list[date]]:
    n = f"{base}corporate_actions/TaiwanStockParValueChange/_all.parquet"
    if n not in z.namelist():
        return {}
    q = pd.read_parquet(io.BytesIO(z.read(n)))
    if q.empty or not len(q.columns):
        return {}
    sid_col = next((c for c in ("stock_id", "StockID", "Code", "code") if c in q.columns), None)
    date_col = _date_column(q)
    if sid_col is None or date_col is None:
        raise RuntimeError(f"market-wide ParValueChange schema missing stock/date columns: {list(q.columns)}")
    out: dict[str, list[date]] = {}
    for sid, g in q.groupby(q[sid_col].astype(str).str.strip()):
        vals = sorted({x for x in (parse_date(v) for v in g[date_col].tolist()) if x is not None})
        if vals:
            out[str(sid)] = vals
    return out


def load_action_dates(
    z: zipfile.ZipFile,
    base: str,
    sid: str,
    marketwide_par_value: dict[str, list[date]],
) -> dict[str, list[date]]:
    out: dict[str, list[date]] = {}
    names = set(z.namelist())
    for dataset in ACTION_DATASETS:
        n = f"{base}corporate_actions/{dataset}/symbol={sid}.parquet"
        if n not in names:
            raise RuntimeError(f"missing corporate-action artifact: {n}")
        q = pd.read_parquet(io.BytesIO(z.read(n)))
        c = _date_column(q)
        vals: list[date] = []
        if c:
            vals = sorted({x for x in (parse_date(v) for v in q[c].tolist()) if x is not None})
        if dataset == "TaiwanStockParValueChange":
            vals = sorted(set(vals).union(marketwide_par_value.get(sid, [])))
        out[dataset] = vals
    return out


def action_hits(actions: dict[str, list[date]], t: date, h_end: date) -> list[str]:
    hits: list[str] = []
    for dataset, dates in actions.items():
        if any(t < x <= h_end for x in dates):
            hits.append(dataset)
    return hits


def valid_ohlc_frame(q: pd.DataFrame) -> pd.Series:
    o = q[["open", "high", "low", "close"]]
    return (
        o.notna().all(axis=1)
        & (o > 0).all(axis=1)
        & (q["high"] >= q[["open", "low", "close"]].max(axis=1))
        & (q["low"] <= q[["open", "high", "close"]].min(axis=1))
    )


def load_price(z: zipfile.ZipFile, base: str, sid: str) -> pd.DataFrame:
    n = f"{base}ohlcv/symbol={sid}.parquet"
    if n not in z.namelist():
        raise RuntimeError(f"missing selected-symbol OHLCV artifact: {n}")
    q = pd.read_parquet(io.BytesIO(z.read(n)))
    need = ["trade_date", "open", "high", "low", "close"]
    miss = [c for c in need if c not in q.columns]
    if miss:
        raise RuntimeError(f"OHLCV schema missing {miss} for {sid}")
    q = q[need].copy()
    q["trade_date"] = pd.to_datetime(q["trade_date"], errors="coerce").dt.date
    for c in ["open", "high", "low", "close"]:
        q[c] = pd.to_numeric(q[c], errors="coerce")
    q = q[q["trade_date"].notna()].sort_values("trade_date").reset_index(drop=True)
    return q


def quantile_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "p50": None,
            "p80": None,
            "p90": None,
            "p95": None,
            "iqr": None,
            "mean": None,
        }
    a = np.asarray(values, dtype=float)
    q25, q50, q75, q80, q90, q95 = np.quantile(
        a, [0.25, 0.50, 0.75, 0.80, 0.90, 0.95], method="linear"
    )
    return {
        "count": int(len(a)),
        "p50": float(q50),
        "p80": float(q80),
        "p90": float(q90),
        "p95": float(q95),
        "iqr": float(q75 - q25),
        "mean": float(np.mean(a)),
    }


def _safe_float(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _read_selected_cohort(client: Any, bucket: str, prefix: str, cohort_run_id: str) -> pd.DataFrame:
    obj = f"{prefix}/revisions/{cohort_run_id}/cohort/cohort_manifest.csv"
    raw = client.bucket(bucket).blob(obj).download_as_bytes()
    q = pd.read_csv(io.BytesIO(raw), dtype=str).fillna("")
    required = {"stock_id", "effective_start", "effective_end_exclusive", "coverage", "qualified", "selected"}
    miss = sorted(required - set(q.columns))
    if miss:
        raise RuntimeError(f"cohort manifest schema missing: {miss}")
    q = q[q["selected"].map(truthy)].copy()
    if len(q) != 500:
        raise RuntimeError(f"selected cohort must equal 500; got {len(q)}")
    if q["stock_id"].duplicated().any():
        raise RuntimeError("selected cohort has duplicate stock_id")
    if (pd.to_numeric(q["coverage"], errors="coerce") < 0.90).any():
        raise RuntimeError("selected cohort contains coverage below 0.90")
    return q.sort_values("stock_id").reset_index(drop=True)


def _obs_for_symbol(
    sid: str,
    lifecycle_start: date,
    lifecycle_end: date | None,
    q: pd.DataFrame,
    actions: dict[str, list[date]],
    weekly: list[date],
    calendar: list[date],
    research_end: date,
) -> tuple[list[dict[str, Any]], Counter, dict[int, Counter]]:
    rows: list[dict[str, Any]] = []
    exc = Counter()
    year_exc: dict[int, Counter] = defaultdict(Counter)

    dup_dates = set(q.loc[q.duplicated("trade_date", keep=False), "trade_date"].tolist())
    q_unique = q[~q["trade_date"].isin(dup_dates)].copy()
    q_unique["valid_ohlc"] = valid_ohlc_frame(q_unique)
    by_date = {r.trade_date: r for r in q_unique.itertuples(index=False)}
    dates = q_unique["trade_date"].tolist()
    date_pos = {dt: i for i, dt in enumerate(dates)}
    cal_pos = {dt: i for i, dt in enumerate(calendar)}

    eligible_t = [
        t for t in weekly
        if lifecycle_start <= t <= research_end and (lifecycle_end is None or t < lifecycle_end)
    ]

    for t in eligible_t:
        yr = t.year
        base: dict[str, Any] = {
            "stock_id": sid,
            "t": t.isoformat(),
            "year": yr,
            "par_value_coverage_unknown_pre2020": t < PAR_VALUE_KNOWN_START,
        }
        if t in dup_dates:
            t_status = "excluded_duplicate_t"
            t_row = None
        else:
            t_row = by_date.get(t)
            if t_row is None:
                t_status = "excluded_missing_t"
            elif _safe_float(t_row.close) is None or float(t_row.close) <= 0:
                t_status = "excluded_invalid_t_close"
            else:
                t_status = "ok"

        cp = cal_pos.get(t)
        e = calendar[cp + 1] if cp is not None and cp + 1 < len(calendar) else None
        if t_status != "ok":
            e_status = t_status
        elif e is None or e > research_end:
            e_status = "excluded_no_entry_calendar_date"
        elif lifecycle_end is not None and e >= lifecycle_end:
            e_status = "excluded_entry_outside_lifecycle"
        elif e in dup_dates:
            e_status = "excluded_duplicate_entry"
        else:
            e_row = by_date.get(e)
            if e_row is None:
                e_status = "excluded_missing_entry"
            elif _safe_float(e_row.open) is None or float(e_row.open) <= 0:
                e_status = "excluded_invalid_entry_open"
            else:
                e_status = "ok"

        base["entry_date"] = iso(e)
        base["entry_status"] = e_status
        entry_open = None
        if e_status == "ok":
            entry_open = float(by_date[e].open)
            base["entry_open"] = entry_open
        else:
            base["entry_open"] = None

        for h in HORIZONS:
            status = e_status
            mfe = mae = fwd = None
            peak_day = None
            h_end = None
            action_types = ""
            if status == "ok":
                p0 = date_pos.get(e)
                if p0 is None:
                    status = "excluded_missing_entry"
                else:
                    window = q_unique.iloc[p0:p0 + h].copy()
                    if lifecycle_end is not None:
                        window = window[window["trade_date"] < lifecycle_end]
                    if len(window) < h:
                        status = "excluded_incomplete_horizon"
                    elif not bool(window["valid_ohlc"].all()):
                        status = "excluded_invalid_ohlc_horizon"
                    else:
                        h_end = window.iloc[h - 1]["trade_date"]
                        hits = action_hits(actions, t, h_end)
                        if hits:
                            status = "excluded_corporate_action"
                            action_types = "|".join(sorted(hits))
                        else:
                            highs = window["high"].to_numpy(dtype=float)
                            lows = window["low"].to_numpy(dtype=float)
                            closes = window["close"].to_numpy(dtype=float)
                            peak_idx = int(np.argmax(highs))
                            mfe = float(highs[peak_idx] / entry_open - 1.0)
                            mae = float(np.min(lows) / entry_open - 1.0)
                            fwd = float(closes[-1] / entry_open - 1.0)
                            peak_day = peak_idx + 1
                            status = "valid"

            rec = dict(base)
            rec.update({
                "horizon": h,
                "status": status,
                "outcome_end_date": iso(h_end),
                "mfe": mfe,
                "mae": mae,
                "forward_return": fwd,
                "days_to_peak": peak_day,
                "corporate_action_types": action_types,
            })
            rows.append(rec)
            exc[(h, status)] += 1
            year_exc[yr][(h, status)] += 1
    return rows, exc, year_exc


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    source_obj = str(request.get("source_gcs_object", "")).strip()
    expected_sha = str(request.get("source_sha256", "")).strip().lower()
    expected_size = int(request.get("source_size_bytes", 0))
    materialized_revision = str(request.get("materialized_revision", "20260917T025906Z"))
    cohort_run_id = str(request.get("cohort_run_id", "")).strip()
    research_start = parse_date(request.get("research_start")) or date(2015, 1, 1)
    research_end = parse_date(request.get("research_end")) or date(2026, 9, 16)

    if not source_obj or len(expected_sha) != 64 or expected_size <= 0:
        raise RuntimeError("immutable source identity missing")
    if not cohort_run_id:
        raise RuntimeError("cohort_run_id missing")

    from google.cloud import storage
    client = storage.Client()
    buck = client.bucket(bucket)
    cohort = _read_selected_cohort(client, bucket, prefix, cohort_run_id)
    root = f"{prefix}/revisions/{run_id}"
    base = f"janus_step2a_materialized/{materialized_revision}/"

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        source_path = td_path / "source.zip"
        buck.blob(source_obj).download_to_filename(source_path)
        if source_path.stat().st_size != expected_size or file_sha(source_path) != expected_sha:
            raise RuntimeError("staged source identity mismatch")

        obs_path = td_path / "observations.parquet"
        symbol_summary_rows: list[dict[str, Any]] = []
        exclusions = Counter()
        year_exclusions: dict[int, Counter] = defaultdict(Counter)
        values: dict[int, list[float]] = {h: [] for h in HORIZONS}
        year_values: dict[tuple[int, int], list[float]] = defaultdict(list)
        total_potential: Counter = Counter()
        year_potential: Counter = Counter()
        pre2020_valid: Counter = Counter()
        writer = None

        with zipfile.ZipFile(source_path) as z:
            calendar, calendar_meta = cohort_build.calendar(z, base, research_start, research_end)
            weekly = weekly_first_trading_days(calendar)
            import pyarrow as pa
            import pyarrow.parquet as pq
            marketwide_par_value = load_marketwide_par_value_dates(z, base)

            for idx, r in cohort.iterrows():
                sid = str(r["stock_id"])
                s = parse_date(r["effective_start"])
                e = parse_date(r["effective_end_exclusive"])
                if s is None:
                    raise RuntimeError(f"selected symbol has no effective_start: {sid}")
                q = load_price(z, base, sid)
                actions = load_action_dates(z, base, sid, marketwide_par_value)
                obs, exc, yexc = _obs_for_symbol(sid, s, e, q, actions, weekly, calendar, research_end)
                odf = pd.DataFrame(obs)
                for c in ("year", "horizon", "days_to_peak"):
                    odf[c] = pd.to_numeric(odf[c], errors="coerce").astype("Int64")
                for c in ("entry_open", "mfe", "mae", "forward_return"):
                    odf[c] = pd.to_numeric(odf[c], errors="coerce").astype("Float64")
                odf["par_value_coverage_unknown_pre2020"] = odf["par_value_coverage_unknown_pre2020"].astype(bool)
                if writer is None:
                    table = pa.Table.from_pandas(odf, preserve_index=False)
                    writer = pq.ParquetWriter(obs_path, table.schema, compression="zstd")
                    writer.write_table(table)
                else:
                    writer.write_table(pa.Table.from_pandas(odf, schema=writer.schema, preserve_index=False))

                exclusions.update(exc)
                for yr, c in yexc.items():
                    year_exclusions[yr].update(c)
                valid20 = valid60 = 0
                for rec in obs:
                    h = int(rec["horizon"])
                    total_potential[h] += 1
                    year_potential[(int(rec["year"]), h)] += 1
                    if rec["status"] == "valid":
                        v = float(rec["mfe"])
                        values[h].append(v)
                        year_values[(int(rec["year"]), h)].append(v)
                        if rec["par_value_coverage_unknown_pre2020"]:
                            pre2020_valid[h] += 1
                        if h == 20:
                            valid20 += 1
                        elif h == 60:
                            valid60 += 1
                symbol_summary_rows.append({
                    "stock_id": sid,
                    "source_daily_coverage": float(r["coverage"]),
                    "potential_weekly_observations": len(obs) // len(HORIZONS),
                    "valid_mfe20": valid20,
                    "valid_mfe60": valid60,
                    "duplicate_price_dates": int(q.duplicated("trade_date", keep=False).sum()),
                })
                if (idx + 1) % 25 == 0:
                    print(f"[outcome {idx+1}/500] {sid} weekly={len(obs)//2}", flush=True)

        if writer is not None:
            writer.close()
        if not obs_path.exists():
            raise RuntimeError("no outcome observations produced")

        dist_rows: list[dict[str, Any]] = []
        for h in HORIZONS:
            st = quantile_stats(values[h])
            dist_rows.append({
                "scope": "pooled",
                "year": "",
                "horizon": h,
                "potential_count": int(total_potential[h]),
                "valid_count": st["count"],
                "valid_rate": (st["count"] / total_potential[h]) if total_potential[h] else None,
                **{k: st[k] for k in ("p50", "p80", "p90", "p95", "iqr", "mean")},
            })
        for (yr, h), pot in sorted(year_potential.items()):
            st = quantile_stats(year_values[(yr, h)])
            dist_rows.append({
                "scope": "year",
                "year": yr,
                "horizon": h,
                "potential_count": int(pot),
                "valid_count": st["count"],
                "valid_rate": (st["count"] / pot) if pot else None,
                **{k: st[k] for k in ("p50", "p80", "p90", "p95", "iqr", "mean")},
            })

        exc_rows: list[dict[str, Any]] = []
        for (h, status), count in sorted(exclusions.items()):
            exc_rows.append({"scope": "pooled", "year": "", "horizon": h, "status": status, "count": count})
        for yr, c in sorted(year_exclusions.items()):
            for (h, status), count in sorted(c.items()):
                exc_rows.append({"scope": "year", "year": yr, "horizon": h, "status": status, "count": count})

        source_cov = pd.to_numeric(cohort["coverage"], errors="coerce").to_numpy(dtype=float)
        coverage_stats = {
            "min": float(np.nanmin(source_cov)),
            "p50": float(np.nanquantile(source_cov, 0.50, method="linear")),
            "p90": float(np.nanquantile(source_cov, 0.90, method="linear")),
            "max": float(np.nanmax(source_cov)),
        }
        pooled = {str(r["horizon"]): r for r in dist_rows if r["scope"] == "pooled"}
        summary = {
            "schema_version": "janus.research.cloud-cohort-500.outcomes.v1",
            "status": "ok",
            "action": "preflight_and_outcomes",
            "run_id": run_id,
            "generated_at": now(),
            "research_period": {"start": iso(research_start), "end": iso(research_end)},
            "source": {
                "gcs_object": source_obj,
                "sha256": expected_sha,
                "size_bytes": expected_size,
                "materialized_revision": materialized_revision,
            },
            "cohort": {
                "cohort_run_id": cohort_run_id,
                "selected_symbols": int(len(cohort)),
                "source_daily_coverage_gate": 0.90,
                "source_daily_coverage_stats": coverage_stats,
            },
            "calendar": calendar_meta | {
                "weekly_snapshots": len(weekly),
                "first_weekly_t": iso(weekly[0] if weekly else None),
                "last_weekly_t": iso(weekly[-1] if weekly else None),
            },
            "outcomes": {
                "horizons": list(HORIZONS),
                "quantile_method": "numpy.linear",
                "pooled": pooled,
                "pre2020_par_value_coverage_unknown_valid_counts": {str(h): int(pre2020_valid[h]) for h in HORIZONS},
            },
            "dq": {
                "selected_symbol_count": 500,
                "cohort_coverage_gate_pass": bool(len(cohort) == 500 and np.nanmin(source_cov) >= 0.90),
                "exclusion_counts": {f"H{h}:{s}": int(c) for (h, s), c in sorted(exclusions.items())},
                "systemic_gap_decision": "NOT_EVALUATED",
                "note": "Year-level valid rates and exclusions are emitted for structural-gap review; no extra acceptance threshold is invented here.",
            },
            "isolation": {
                "postgresql_used": False,
                "database_used": False,
                "existing_janus_iceberg_catalog_used": False,
                "janus_core_written": False,
                "janus_mart_written": False,
                "janus_private_mart_written": False,
                "runtime_secret_used": False,
                "official_public_twse_http_used": False,
            },
            "next_gate": "sensitivity_and_research_report",
        }

        dist_fields = ["scope", "year", "horizon", "potential_count", "valid_count", "valid_rate", "p50", "p80", "p90", "p95", "iqr", "mean"]
        exc_fields = ["scope", "year", "horizon", "status", "count"]
        sym_fields = ["stock_id", "source_daily_coverage", "potential_weekly_observations", "valid_mfe20", "valid_mfe60", "duplicate_price_dates"]
        outputs = [
            (f"{root}/dq/preflight_summary.json", (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"), "application/json"),
            (f"{root}/dq/exclusions.csv", csv_bytes(exc_rows, exc_fields), "text/csv"),
            (f"{root}/dq/symbol_summary.csv", csv_bytes(symbol_summary_rows, sym_fields), "text/csv"),
            (f"{root}/outcomes/mfe_distribution.csv", csv_bytes(dist_rows, dist_fields), "text/csv"),
        ]
        for obj, body, ct in outputs:
            buck.blob(obj).upload_from_string(body, content_type=ct)
        buck.blob(f"{root}/outcomes/observations.parquet").upload_from_filename(obs_path, content_type="application/octet-stream")
        return summary


def self_test() -> None:
    cal = [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5)]
    assert weekly_first_trading_days(cal) == [date(2026, 9, 28), date(2026, 10, 5)]
    s = quantile_stats([0.0, 0.1, 0.2, 0.3, 0.4])
    assert abs(s["p50"] - 0.2) < 1e-12
    assert abs(s["p80"] - 0.32) < 1e-12
    q = pd.DataFrame({"open": [10.0], "high": [12.0], "low": [9.0], "close": [11.0]})
    assert bool(valid_ohlc_frame(q).iloc[0])
    assert action_hits({"x": [date(2026, 9, 30)]}, date(2026, 9, 29), date(2026, 10, 1)) == ["x"]
