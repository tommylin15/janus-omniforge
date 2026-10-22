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
    # Exact copies can be deterministically collapsed without altering
    # model features; an affected stock with conflicting revisions must be
    # quarantined while the unrelated stock continues shadow inference.
    identical = predict_core_shadow([*rows, dict(rows[-1])], as_of, Model(), core_snapshot_id="core-fixed")
    assert {x["symbol"] for x in identical["predictions"]} == {"2330", "6488"}
    assert identical["identical_core_duplicates_collapsed"] == 1
    assert identical["ambiguous_core_symbols"] == 0
    dispute = dict(rows[-1], close=rows[-1]["close"] + 2)
    conflicting = predict_core_shadow([*rows, dispute], as_of, Model(), core_snapshot_id="core-fixed")
    assert {x["symbol"] for x in conflicting["predictions"]} == {"2330"}
    assert conflicting["ambiguous_core_symbols"] == 1
    assert conflicting["publication_allowed"] is False
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


def test_core_mixed_sources_contradictory_historical_revision_quarantines_stock():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    older = next(r for r in rows if r["symbol"] == "2330" and r["trade_date"] < as_of)
    contradictory = dict(older, provenance_id="revised", volume_shares=older["volume_shares"]+500)
    result = predict_core_shadow([*rows, contradictory], as_of, Model(),
                                 core_snapshot_id="core-fixed")
    assert {item["symbol"] for item in result["predictions"]} == {"6488"}
    assert result["ambiguous_core_symbols"] == 1
    assert result["publication_allowed"] is False


def test_duplicate_with_different_source_but_same_prices_is_safe_only_in_shadow():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    alternate = dict(rows[-1], source_id="alternate-approved", provenance_id="different")
    result = predict_core_shadow([*rows, alternate], as_of, Model(),
                                 core_snapshot_id="core-fixed")
    assert result["status"] == "SHADOW_ONLY"
    assert result["identical_core_duplicates_collapsed"] == 1
    assert len(result["predictions"]) == 2
    assert all(p["publication_allowed"] is False for p in result["predictions"])

def test_historical_market_conflict_quarantines_only_affected_symbol():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    # Core may contain a historical TWSE/TPEx discrepancy for one stock.
    # Such a symbol must not be reclassified by guessing, and must not stop
    # unrelated stocks from receiving safe shadow-only predictions.
    revised = [
        dict(r, market="TPEx") if r["symbol"] == "2330" and r["trade_date"] < as_of else r
        for r in rows
    ]
    out = predict_core_shadow(revised, as_of, Model(), core_snapshot_id="core-fixed")
    assert out["status"] == "SHADOW_ONLY"
    assert out["publication_allowed"] is False
    assert out["ambiguous_core_symbols"] == 1
    assert {r["symbol"] for r in out["predictions"]} == {"6488"}
    assert all(r["quality"] == "SHADOW_UNVALIDATED" for r in out["predictions"])


def test_same_day_cross_market_revision_quarantines_only_affected_symbol():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    revised = dict(next(r for r in rows if r["symbol"] == "2330"),
                   market="tpex", source_id="tpex", provenance_id="revision")
    out = predict_core_shadow([*rows, revised], as_of, Model(),
                              core_snapshot_id="core-fixed")
    assert out["ambiguous_core_symbols"] == 1
    assert {r["symbol"] for r in out["predictions"]} == {"6488"}
    assert out["publication_allowed"] is False

def test_future_published_revision_is_rejected_without_using_fetched_at_as_pit():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    future = dict(rows[-1], published_at="2026-12-01T15:00:00+08:00")
    with pytest.raises(ValueError, match="future-available source revision"):
        predict_core_shadow([*rows[:-1], future], as_of, Model(), core_snapshot_id="core-fixed")
    malformed = dict(rows[-1], availability_at="not-a-time")
    with pytest.raises(ValueError, match="invalid publication metadata"):
        predict_core_shadow([*rows[:-1], malformed], as_of, Model(), core_snapshot_id="core-fixed")
    fetched_later = [dict(x, fetched_at="2026-10-22T12:00:00+08:00") for x in rows]
    result = predict_core_shadow(fetched_later, as_of, Model(), core_snapshot_id="core-fixed")
    assert result["eligible_symbols"] == 2
    assert result["excluded_target_symbols_count"] == 0


def test_excluded_targets_get_aggregate_reasons_not_private_membership():
    rows = bars()
    as_of = max(r["trade_date"] for r in rows)
    out = predict_core_shadow(rows, as_of, Model(), core_snapshot_id="core-fixed",
                              target_symbols={"2330", "6488", "9999"})
    assert out["target_symbols_count"] == 3
    assert out["eligible_symbols"] == 2
    assert out["excluded_target_symbols_count"] == 1
    assert out["excluded_target_reasons"]["NO_ACCEPTED_CORE_HISTORY_OR_ACTION_OR_SOURCE"] == 1
    assert "held" not in str(out) and "watchlisted" not in str(out)
