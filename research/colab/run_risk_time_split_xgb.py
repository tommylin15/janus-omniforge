"""Research-only fixed-window Risk: rolling20 vs Ridge5/Ridge8/XGBoost8.

Train: signal >= 2025-07-01, label matured <= 2026-06-30.
OOS: signal 2026-07..09, with mature 20-market-session label <= 2026-09-30.
This is a retrospective diagnostic, NOT untouched holdout/Colab acceptance/promotion.
No external service, no GCS, no owner holdings, no model auto-publication.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    from .monthly_folder_io import load_monthly_folders
    from .risk_pilot import make_risk_panel
    from .risk_v1 import add_v1_features, V0_FEATURES, V1_FEATURES
except ImportError:
    from monthly_folder_io import load_monthly_folders
    from risk_pilot import make_risk_panel
    from risk_v1 import add_v1_features, V0_FEATURES, V1_FEATURES

TRAIN_START = "2025-07-01"
TRAIN_MATURITY_CUTOFF = "2026-06-30"
TEST_START = "2026-07-01"
TEST_END = "2026-09-30"
XGB_PARAMS = {
    "n_estimators": 240, "max_depth": 3, "learning_rate": 0.05,
    "subsample": 0.8, "colsample_bytree": 1.0, "reg_lambda": 10.0,
    "min_child_weight": 25, "objective": "reg:squarederror",
    "tree_method": "hist", "n_jobs": 4, "random_state": 20261022,
}


def fixed_split(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use only signal-available X and pre-cutoff matured Y.

    Never inspect future label shock flags to choose eligible examples;
    such ex-post censorship would overstate prospective model quality.
    """
    required = [*V1_FEATURES, "target_fwd_vol20", "label_matures_on",
                "unverified_shock_feature", "trade_date", "market", "symbol"]
    for column in required:
        if column not in panel:
            raise ValueError(f"required column missing: {column}")
    eligible = panel.dropna(subset=[*V1_FEATURES, "target_fwd_vol20",
                                    "label_matures_on"]).copy()
    eligible = eligible.loc[eligible["unverified_shock_feature"].eq(0)]
    train = eligible.loc[
        eligible["trade_date"].ge(pd.Timestamp(TRAIN_START))
        & eligible["trade_date"].le(pd.Timestamp(TRAIN_MATURITY_CUTOFF))
        & eligible["label_matures_on"].le(pd.Timestamp(TRAIN_MATURITY_CUTOFF))
    ]
    test = eligible.loc[
        eligible["trade_date"].ge(pd.Timestamp(TEST_START))
        & eligible["trade_date"].le(pd.Timestamp(TEST_END))
        & eligible["label_matures_on"].le(pd.Timestamp(TEST_END))
    ]
    if (len(train) < 20000 or len(test) < 10000
            or train["trade_date"].nunique() < 120
            or test["trade_date"].nunique() < 20):
        raise ValueError(f"insufficient real matured cohort train={len(train)}, test={len(test)}")
    if (train["label_matures_on"].max() > pd.Timestamp(TRAIN_MATURITY_CUTOFF)
            or test["label_matures_on"].max() > pd.Timestamp(TEST_END)):
        raise ValueError("future label leaked across time boundary")
    return train, test


def run_four_models(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """Fit only train, no tuning/early stopping on OOS test."""
    try:
        from xgboost import XGBRegressor
    except ImportError as exc:
        raise RuntimeError("Research-only extra required: pip install xgboost") from exc

    y_train = train["target_fwd_vol20"].to_numpy(dtype=float)
    target = test["target_fwd_vol20"].to_numpy(dtype=float)
    predictions = {"Rolling Vol20": test["vol20"].to_numpy(dtype=float)}
    for name, columns in (("Ridge v0", V0_FEATURES), ("Ridge v1", V1_FEATURES)):
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        model.fit(train[list(columns)], y_train)
        predictions[name] = np.maximum(0, model.predict(test[list(columns)]))
    booster = XGBRegressor(**XGB_PARAMS)
    booster.fit(train[list(V1_FEATURES)].to_numpy(dtype=np.float32),
                y_train.astype(np.float32))
    predictions["XGBoost v1"] = np.maximum(
        0, booster.predict(test[list(V1_FEATURES)].to_numpy(dtype=np.float32))
    ).astype(float)

    def metrics(mask):
        actual = target[mask]
        return {name: {"mae": float(np.mean(np.abs(actual - values[mask]))),
                       "rmse": float(np.sqrt(np.mean(np.square(actual - values[mask]))))}
                for name, values in predictions.items()}

    months = test["trade_date"].dt.to_period("M").astype(str)
    by_month = {month: {"rows": int(months.eq(month).sum()),
                        "signal_dates": int(test.loc[months.eq(month), "trade_date"].nunique()),
                        "metrics": metrics(months.eq(month).to_numpy())}
                for month in sorted(months.unique())}
    by_market = {market: {"rows": int(test["market"].eq(market).sum()),
                          "metrics": metrics(test["market"].eq(market).to_numpy())}
                 for market in sorted(test["market"].unique())}

    # Calendar-session bootstrap: correlated stocks on the same day stay together.
    grouped = test.reset_index(drop=True).groupby("trade_date", sort=True).indices
    day_losses = []
    for idx in grouped.values():
        actual = target[idx]
        losses = {name: np.abs(actual - values[idx]).sum() for name, values in predictions.items()}
        day_losses.append((len(idx), losses))
    rng = np.random.default_rng(20261022)
    d = len(day_losses)
    block_len = 20
    blocks = int(math.ceil(d / block_len))
    intervals = {}
    if d >= 40:
        gains = {name: [] for name in predictions if name != "Rolling Vol20"}
        for _ in range(2000):
            ids = np.concatenate([((np.arange(block_len) + rng.integers(d)) % d)
                                  for _ in range(blocks)])[:d]
            denom = sum(day_losses[i][0] for i in ids)
            base = sum(day_losses[i][1]["Rolling Vol20"] for i in ids) / denom
            for name in gains:
                challenger = sum(day_losses[i][1][name] for i in ids) / denom
                gains[name].append((base - challenger) / base)
        intervals = {name: {"mae_gain_95pct_interval": np.quantile(gains[name], [.025, .975]).tolist(),
                            "pct_replicates_positive": float(np.mean(np.array(gains[name]) > 0))}
                     for name in gains}
    return {"metrics": metrics(slice(None)), "by_market": by_market,
            "by_month": by_month, "market_date_block_bootstrap": intervals}


def main() -> None:
    cli = argparse.ArgumentParser(description="Fixed user-requested retrospective Risk 4-way OOS")
    cli.add_argument("monthly_folders", nargs="+")
    cli.add_argument("--output", default="risk-2025h2-2026q3.json")
    args = cli.parse_args()
    prices, sources = load_monthly_folders(args.monthly_folders)
    sessions = {market: sorted({date for source in sources
                                for date in source["market_sessions"][market]})
                for market in ("twse", "tpex")}
    panel = add_v1_features(make_risk_panel(prices, market_sessions=sessions))
    train, test = fixed_split(panel)
    result = run_four_models(train, test)
    result.update({
        "status": "RESEARCH_RETROSPECTIVE_NOT_INDEPENDENT_HOLDOUT",
        "publication_allowed": False,
        "source_bar_rows": int(len(prices)),
        "train": {"from": TRAIN_START, "label_maturity_cutoff": TRAIN_MATURITY_CUTOFF,
                  "rows": int(len(train)), "signal_dates": int(train["trade_date"].nunique()),
                  "last_signal": train["trade_date"].max().strftime("%Y-%m-%d")},
        "test": {"from": TEST_START, "through": TEST_END,
                 "rows": int(len(test)), "signal_dates": int(test["trade_date"].nunique()),
                 "last_matured_signal": test["trade_date"].max().strftime("%Y-%m-%d"),
                 "last_label_maturity": test["label_matures_on"].max().strftime("%Y-%m-%d")},
        "market_sessions": {m: len(days) for m, days in sessions.items()},
        "xgboost_fixed_params": XGB_PARAMS,
        "features_v0": list(V0_FEATURES), "features_v1": list(V1_FEATURES),
        "filter": "only past 60-session extreme-return shock known at signal; never future-label shock",
        "known_limitations": [
            "2026-07 and 2026-08 outcomes previously reviewed: not an untouched test",
            "2026-09 signals mostly not yet matured by archive ending 2026-09-30",
            "Current ordinary-stock master only; no historic delisting PIT",
            "Prices unadjusted for documented corporate actions",
            "Overlapping 20-session labels; no independent stock-row inference",
            "No model publication or live Colab execution receipt",
        ],
        "sources": sources,
    })
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(path), "rows": result["test"]["rows"],
                      "mae": {name: item["mae"] for name,item in result["metrics"].items()},
                      "publication_allowed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
