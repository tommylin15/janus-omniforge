"""SEQ-08 Dev one-time real Job release identity / authorization safety."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
SPEC = importlib.util.spec_from_file_location("seq08_real_job", ROOT / "scripts/gcp/seq08_real_mart_acceptance.py")
real = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(real)


def request():
    return {
        "intent": "seq08-bounded-real-mart-acceptance",
        "approved": True, "scope": "existing-dev-one-intelligence-mart-job",
        "source_sha": real.SOURCE, "release_run": real.RELEASE_RUN,
        "jobs_run": real.JOBS_RUN, "api_run": real.API_RUN,
        "registry_run": real.REGISTRY_RUN, "mart_operation": "deep-coverage",
        "job_runs_allowed": 1, "training_allowed": False, "llm_allowed": False,
        "owner_ledger_writes_allowed": False, "new_resources_allowed": False,
    }


def test_strict_existing_dev_single_workload(monkeypatch):
    original = request()
    monkeypatch.setattr(real.Path, "read_text", lambda *_args, **_kwargs: json.dumps(original))
    assert real.authorize()["job_runs_allowed"] == 1
    for key, value in (
        ("approved", False), ("source_sha", "0"*40),
        ("job_runs_allowed", 2), ("training_allowed", True),
        ("owner_ledger_writes_allowed", True), ("scope", "production"),
    ):
        attempt = request()
        attempt[key] = value
        monkeypatch.setattr(real.Path, "read_text", lambda *_args, _attempt=attempt, **_kwargs: json.dumps(_attempt))
        with pytest.raises(ValueError):
            real.authorize()


def test_reject_unverified_workflow_job(monkeypatch):
    data = {"status": "completed", "conclusion": "success",
        "jobs": [{"name": "jobs-rollout", "conclusion": "success", "status": "completed"}]}
    monkeypatch.setattr(real.jobs, "command", lambda _: json.dumps(data))
    real.successful(real.JOBS_RUN, "jobs-rollout")
    with pytest.raises(ValueError):
        real.successful(real.JOBS_RUN, "promote-api-only")
    data["conclusion"] = "failure"
    with pytest.raises(ValueError):
        real.successful(real.JOBS_RUN, "jobs-rollout")
