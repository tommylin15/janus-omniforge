"""Offline contracts for the bounded SEQ-08 model activation operator."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/gcp/seq08_activate_registry.py"
SPEC = importlib.util.spec_from_file_location("seq08_registry_operator", SOURCE)
operator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(operator)


def approved():
    return {
        "intent": "seq08-activate-five-real-heads",
        "approved": True, "apply": True,
        "scope": "existing-dev-mart-single-atomic-pointer",
        "source_sha": operator.RELEASE_SHA,
        "release_run": operator.RELEASE_RUN,
        "jobs_run": operator.JOBS_RUN, "api_run": operator.API_RUN,
        "allow_old_model_fallback": False, "no_new_resources": True,
    }


def fake_requests(monkeypatch, override=None, source_sha=None):
    actual = approved() | (override or {})
    monkeypatch.setattr(operator, "read_json", lambda path:
        actual if path == "ops/seq08-model-activation-request.json"
        else {"source_sha": source_sha or operator.RELEASE_SHA,
              "sha": source_sha or operator.RELEASE_SHA})


def test_request_requires_explicit_approved_exact_version(monkeypatch):
    fake_requests(monkeypatch)
    assert operator.gate_request()["approved"] is True
    for override in ({"approved": False}, {"apply": False},
                     {"allow_old_model_fallback": True},
                     {"scope": "all-projects"},
                     {"source_sha": "0" * 40}):
        fake_requests(monkeypatch, override)
        with pytest.raises(ValueError):
            operator.gate_request()


def test_request_rejects_runtime_source_drift(monkeypatch):
    fake_requests(monkeypatch, source_sha="0" * 40)
    with pytest.raises(ValueError, match="released_runtime"):
        operator.gate_request()


def test_gcs_missing_vs_denied_distinguished(monkeypatch):
    def command(args, timeout=90):
        return SimpleNamespace(returncode=1, stdout=b"",
                               stderr=b"ERROR: 404 object not found")
    monkeypatch.setattr(operator, "command", command)
    assert operator.gcs_read(operator.POINTER) is None
    monkeypatch.setattr(operator, "command", lambda args, timeout=90:
        SimpleNamespace(returncode=1, stdout=b"", stderr=b"ERROR: 403 Access Denied"))
    with pytest.raises(ValueError, match="gcs_read_error_not_missing"):
        operator.gcs_read(operator.POINTER)


def test_github_gate_requires_exact_job_and_sha(monkeypatch):
    payload = {"status": "completed", "conclusion": "success",
               "headSha": operator.RELEASE_SHA,
               "jobs": [{"name": "release-verify", "status": "completed", "conclusion": "success"}]}
    monkeypatch.setattr(operator, "command", lambda args, timeout=90:
        SimpleNamespace(returncode=0, stdout=json.dumps(payload).encode(), stderr=b""))
    operator.github_gate(operator.RELEASE_RUN, "release-verify",
                         expected_sha=operator.RELEASE_SHA)
    with pytest.raises(ValueError, match="github_gate_not_successful"):
        operator.github_gate(operator.RELEASE_RUN, "jobs-rollout")
    with pytest.raises(ValueError, match="github_gate_not_successful"):
        operator.github_gate(operator.RELEASE_RUN, "release-verify",
                             expected_sha="0" * 40)
