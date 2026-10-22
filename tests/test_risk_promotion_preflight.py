"""Risk formal publication never follows automatically from candidate + shadow."""
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/gcp"))
from risk_promotion_preflight import (MODEL_SHA, SCREENING_DATE,
                                      elapsed_weekdays_after, evaluate)


def sample_shadow(rows=1720):
    return {
        "analysis_as_of": SCREENING_DATE,
        "model_sha256": MODEL_SHA,
        "publication_allowed": False,
        "status": "SHADOW_UNVALIDATED",
        "rows": [{"symbol": str(i)} for i in range(rows)],
        "core_snapshot_id": "pinned-core",
        "source_manifest_hash": "sha256:" + "a" * 64,
    }


def test_actual_shadow_is_good_runtime_evidence_but_not_promotion_evidence():
    result = evaluate(MODEL_SHA, sample_shadow(), date(2026, 10, 22))
    assert result["audit_status"] == "COMPLETED"
    assert result["promotion_status"] == "BLOCKED_NOT_ACTIVE"
    assert result["verified"]["candidate_gcs_sha256"] == MODEL_SHA
    assert result["verified"]["shadow_prediction_count"] == 1720
    assert result["verified"]["prospective_oos_state"] == "PENDING"
    assert "untouched_prospective_20_session_matured_oos" not in result["blocked_or_unverified_gates"]
    assert "historical_delisted_master_not_reconstructed" in result["accepted_first_release_limits"]
    assert "eight_feature_cutoff_and_revision_pit_guard" in result["blocked_or_unverified_gates"]
    assert "atomic_registry_cas_with_rollback" in result["blocked_or_unverified_gates"]
    assert result["publication_allowed"] is False
    assert not any(result[k] for k in ("would_write_registry", "would_change_api",
                                       "would_execute_model"))


def test_future_clock_alone_never_creates_validated_oos():
    result = evaluate(MODEL_SHA, sample_shadow(), date(2026, 12, 31))
    assert result["verified"]["upper_bound_weekdays_after_shadow"] >= 20
    assert result["verified"]["prospective_oos_state"] == "MATURITY_REQUIRES_CALENDAR_AND_EOD_EVIDENCE"
    assert "prospective_20_market_sessions_maturity_and_monthly_evaluation" in result["post_activation_acceptance"]
    assert not any("prospective" in x for x in result["blocked_or_unverified_gates"])
    assert result["promotion_status"] == "BLOCKED_NOT_ACTIVE"


def test_missing_or_tampered_evidence_remains_blocked():
    for model, shadow in (
        (None, sample_shadow()), ("0" * 64, sample_shadow()),
        (MODEL_SHA, None), (MODEL_SHA, sample_shadow(rows=0)),
        (MODEL_SHA, {**sample_shadow(), "publication_allowed": True}),
        (MODEL_SHA, {**sample_shadow(), "status": "ACTIVE"}),
    ):
        result = evaluate(model, shadow, date(2026, 10, 22))
        assert result["promotion_status"] == "BLOCKED_NOT_ACTIVE"
        assert result["publication_allowed"] is False
        assert result["blocked_or_unverified_gates"]


def test_weekdays_are_only_an_upper_bound_not_an_exchange_calendar():
    assert elapsed_weekdays_after(date(2026, 10, 21), date(2026, 10, 22)) == 1
    assert elapsed_weekdays_after(date(2026, 10, 23), date(2026, 10, 25)) == 0
    assert elapsed_weekdays_after(date(2026, 10, 22), date(2026, 10, 21)) == 0
