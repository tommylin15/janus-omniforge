"""Offline security contracts for one-time Controller-only ledger reconciliation."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/gcp"))
import controller_ledger_repair_dev as repair


def request():
    return {
        "intent": "controller-ledger-backup-occurrence-repair",
        "approved": True,
        "scope": "existing-dev-controller-only",
        "sha": repair.SOURCE_SHA,
        "release_run": int(repair.RELEASE_RUN),
        "backup_dates": list(repair.BACKUP_DAYS),
        "no_backup_execution": True,
        "no_gcs_mutation": True,
        "no_iam_expansion": True,
        "no_api_deployment": True,
    }


def test_exact_request_rejects_scope_and_safety_drift():
    repair.request_guard(request())
    for key in request():
        altered = request()
        altered[key] = None
        with pytest.raises(ValueError, match="controller_repair_request_invalid"):
            repair.request_guard(altered)
    assert repair.JOB == "janus-batch-controller"
    assert repair.COMPONENT == "ingestion-core"
    assert repair.BACKUP_DAYS == tuple(
        "2026-10-" + str(d).zfill(2) for d in range(18, 24))


def test_postgres_probe_only_repairs_six_receipt_backed_rows():
    ast.parse(repair.PROBE)
    src = repair.PROBE
    assert "pg_try_advisory_lock(1835102836,3)" in src
    assert "control.ledger_backup_requests" in src
    assert "WHERE occurrence_id=%s AND state=%s::jsonb" in src
    assert "AND state->>'status'='running' RETURNING occurrence_id" in src
    assert "backup_receipt_invalid" in src
    assert "retention_cleanup" in src
    assert "final_succeeded" in src
    assert "backup_requests_unchanged" in src
    assert "control.batch_event_outbox" in src
    for banned in ("cleanup_old_backups(", "DELETE FROM", "TRUNCATE", "DROP TABLE",
                   "gcs.Client(", "storage.Client(", "dispatch_job(", "request_backup(",
                   "private.positions", "ALTER ROLE"):
        assert banned not in src
    assert src.count("UPDATE control.batch_occurrences") == 1
    assert "UPDATE control.ledger_backup_requests" not in src


def test_execution_override_keeps_existing_controller_identity_and_entrypoint():
    data = {"template": {"template": {"containers": [
        {"name": "run", "command": ["python"], "image": "fixed"}]}}}
    row = repair.repair_override(data)
    assert row["args"] == ["-c", repair.PROBE]
    assert row["name"] == "run"
    assert {x["name"]: x["value"] for x in row["env"]} == {
        "JANUS_CONTROLLER_LEDGER_REPAIR_SHA": repair.SOURCE_SHA,
        "QUEUE_CONSUMER": "false",
    }
    data["template"]["template"]["containers"][0]["command"] = []
    assert repair.repair_override(data)["args"][:2] == ["python", "-c"]
    data["template"]["template"]["containers"][0]["command"] = ["bash"]
    with pytest.raises(ValueError, match="entrypoint_unexpected"):
        repair.repair_override(data)


def test_controller_only_mutation_and_verified_rollback():
    code = (ROOT / "scripts/gcp/controller_ledger_repair_dev.py").read_text()
    ast.parse(code)
    assert "gcp.update(JOB,target,config_hash)" in code
    assert "gcp.update(JOB,old,config_hash)" in code
    assert "gcp.scheduler_fingerprint" in code
    assert "gcp.wait_for_terminal_executions" in code
    assert 'gcp.set_scheduler("pause","PAUSED")' in code
    assert 'gcp.set_scheduler("resume","ENABLED")' in code
    assert 'gcp.command(gcp.LEASE+["acquire"])' in code
    assert 'gcp.command(gcp.LEASE+["release","--safe-to-release"])' in code
    assert '"PREFLIGHT_BLOCKED_NO_MUTATION"' in code
    assert "gcp.canary(JOB,target,config_hash,journal,save)" in code
    assert "gcp.job(JOB)" in code
    assert "NO_EXECUTION_REFERENCE" not in code
    for banned in ("gcp.update(\"janus-ingestion-core\"", "gcp.update(\"janus-api\"",
                   "gcp.update(\"janus-private-pipeline\"", "gcp.update(\"janus-intelligence-mart\"",
                   "gcloud iam ", "gcloud sql", "gcloud storage rm"):
        assert banned not in code
