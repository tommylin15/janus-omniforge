"""Prospective Risk maturity is independent of historical OOS, with immutable receipts."""
from datetime import date, timedelta
import math
import pytest

from research.colab.risk_matured_outcomes import reconcile, write_once


def dates(n=23):
    start = date(2026, 1, 2)
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def fixture():
    ds = dates()
    shadow = {"status": "SHADOW_UNVALIDATED", "publication_allowed": False,
              "analysis_as_of": ds[0], "model_sha256": "a" * 64,
              "source_manifest_hash": "sha256:" + "b" * 64,
              "rows": [{"symbol": "2330", "market": "twse", "analysis_as_of": ds[0],
                        "future_20d_volatility_annualized": .3,
                        "recent_20d_volatility_annualized": .4}]}
    bars = [{"symbol": "2330", "market": "twse", "trade_date": d,
             "close": 100 * 1.01 ** i, "source_authorization": "approved"}
            for i, d in enumerate(ds)]
    return shadow, bars, {"twse": ds, "tpex": ds}


def test_pending_after_nineteen_market_sessions_is_not_evaluation_success():
    shadow, bars, sessions = fixture()
    result = reconcile(shadow, bars[:20], sessions, sessions["twse"][19])
    assert result["status_counts"] == {"MATURED": 0, "PENDING": 1, "EXCLUDED": 0}
    assert result["overall"]["mae"] is None
    assert result["outcomes"][0]["reason"] == "TWENTY_MARKET_SESSIONS_NOT_MATURE"


def test_exact_twenty_sessions_maturity_and_same_sample_rolling20():
    shadow, bars, sessions = fixture()
    result = reconcile(shadow, bars[:21], sessions, sessions["twse"][20])
    realized = math.sqrt(252) * math.log(1.01)
    assert result["status_counts"] == {"MATURED": 1, "PENDING": 0, "EXCLUDED": 0}
    assert result["overall"]["unique_signal_dates"] == 1
    assert result["overall"]["mae"] == pytest.approx(abs(.3 - realized))
    assert result["overall"]["rolling20_rmse"] == pytest.approx(abs(.4 - realized))
    assert result["by_market"]["tpex"]["matured_symbols"] == 0
    assert result["publication_allowed"] is False


def test_company_action_quarantines_window_not_rewrites_real_crash():
    shadow, bars, sessions = fixture()
    bars[10]["is_corporate_action"] = True
    result = reconcile(shadow, bars[:21], sessions, sessions["twse"][20])
    assert result["outcomes"][0]["status"] == "EXCLUDED"
    assert result["outcomes"][0]["reason"] == "COMPANY_ACTION_OR_DENIED_SOURCE"
    bars[10].pop("is_corporate_action")
    bars[10]["close"] *= .4
    result = reconcile(shadow, bars[:21], sessions, sessions["twse"][20])
    assert result["outcomes"][0]["status"] == "MATURED"
    assert result["outcomes"][0]["realized_20d_volatility_annualized"] > 1


def test_matured_missing_bars_are_pending_and_revision_ambiguity_is_rejected():
    shadow, bars, sessions = fixture()
    result = reconcile(shadow, bars[:10] + bars[11:21], sessions, sessions["twse"][20])
    assert result["outcomes"][0]["reason"] == "MATURED_SESSIONS_MISSING_SOURCE_BARS"
    with pytest.raises(ValueError, match="ambiguous"):
        reconcile(shadow, bars[:21] + [dict(bars[11])], sessions, sessions["twse"][20])


def test_immutable_output_cannot_be_overwritten(tmp_path):
    shadow, bars, sessions = fixture()
    result = reconcile(shadow, bars[:21], sessions, sessions["twse"][20])
    p = tmp_path / "maturity.json"
    write_once(result, p)
    previous = p.read_bytes()
    with pytest.raises(FileExistsError):
        write_once(result, p)
    assert p.read_bytes() == previous
