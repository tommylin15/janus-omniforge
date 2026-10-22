"""Research versus Core-to-Mart Risk eight-factor test-vector parity.

These deterministic vectors exercise formulas, feature order, units, float32,
missing/preprocessing policy and deidentified target-only predictions.
Real GCS UBJ byte identity is a separate live readback gate.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.risk_shadow import predict_core_shadow, FEATURE_VERSION
from research.colab.risk_pilot import make_risk_panel
from research.colab.risk_v1 import add_v1_features, V1_FEATURES


def synthetic_eod():
    days = pd.bdate_range("2026-03-02", periods=98)
    out = []
    core = []
    for symbol, market, mult in (("2330", "twse", 1.), ("6488", "tpex", 1.3)):
        for idx, day in enumerate(days):
            close = float((85 + .12 * idx + .4 * np.sin(idx / 7)) * mult)
            open_ = close * (1 - .002 * np.sin(idx / 4))
            high = max(close, open_) * 1.014
            low = min(close, open_) * .985
            volume = 30_000 + 37 * idx
            turnover = volume * close
            d = day.date().isoformat()
            out.append({"symbol": symbol, "market": market, "trade_date": d,
                        "open": open_, "high": high, "low": low, "close": close,
                        "volume": volume, "turnover": turnover})
            core.append({"symbol": symbol, "market": market.upper(), "trade_date": d,
                         "open": open_, "high": high, "low": low, "close": close,
                         "volume_shares": volume, "turnover_twd": turnover,
                         "source_id": "licensed-dataset", "source_authorization": "approved",
                         "provenance_id": f"{market}-{idx}"})
    return out, core, {"twse": days, "tpex": days}, days[-1].date().isoformat()


def test_identical_eight_factor_vector_float32_and_prediction_parity():
    research_rows, core, sessions, as_of = synthetic_eod()
    raw = pd.DataFrame(research_rows)
    expected = add_v1_features(make_risk_panel(raw, market_sessions=sessions))
    latest = expected.loc[expected.trade_date.eq(pd.Timestamp(as_of))]
    assert tuple(V1_FEATURES) == (
        "vol20", "vol60", "drawdown60", "abs_return5", "volume_ratio20",
        "atr14_pct", "abs_overnight_gap5", "log_turnover20")
    x_research = latest[list(V1_FEATURES)].to_numpy(dtype=np.float32)
    assert np.isfinite(x_research).all()
    class Capture:
        matrix = None
        def predict(self, matrix):
            self.matrix = matrix.copy()
            return np.maximum(0, matrix[:, 0] + matrix[:, 5])
    model = Capture()
    report = predict_core_shadow(core, as_of, model,
                                 core_snapshot_id="pinned-canonical-core",
                                 target_symbols={"2330", "6488"})
    assert report["eligible_symbols"] == 2
    assert report["target_symbols_count"] == 2
    assert model.matrix.dtype == np.float32
    np.testing.assert_array_equal(model.matrix, x_research)
    np.testing.assert_allclose(
        [p["future_20d_volatility_annualized"] for p in report["predictions"]],
        np.maximum(0, x_research[:, 0] + x_research[:, 5]), rtol=0, atol=0)
    assert all(x["feature_version"] == FEATURE_VERSION and not x["publication_allowed"]
               for x in report["predictions"])


def test_future_bar_does_not_enter_cutoff_features():
    research_rows, core, sessions, as_of = synthetic_eod()
    day_after = (pd.Timestamp(as_of) + pd.Timedelta(days=1)).date().isoformat()
    future = dict(core[-1], trade_date=day_after, provenance_id="future")
    try:
        predict_core_shadow(core + [future], as_of, object(),
                            core_snapshot_id="pinned-canonical-core",
                            target_symbols={"2330"})
    except ValueError as exc:
        assert "future session" in str(exc)
    else:
        raise AssertionError("future Core EOD unexpectedly accepted")
