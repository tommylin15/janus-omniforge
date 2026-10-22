#!/usr/bin/env python3
"""Bounded Risk model registry CAS contract (no implicit ACTIVE mutation).

The existing dev bucket is the only registry store. Generation-match writes
must be performed by an approved GitHub Actions deployment owner; never a
Colab notebook, public API, research script or preflight observation.

No network or GCS write occurs importing/calling plan_transition. This file
is a reusable *primitive*, not evidence that UI/serving is already connected.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re

BUCKET = "gen-lang-client-0593591102-dev-mart"
ACTIVE_OBJECT = "risk-models/registry/risk-active.json"
MODEL_VERSION = "risk-xgboost8-2025h2-v1"
MODEL_SHA256 = "36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044"
MODEL_OBJECT = "risk-models/candidates/2026Q3-20261022/risk-xgboost8-2025h2-v1.ubj"
FEATURE_VERSION = "risk-ohlcv8-market-session-v1"
SHA = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_PROMOTION_EVIDENCE = (
    "risk_candidate_gcs_byte_sha256",
    "risk_training_serving_vector_parity",
    "risk_cutoff_and_action_window",
    "risk_target_union_and_exclusion_readback",
    "risk_serving_projection_and_api_ui_ready",
    "risk_rollback_baseline_readback",
    "risk_ci_exact_sha",
)


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def validate_pointer(pointer: dict | None) -> None:
    if pointer is None:
        return
    if not isinstance(pointer, dict) or pointer.get("schema_version") != 1:
        raise ValueError("invalid risk registry schema")
    if pointer.get("role") != "risk" or pointer.get("mode") not in ("ACTIVE", "DETERMINISTIC"):
        raise ValueError("invalid risk registry role/mode")
    if pointer["mode"] == "ACTIVE":
        if (pointer.get("model_version") != MODEL_VERSION
                or pointer.get("model_sha256") != MODEL_SHA256
                or pointer.get("feature_version") != FEATURE_VERSION
                or pointer.get("model_gcs_uri") != f"gs://{BUCKET}/{MODEL_OBJECT}"):
            raise ValueError("Risk active pointer model identity mismatch")
    else:
        if any(pointer.get(k) is not None for k in
               ("model_version", "model_sha256", "feature_version", "model_gcs_uri")):
            raise ValueError("deterministic fallback must not name an active model")
    if not SHA.fullmatch(str(pointer.get("source_commit_sha256", ""))):
        # Runtime source is a Git commit SHA1, not a model hash. The field name
        # intentionally encodes the digest kind; don't accept shortened SHA.
        raise ValueError("invalid source commit identity")


def _candidate_pointer(*, model_active: bool, source_sha: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("full Git source SHA required")
    return {
        "schema_version": 1, "role": "risk",
        "mode": "ACTIVE" if model_active else "DETERMINISTIC",
        "model_version": MODEL_VERSION if model_active else None,
        "model_sha256": MODEL_SHA256 if model_active else None,
        "model_gcs_uri": f"gs://{BUCKET}/{MODEL_OBJECT}" if model_active else None,
        "feature_version": FEATURE_VERSION if model_active else None,
        "source_commit_sha256": sha256(source_sha.encode("ascii")).hexdigest(),
    }


def plan_transition(*, current: dict | None, current_generation: int,
                    expected_previous_sha256: str | None, candidate_sha256: str,
                    source_sha: str, proof: dict[str, str],
                    approved: bool, activate: bool) -> dict:
    """Build an exact generation-fenced promotion or rollback plan.

    The return is a DRY-RUN proposal. Actual GCS reads/writes and multi-step
    rollback/readback must be orchestrated under existing deploy lease.
    """
    validate_pointer(current)
    if not isinstance(current_generation, int) or isinstance(current_generation, bool) or current_generation < 0:
        raise ValueError("invalid GCS generation")
    if (current is None) != (current_generation == 0):
        raise ValueError("pointer / generation mismatch")
    if candidate_sha256 != MODEL_SHA256:
        raise ValueError("candidate model hash mismatch")
    prev = current.get("model_sha256") if current else None
    if prev != expected_previous_sha256:
        raise ValueError("stale expected-previous model CAS")
    if not approved:
        raise PermissionError("explicit owner approval required for risk registry mutation")
    if activate:
        missing = sorted(x for x in REQUIRED_PROMOTION_EVIDENCE if proof.get(x) != "PASS")
        if missing:
            raise ValueError("risk promotion missing mandatory evidence: " + ",".join(missing))
        if current is not None and current["mode"] == "ACTIVE":
            raise ValueError("Risk model already ACTIVE; no unnecessary re-promotion")
    # Rollback is always allowed after approval and correct CAS, including on
    # a newly created registry; it may never redirect to unreviewed model bytes.
    next_pointer = _candidate_pointer(model_active=activate, source_sha=source_sha)
    return {
        "bucket": BUCKET, "object": ACTIVE_OBJECT,
        "if_generation_match": current_generation,
        "previous": current,
        "previous_generation": current_generation,
        "next": next_pointer,
        "next_sha256": sha256(canonical(next_pointer)).hexdigest(),
        "activation_requested": activate,
        "requires_existing_deploy_lease": True,
        "write_performed": False,
    }


def validate_transition_readback(plan: dict, actual: dict,
                                 actual_generation: int) -> None:
    if actual_generation <= plan["if_generation_match"]:
        raise ValueError("GCS CAS write generation did not advance")
    validate_pointer(actual)
    if canonical(actual) != canonical(plan["next"]):
        raise ValueError("GCS registry CAS readback mismatch")
    if sha256(canonical(actual)).hexdigest() != plan["next_sha256"]:
        raise ValueError("GCS registry CAS content hash mismatch")
