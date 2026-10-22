"""No publication or future leak from Core-to-XGBoost shadow lane."""
from datetime import date, timedelta
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.risk_shadow import (MODEL_SHA256, MODEL_NAME, load_model_from_pinned_store,
                                          predict_core_shadow)


def bars():
    result = []
    start = date(2026, 2, 1)
    for market, symbol in (("TWSE", "2330"), ("TPEX", "6488")):
        for i in range(137):
            day = start + timedelta(days=i)
            if day.weekday() >= 5:
                continue
            close = 100. + i * .13 + (i % 7) * .04
            result.append({
                "symbol": symbol, "market": market,
                "trade_date": day.isoformat(), "open": close * .999,
                "high": close * 1.015, "low": close * .985, "close": close,
                "volume_shares": 1000 + i, "turnover_twd": (1000 + i) * close,
                "source_id": market.lower(), "provenance_id": f"{symbol}-{i}",
                "quality_flag": "pass", "source_authorization": "approved",
            })
    return result


class Model:
    def predict(self, matrix):
        assert matrix.shape[1] == 8 and matrix.dtype == np.float32
        return np.repeat(.37, len(matrix))


def test_shadow_inference_publishes_no_canonical_or_user_prediction():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    result = predict_core_shadow(rows, as_of, Model(), core_snapshot_id="core-fixed")
    assert result["status"] == "SHADOW_ONLY"
    assert result["publication_allowed"] is False
    assert {r["symbol"] for r in result["predictions"]} == {"2330", "6488"}
    assert all(p["publication_allowed"] is False and p["quality"] == "SHADOW_UNVALIDATED"
               and p["model_sha256"] == MODEL_SHA256 for p in result["predictions"])
    assert all(p["future_20d_volatility_annualized"] == .37 for p in result["predictions"])


def test_core_source_refuses_future_critical_or_duplicate_rows():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    broken = dict(rows[-1], trade_date="2026-12-31")
    with pytest.raises(ValueError, match="future session"):
        predict_core_shadow([*rows, broken], as_of, Model(), core_snapshot_id="core-fixed")
    with pytest.raises(ValueError, match="duplicate admitted"):
        predict_core_shadow([*rows, dict(rows[-1])], as_of, Model(), core_snapshot_id="core-fixed")
    blocked = [dict(r, quality_flag="critical") if r["symbol"] == "6488" else r for r in rows]
    result = predict_core_shadow(blocked, as_of, Model(), core_snapshot_id="core-fixed")
    assert not any(p["symbol"] == "6488" for p in result["predictions"])


def test_missing_bar_breaks_features_no_fill():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    # A single missing 2330 observation inside the recent 60-session feature
    # window must cause no eligible candidate for that symbol.
    stock = [r for r in rows if r["symbol"] == "2330"]
    removed = stock[-15]["trade_date"]
    data = [r for r in rows if not (r["symbol"] == "2330" and r["trade_date"] == removed)]
    out = predict_core_shadow(data, as_of, Model(), core_snapshot_id="core-fixed")
    assert not any(p["symbol"] == "2330" for p in out["predictions"])
    assert any(p["symbol"] == "6488" for p in out["predictions"])


def test_gcs_model_pin_blocks_tampering_before_deserialization():
    class Store:
        def read(self, path):
            assert path == MODEL_NAME
            return b"forged-xgb"
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_model_from_pinned_store(Store())
