"""Time-purged Risk 2025/07..2026/06 / 2026/07..09 research comparison."""
import numpy as np
import pandas as pd
import pytest

from research.colab.run_risk_time_split_xgb import fixed_split, run_four_models
from research.colab.risk_v1 import V1_FEATURES


def fixture_panel(stocks=110):
    dates = pd.bdate_range("2025-01-01", "2026-09-30")
    base = np.arange(len(dates), dtype=float)
    rows = []
    for stock in range(stocks):
        market = "twse" if stock % 2 == 0 else "tpex"
        symbol = f"{1000 + stock:04d}"
        frame = pd.DataFrame({"symbol": symbol, "market": market,
                              "trade_date": dates,
                              "target_fwd_vol20": 0.20 + .02*np.sin(base/13 + stock),
                              "label_matures_on": pd.Series(dates).shift(-20),
                              "unverified_shock_feature": 0.,
                              "unverified_shock_label": 0.})
        for offset, col in enumerate(V1_FEATURES):
            frame[col] = 0.15 + .03 * np.sin(base/(8 + offset) + stock/10)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def test_maturity_purge_and_calendar_cutoffs():
    train, test = fixed_split(fixture_panel())
    assert len(train) >= 20000
    assert len(test) >= 10000
    assert train.trade_date.min() >= pd.Timestamp("2025-07-01")
    assert train.label_matures_on.max() <= pd.Timestamp("2026-06-30")
    assert test.trade_date.min() >= pd.Timestamp("2026-07-01")
    assert test.label_matures_on.max() <= pd.Timestamp("2026-09-30")
    assert test.trade_date.max() < pd.Timestamp("2026-09-30")


def test_cannot_filter_using_future_outcome_shock():
    panel = fixture_panel()
    a, b = fixed_split(panel)
    changed = panel.copy()
    changed["unverified_shock_label"] = 1.
    c, d = fixed_split(changed)
    assert len(a) == len(c)
    assert len(b) == len(d)
    assert b[["symbol", "trade_date"]].equals(d[["symbol", "trade_date"]])


def test_future_signal_feature_shocks_are_excluded_as_of_signal():
    panel = fixture_panel()
    mask = panel.trade_date.eq(pd.Timestamp("2026-07-01"))
    panel.loc[mask, "unverified_shock_feature"] = 1.
    _, test = fixed_split(panel)
    assert not test.trade_date.eq(pd.Timestamp("2026-07-01")).any()


def test_xgboost_uses_identical_cohorts_and_never_publishes():
    pytest.importorskip("xgboost")
    train, test = fixed_split(fixture_panel())
    out = run_four_models(train, test)
    assert set(out["metrics"]) == {"Rolling Vol20", "Ridge v0", "Ridge v1", "XGBoost v1"}
    assert all(out["by_market"][m]["rows"] > 0 for m in ("twse", "tpex"))
    assert all(m["mae"] >= 0 for m in out["metrics"].values())
    assert "2026-07" in out["by_month"]
    assert out["market_date_block_bootstrap"]
