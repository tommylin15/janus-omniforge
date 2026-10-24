"""API-only dev promotion gates must never implicitly mutate Jobs or storage."""
import sys
from pathlib import Path

import pytest
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "gcp"))
import ghcr_api_only_promote as p


def approved():
    return {"intent": "promote-existing-dev-api-only-fixed-ghcr",
            "approved": True, "scope": "existing-dev-janus-api-only",
            "source_sha": "a" * 40, "prior_serving_sha": "b" * 40,
            "release_run": "123456789", "candidate_run": "123456788",
            "auth_boundary_run": "123456787", "rollback_mode": "reversible_ghcr",
            "no_jobs_mutation": True, "no_scheduler_mutation": True,
            "no_storage_mutation": True, "no_iam_mutation": True}


def test_request_exact_dev_api_only_controls():
    assert p.approved_request(approved())["no_jobs_mutation"] is True
    for key, value in [("approved", False), ("no_jobs_mutation", False),
                       ("no_scheduler_mutation", False),
                       ("no_storage_mutation", False), ("no_iam_mutation", False),
                       ("scope", "all-jobs"), ("prior_serving_sha", "a" * 40)]:
        bad = approved()
        bad[key] = value
        with pytest.raises(ValueError):
            p.approved_request(bad)


def test_upstream_failure_and_missing_job_are_rejected(monkeypatch):
    import json
    monkeypatch.setattr(p, "command", lambda args: json.dumps({
        "status": "completed", "conclusion": "success", "jobs": []}))
    with pytest.raises(ValueError, match="upstream_job_receipt_invalid"):
        p.check_run("123456789", "candidate")
    monkeypatch.setattr(p, "command", lambda args: json.dumps({
        "status": "completed", "conclusion": "failure",
        "jobs": [{"name": "candidate", "conclusion": "success"}]}))
    with pytest.raises(ValueError, match="upstream_run_not_successful"):
        p.check_run("123456789", "candidate")


def test_http_failure_never_counted_as_released_success(tmp_path, monkeypatch):
    # A malformed request must fail closed without any lease or GCP operation.
    monkeypatch.setattr(p, "REQUEST", tmp_path / "request.json")
    p.REQUEST.write_text("{}")
    monkeypatch.setattr(p, "command",
                        lambda args: (_ for _ in ()).throw(AssertionError("unexpected command")))
    receipt = tmp_path / "receipt.json"
    assert p.promote(receipt) == 78
    assert __import__("json").loads(receipt.read_text())["phase"] == "PREFLIGHT_BLOCKED"


def test_direct_mode_switches_only_once_and_never_claims_rehearsal(tmp_path, monkeypatch):
    import json
    req = approved()
    req["traffic_validation_mode"] = "direct"
    monkeypatch.setattr(p, "REQUEST", tmp_path / "request.json")
    p.REQUEST.write_text(json.dumps(req))
    monkeypatch.setattr(p, "preflight", lambda _payload: None)
    baseline = {"status": {"traffic": []}}
    monkeypatch.setattr(p, "live_pair", lambda _payload:
                        (baseline, "old-revision", "new-revision", "ghcr.io/example"))
    monkeypatch.setattr(p, "describe", lambda: {"status": {}})
    monkeypatch.setattr(p.api, "active", lambda _: "new-revision")
    switches = []
    monkeypatch.setattr(p.api, "switch", lambda revision, _baseline: switches.append(revision))
    monkeypatch.setattr(p.api, "health", lambda _sha: None)
    commands = []
    monkeypatch.setattr(p, "command", lambda args: commands.append(list(args)) or "")
    receipt = tmp_path / "receipt.json"
    assert p.promote(receipt) == 0
    result = json.loads(receipt.read_text())
    assert switches == ["new-revision"]
    assert result["phase"] == "PASS_API_ONLY_100_PERCENT"
    assert result["traffic_validation_mode"] == "direct"
    assert result["rollback_exercised"] is False
    assert result["lease_released"] is True
    assert any("release" in args for args in commands)


def test_direct_mode_rollback_on_real_health_failure(tmp_path, monkeypatch):
    import json
    req = approved()
    req["traffic_validation_mode"] = "direct"
    monkeypatch.setattr(p, "REQUEST", tmp_path / "request.json")
    p.REQUEST.write_text(json.dumps(req))
    monkeypatch.setattr(p, "preflight", lambda _payload: None)
    baseline = {"status": {"traffic": []}}
    monkeypatch.setattr(p, "live_pair", lambda _payload:
                        (baseline, "old-revision", "new-revision", "ghcr.io/example"))
    monkeypatch.setattr(p, "describe", lambda: {"status": {}})
    monkeypatch.setattr(p.api, "active", lambda _: "old-revision")
    switches = []
    monkeypatch.setattr(p.api, "switch", lambda revision, _baseline: switches.append(revision))
    def health(sha):
        if sha == req["source_sha"]:
            raise RuntimeError("candidate_health_failed")
    monkeypatch.setattr(p.api, "health", health)
    monkeypatch.setattr(p, "command", lambda _: "")
    receipt = tmp_path / "receipt.json"
    assert p.promote(receipt) == 78
    result = json.loads(receipt.read_text())
    assert switches == ["new-revision", "old-revision"]
    assert result["phase"] == "RESTORED_PREVIOUS_100_PERCENT"
    assert result["lease_released"] is True
