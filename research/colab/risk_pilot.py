"""D07-PRE Risk Analyst research-only pilot for manual Google Colab execution.

Consumes approved monthly Drive ZIPs (not Janus canonical data).  Predictions
remain research-only until source-use and independent OOS/promotion gates pass.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZON = 20
FEATURES = ("vol20", "vol60", "drawdown60", "abs_return5", "volume_ratio20")
REQUIRED = ("symbol", "market", "trade_date", "close", "volume")


def load_monthly_zips(paths: Iterable[str | Path]) -> tuple[pd.DataFrame, list[dict]]:
    """Load OHLCV only from hashed research monthly ZIPs; preserve provenance."""
    batches = []
    provenance = []
    for path in paths:
        path = Path(path)
        with ZipFile(path) as archive:
            names = archive.namelist()
            if len(set(names)) != len(names) or any(
                name.startswith("/") or ".." in name.split("/") for name in names
            ):
                raise ValueError("unsafe or duplicate ZIP member")
            required = {"manifest.json", "quality.json", "universe.csv", "ohlcv.csv"}
            if not required.issubset(names):
                raise ValueError("monthly ZIP lacks mandatory research files")
            manifest = json.loads(archive.read("manifest.json"))
            quality = json.loads(archive.read("quality.json"))
            month = manifest.get("month")
            if not isinstance(month, str) or not pd.Series([month]).str.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])").iloc[0]:
                raise ValueError("invalid research archive month")
            hashes = manifest.get("sha256", {})
            if not isinstance(hashes, dict):
                raise ValueError("manifest.sha256 is missing")
            for member in ("ohlcv.csv", "universe.csv", "quality.json"):
                expected = hashes.get(member)
                if not isinstance(expected, str) or not expected:
                    raise ValueError(f"missing SHA256 for {member}")
                actual = hashlib.sha256(archive.read(member)).hexdigest()
                if actual != expected:
                    raise ValueError(f"SHA256 mismatch: {member}")
            if quality.get("status") not in ("PASS", "PARTIAL", "PROBE"):
                raise ValueError("quality status missing or invalid")
            universe = pd.read_csv(io.BytesIO(archive.read("universe.csv")), dtype={"symbol": "string", "market": "string"})
            if any(c not in universe.columns for c in ("symbol", "market")) or universe.duplicated(["symbol"]).any():
                raise ValueError("universe missing symbols or contains duplicates")
            if not universe["market"].isin(["twse", "tpex"]).all() or not universe["symbol"].str.fullmatch(r"[1-9][0-9]{3}").all():
                raise ValueError("universe contains nonordinary stock candidates")
            data = pd.read_csv(io.BytesIO(archive.read("ohlcv.csv")), dtype={"symbol": "string", "market": "string"})
            if any(c not in data.columns for c in REQUIRED):
                raise ValueError("OHLCV required columns are missing")
            if not data.empty:
                verified = data.merge(universe[["symbol", "market"]], on=["symbol", "market"], how="left", indicator=True)
                if not (verified["_merge"] == "both").all():
                    raise ValueError("OHLCV market/symbol not in research universe")
                if not data["trade_date"].astype(str).str.startswith(month + "-").all():
                    raise ValueError("OHLCV date is outside source archive month")
            data["source_month"] = month
            data["source_archive_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            batches.append(data)
            provenance.append({"archive": str(path), "month": month, "sha256": data["source_archive_sha256"].iloc[0] if not data.empty else hashlib.sha256(path.read_bytes()).hexdigest(), "quality_status": quality["status"]})
    if not batches:
        raise ValueError("no monthly research archives")
    merged = pd.concat(batches, ignore_index=True)
    merged["trade_date"] = pd.to_datetime(merged["trade_date"], format="%Y-%m-%d", errors="raise")
    if merged.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("duplicate symbol/trade_date in research monthly files; revision selection required")
    if not merged["market"].isin(["twse", "tpex"]).all():
        raise ValueError("unknown market or non-common-share candidate")
    return merged, provenance


def make_risk_panel(prices: pd.DataFrame, horizon: int = HORIZON,
                    *, market_sessions: dict | None = None) -> pd.DataFrame:
    """Risk X/Y on full market-session grids; never bridge a stock's missing day.

    Explicit sessions come from the hashed monthly research manifests.  If
    absent (legacy fixture callers), infer each market's dates from all its
    observed stocks.  Neither path forward-fills prices, volumes, or labels.
    """
    if horizon < 2:
        raise ValueError("horizon must be at least 2")
    if any(col not in prices for col in REQUIRED):
        raise ValueError("missing required OHLCV columns")
    if not prices["market"].isin(["twse", "tpex"]).all():
        raise ValueError("only verified TWSE/TPEx ordinary-stock universe allowed")
    work = prices.copy()
    work["trade_date"] = pd.to_datetime(work["trade_date"])
    work["close"] = pd.to_numeric(work["close"], errors="raise")
    work["volume"] = pd.to_numeric(work["volume"], errors="raise")
    if (~np.isfinite(work["close"]) | (work["close"] <= 0)).any():
        raise ValueError("invalid close price; do not fabricate missing values")
    if (~np.isfinite(work["volume"]) | (work["volume"] < 0)).any():
        raise ValueError("invalid volume")
    if work.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("duplicate research bars")
    work = work.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    grids = {}
    for market in work["market"].unique():
        observed = pd.DatetimeIndex(work.loc[work["market"] == market, "trade_date"].unique()).sort_values()
        if market_sessions is None:
            grid = observed
        else:
            if market not in market_sessions:
                raise ValueError(f"{market} official market sessions missing")
            grid = pd.DatetimeIndex(pd.to_datetime(market_sessions[market]))
            if not grid.is_monotonic_increasing or grid.has_duplicates or len(grid) == 0:
                raise ValueError(f"{market} market sessions not ordered or unique")
            if len(observed.difference(grid)):
                raise ValueError(f"{market} price outside evidenced trading sessions")
        grids[market] = grid

    output = []
    for (symbol, market), g in work.groupby(["symbol", "market"], sort=False):
        g = g.set_index("trade_date").reindex(grids[market]).rename_axis("trade_date").reset_index()
        g["symbol"] = symbol
        g["market"] = market
        ret = np.log(g["close"] / g["close"].shift(1))
        g["vol20"] = ret.pow(2).rolling(20, min_periods=20).mean().pow(.5) * math.sqrt(252)
        g["vol60"] = ret.pow(2).rolling(60, min_periods=60).mean().pow(.5) * math.sqrt(252)
        g["drawdown60"] = g["close"] / g["close"].rolling(60, min_periods=60).max() - 1.0
        g["abs_return5"] = (g["close"] / g["close"].shift(5) - 1.0).abs()
        g["volume_ratio20"] = g["volume"] / g["volume"].shift(1).rolling(20, min_periods=20).mean().replace(0, np.nan)
        # At t, label returns are t+1 ... t+H; missing sessions imply NaN.
        g["target_fwd_vol20"] = (ret.shift(-1).pow(2).rolling(horizon, min_periods=horizon).mean().shift(-(horizon - 1))).pow(.5) * math.sqrt(252)
        g["label_matures_on"] = g["trade_date"].shift(-horizon)
        # Screening is a research-only sensitivity, NOT proof of a split.
        shock = (ret.abs() > math.log(1.35)).astype(float)
        g["unverified_shock_feature"] = shock.rolling(60, min_periods=60).max()
        g["unverified_shock_label"] = shock.shift(-1).rolling(horizon, min_periods=horizon).max().shift(-(horizon - 1))
        output.append(g)
    return pd.concat(output, ignore_index=True)


def evaluate_risk_pilot(panel: pd.DataFrame, cutoff: str | pd.Timestamp,
                        *, min_train: int = 100, min_test: int = 20,
                        exclude_unverified_shocks: bool = False,
                        oos_end: str | pd.Timestamp | None = None) -> dict:
    """Predeclared time-cut Ridge vs rolling20; all train labels mature by cutoff.

    Single fixed-cutoff research OOS, not multi-fold walk-forward or a
    production promotion gate.  Market/date cohorts remain together.
    """
    cutoff = pd.Timestamp(cutoff)
    as_of = panel["trade_date"].max()
    eligible = panel.dropna(subset=[*FEATURES, "target_fwd_vol20", "label_matures_on"]).copy()
    eligible = eligible.loc[eligible["label_matures_on"] <= as_of]
    if exclude_unverified_shocks:
        required = ("unverified_shock_feature", "unverified_shock_label")
        if any(col not in eligible for col in required):
            raise ValueError("corporate action sensitivity flags missing")
        eligible = eligible.loc[(eligible[required[0]] == 0) & (eligible[required[1]] == 0)]
    train = eligible[(eligible["trade_date"] <= cutoff) & (eligible["label_matures_on"] <= cutoff)]
    test = eligible[(eligible["trade_date"] > cutoff) & (eligible["label_matures_on"] <= as_of)]
    if oos_end is not None:
        test = test.loc[test["trade_date"] <= pd.Timestamp(oos_end)]
    if len(train) < min_train or len(test) < min_test:
        raise ValueError(f"insufficient matured samples: train={len(train)}, test={len(test)}")
    estimator = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    estimator.fit(train[list(FEATURES)], train["target_fwd_vol20"])
    actual = test["target_fwd_vol20"].to_numpy()
    baseline = test["vol20"].to_numpy()
    challenger = np.clip(estimator.predict(test[list(FEATURES)]), 0, None)

    def score(y, base, candidate):
        return {
            "rolling20_baseline": {"mae": float(np.mean(np.abs(y - base))),
                                   "rmse": float(np.sqrt(np.mean((y - base)**2)))},
            "ridge_challenger": {"mae": float(np.mean(np.abs(y - candidate))),
                                 "rmse": float(np.sqrt(np.mean((y - candidate)**2)))},
        }
    metrics = score(actual, baseline, challenger)
    sampled = test[["trade_date", "market", "symbol", "target_fwd_vol20"]].copy()
    sampled["baseline"] = baseline
    sampled["challenger"] = challenger
    by_market = {}
    by_month = {}
    for market, group in sampled.groupby("market"):
        by_market[market] = {"rows": int(len(group)), "unique_dates": int(group["trade_date"].nunique()),
                             "metrics": score(group["target_fwd_vol20"].to_numpy(),
                                              group["baseline"].to_numpy(), group["challenger"].to_numpy())}
    for month, group in sampled.groupby(sampled["trade_date"].dt.to_period("M")):
        by_month[str(month)] = {"rows": int(len(group)), "unique_dates": int(group["trade_date"].nunique()),
                                "metrics": score(group["target_fwd_vol20"].to_numpy(),
                                                 group["baseline"].to_numpy(), group["challenger"].to_numpy())}
    return {
        "model": "risk-forward-20d-realized-volatility-ridge-v0",
        "status": "RESEARCH_OOS_ONLY_NOT_PROMOTABLE",
        "source_license_status": "REQUIRES_OPERATOR_VERIFICATION",
        "corporate_action_adjustment": "UNVERIFIED",
        "historical_pit": "NOT_VERIFIED",
        "cutoff": cutoff.date().isoformat(),
        "oos_end": (pd.Timestamp(oos_end).date().isoformat() if oos_end is not None else None),
        "as_of": as_of.date().isoformat(),
        "train_rows": len(train),
        "oos_rows": len(test),
        "train_unique_dates": int(train["trade_date"].nunique()),
        "oos_unique_dates": int(test["trade_date"].nunique()),
        "train_latest_label_maturity": train["label_matures_on"].max().date().isoformat(),
        "oos_latest_label_maturity": test["label_matures_on"].max().date().isoformat(),
        "oos_symbols": int(test["symbol"].nunique()),
        "metrics": metrics,
        "oos_by_market": by_market,
        "oos_by_month": by_month,
        "sensitivity_exclude_unverified_gt35pct_shocks": exclude_unverified_shocks,
        "candidate_beats_baseline_mae": bool(metrics["ridge_challenger"]["mae"] < metrics["rolling20_baseline"]["mae"]),
        "publication_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual Colab Risk pilot; does not publish Janus models")
    parser.add_argument("zips", nargs="+", help="Drive research YYYY-MM.zip paths downloaded/mounted by operator")
    parser.add_argument("--cutoff", required=True, help="YYYY-MM-DD, earliest OOS trading day is after cutoff")
    parser.add_argument("--result", default="risk_pilot_oos.json")
    args = parser.parse_args()
    prices, source = load_monthly_zips(args.zips)
    panel = make_risk_panel(prices)
    report = evaluate_risk_pilot(panel, args.cutoff)
    report["sources"] = source
    Path(args.result).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "oos_rows": report["oos_rows"], "candidate_beats_baseline_mae": report["candidate_beats_baseline_mae"]}))


if __name__ == "__main__":
    main()
