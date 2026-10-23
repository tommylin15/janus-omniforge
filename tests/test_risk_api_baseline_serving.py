"""Risk API: latest deterministic row must not hide a valid ACTIVE forecast."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from packages.analysis_product import content_hash
from services.api.analysis import AnalysisService


MODEL_SHA = "36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044"
ROLES = ("fundamental", "valuation", "quant", "risk", "event")


def today():
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def product(as_of, *, candidate=False, symbol="2327"):
    value = {
        "symbol": symbol, "analysis_as_of": str(as_of),
        "core_snapshot_id": "core-" + str(as_of),
        "specialists": [
            {"role": role, "analysis_as_of": str(as_of),
             "core_snapshot_id": "core-" + str(as_of),
             "model_status": "deterministic-unpromoted-v1",
             "baseline_status": "available",
             "metrics": {"recent_20d_volatility_annualized": .20} if role == "risk"
                        else {"unchanged": role}}
            for role in ROLES],
        "model_quality": "NOT_VERIFIED",
    }
    if candidate:
        value["risk_first_release_candidate"] = {
            "symbol": symbol, "analysis_as_of": str(as_of),
            "core_snapshot_id": value["core_snapshot_id"],
            "model_sha256": MODEL_SHA,
            "future_20d_volatility_annualized": .32,
            "recent_20d_volatility_annualized": .20,
        }
    value["content_hash"] = content_hash(value)
    return value


class Cursor:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value


class FakeRepository:
    def __init__(self, latest, prior=None, *, mode="ACTIVE"):
        self.latest, self.prior, self.mode = latest, prior, mode
        self.calls = []

    @contextmanager
    def _connection(self):
        yield self

    def execute(self, sql, params):
        self.calls.append((sql, params))
        if "FROM private.specialist_product" in sql:
            if "payload_json ?" in sql:
                assert params == (self.latest["symbol"], self.latest["analysis_as_of"])
                return Cursor({"payload_json": self.prior} if self.prior else None)
            assert params[0] == self.latest["symbol"]
            return Cursor({"payload_json": self.latest})
        if "FROM private.risk_model_activation" in sql:
            return Cursor({"mode": self.mode, "model_sha256": MODEL_SHA})
        if "FROM private.market_screening_product" in sql:
            return Cursor(None)
        raise AssertionError(sql)


def risk(value):
    return next(s for s in value["specialists"] if s["role"] == "risk")


def test_recent_older_risk_is_visible_without_downgrading_newer_baseline():
    prior = product(today() - timedelta(days=2), candidate=True)
    latest = product(today() - timedelta(days=1))
    repo = FakeRepository(latest, prior)
    served = AnalysisService(repo).baseline("2327")
    assert served["analysis_as_of"] == latest["analysis_as_of"]
    assert served["core_snapshot_id"] == latest["core_snapshot_id"]
    assert served["risk_serving_as_of"] == prior["analysis_as_of"]
    assert served["risk_serving_core_snapshot_id"] == prior["core_snapshot_id"]
    assert served["risk_serving_source_hash"] != latest["content_hash"]
    assert served["risk_serving_status"] == "FIRST_RELEASE_APPROVED"
    assert risk(served)["analysis_as_of"] == prior["analysis_as_of"]
    assert risk(served)["core_snapshot_id"] == prior["core_snapshot_id"]
    assert risk(served)["model_status"] == "first_release_approved"
    assert risk(served)["metrics"]["future_20d_volatility_annualized"] == .32
    assert served["specialists"][2] == latest["specialists"][2]
    assert latest["content_hash"] == content_hash({k: v for k, v in latest.items()
                                                   if k != "content_hash"})
    assert served["source_projection_hash"] == latest["content_hash"]
    assert served["content_hash"] == content_hash({k: v for k, v in served.items()
                                                   if k != "content_hash"})
    assert any("payload_json ?" in sql for sql, _ in repo.calls)


def test_rollback_immediately_hides_historical_model_numbers():
    repo = FakeRepository(product(today(), candidate=False),
                          product(today() - timedelta(days=1), candidate=True),
                          mode="DETERMINISTIC")
    served = AnalysisService(repo).baseline("2327")
    assert risk(served)["model_status"] == "deterministic-unpromoted-v1"
    assert "future_20d_volatility_annualized" not in risk(served)["metrics"]
    assert "risk_serving_status" not in served


def test_exact_execution_id_cannot_substitute_other_executions():
    repo = FakeRepository(product(today()), product(today(), candidate=True))
    served = AnalysisService(repo).baseline(
        "2327", execution_id="00000000-0000-0000-0000-000000000001")
    assert "risk_serving_status" not in served
    assert not any("payload_json ?" in sql for sql, _ in repo.calls)


def test_expired_candidate_not_promoted():
    repo = FakeRepository(product(today()), product(today() - timedelta(days=8), candidate=True))
    served = AnalysisService(repo).baseline("2327")
    assert "risk_serving_status" not in served
    assert not any("FROM private.risk_model_activation" in sql for sql, _ in repo.calls)


def test_invalid_candidate_hash_fails_closed():
    older = product(today() - timedelta(days=1), candidate=True)
    older["risk_first_release_candidate"]["future_20d_volatility_annualized"] = .99
    with pytest.raises(HTTPException) as error:
        AnalysisService(FakeRepository(product(today()), older)).baseline("2327")
    assert error.value.status_code == 503


def test_latest_active_and_inactive_remain_reversible():
    latest = product(today(), candidate=True)
    active = AnalysisService(FakeRepository(latest)).baseline("2327")
    assert risk(active)["model_status"] == "first_release_approved"
    rollback = AnalysisService(FakeRepository(latest, mode="DETERMINISTIC")).baseline("2327")
    assert "risk_serving_status" not in rollback
    assert "risk_first_release_candidate" not in rollback
    assert risk(rollback)["model_status"] == "deterministic-unpromoted-v1"


def test_wrong_symbol_does_not_mix_forecast():
    prior = product(today() - timedelta(days=1), candidate=True, symbol="2330")
    with pytest.raises(ValueError, match="identity mismatch"):
        AnalysisService(FakeRepository(product(today()), prior)).baseline("2327")
