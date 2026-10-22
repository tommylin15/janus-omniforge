"""Risk first promotion/rollback must be a generation-fenced, audited no-op until approved."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/gcp"))
from risk_registry_cas import (MODEL_SHA256, REQUIRED_PROMOTION_EVIDENCE,
                               plan_transition, validate_pointer,
                               validate_transition_readback)


GIT_SHA = "5f2576cde9bd8c747f96befcf6e7aa2c5510ee1f"
PROOF = {item: "PASS" for item in REQUIRED_PROMOTION_EVIDENCE}


def start(*, approved=True, proof=PROOF):
    return plan_transition(current=None, current_generation=0,
        expected_previous_sha256=None, candidate_sha256=MODEL_SHA256,
        source_sha=GIT_SHA, proof=proof, approved=approved, activate=True)


def test_not_approved_never_produces_registry_write_plan():
    with pytest.raises(PermissionError, match="approval"):
        start(approved=False)


def test_missing_serving_or_parity_evidence_blocks_active_transition():
    for key in REQUIRED_PROMOTION_EVIDENCE:
        with pytest.raises(ValueError, match="missing mandatory evidence"):
            start(proof={k: v for k, v in PROOF.items() if k != key})


def test_first_promotion_pins_exact_generation_digest_and_requires_readback():
    planned = start()
    assert planned["if_generation_match"] == 0
    assert planned["next"]["model_sha256"] == MODEL_SHA256
    assert planned["next"]["source_git_sha"] == GIT_SHA
    assert planned["write_performed"] is False
    assert planned["requires_existing_deploy_lease"] is True
    validate_transition_readback(planned, planned["next"], actual_generation=1)
    with pytest.raises(ValueError, match="generation"):
        validate_transition_readback(planned, planned["next"], actual_generation=0)
    with pytest.raises(ValueError, match="mismatch"):
        validate_transition_readback(planned, dict(planned["next"], model_sha256="0" * 64), 2)


def test_stale_expected_previous_cannot_overwrite_or_repromote():
    active = start()["next"]
    with pytest.raises(ValueError, match="stale"):
        plan_transition(current=active, current_generation=9,
            expected_previous_sha256=None, candidate_sha256=MODEL_SHA256,
            source_sha=GIT_SHA, proof=PROOF, approved=True, activate=False)
    with pytest.raises(ValueError, match="already ACTIVE"):
        plan_transition(current=active, current_generation=9,
            expected_previous_sha256=MODEL_SHA256, candidate_sha256=MODEL_SHA256,
            source_sha=GIT_SHA, proof=PROOF, approved=True, activate=True)


def test_explicit_rollback_to_deterministic_requires_generation_and_readback():
    current = start()["next"]
    revert = plan_transition(current=current, current_generation=5,
        expected_previous_sha256=MODEL_SHA256, candidate_sha256=MODEL_SHA256,
        source_sha=GIT_SHA, proof={}, approved=True, activate=False)
    assert revert["next"]["mode"] == "DETERMINISTIC"
    assert revert["next"]["model_sha256"] is None
    assert revert["if_generation_match"] == 5
    validate_transition_readback(revert, revert["next"], 6)
    with pytest.raises(PermissionError):
        plan_transition(current=current, current_generation=5,
            expected_previous_sha256=MODEL_SHA256, candidate_sha256=MODEL_SHA256,
            source_sha=GIT_SHA, proof={}, approved=False, activate=False)


def test_rejects_invalid_model_hash_pointer_or_fake_generation():
    with pytest.raises(ValueError, match="hash mismatch"):
        plan_transition(current=None, current_generation=0,
            expected_previous_sha256=None, candidate_sha256="bad",
            source_sha=GIT_SHA, proof=PROOF, approved=True, activate=True)
    with pytest.raises(ValueError, match="pointer / generation"):
        plan_transition(current=None, current_generation=4,
            expected_previous_sha256=None, candidate_sha256=MODEL_SHA256,
            source_sha=GIT_SHA, proof=PROOF, approved=True, activate=True)
    with pytest.raises(ValueError):
        validate_pointer({"schema_version": 1, "role": "risk", "mode": "ACTIVE",
                          "model_sha256": MODEL_SHA256,
                          "source_git_sha": GIT_SHA})
