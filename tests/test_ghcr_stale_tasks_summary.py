"""Task-level historical Cloud Run state remains evidence, never promotion."""
from __future__ import annotations

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
inspect_tasks = runpy.run_path(str(ROOT / "scripts/gcp/ghcr_stale_tasks_summary.py"))["inspect_tasks"]
EXEC = "janus-private-pipeline-7rkz7"


def test_empty_task_page_not_accepted_as_terminal():
    row = inspect_tasks(EXEC, [])
    assert row["task_readback"] == "READABLE_BOUNDED"
    assert row["tasks_scanned"] == 0
    assert row["terminal_confirmed"] is False


def test_task_activity_is_counts_only_and_never_claims_terminal():
    secret = "never-expose-private-owner-secrets"
    row = inspect_tasks(EXEC, [
        {"name": "private-task-1", "status": {"startTime": "2026-09-20T01:00:00Z"},
         "env": {"SECRET": secret}},
        {"name": "private-task-2", "status": {
            "startTime": "2026-09-20T01:00:00Z",
            "completionTime": "2026-09-20T01:01:00Z"}}])
    assert row["tasks_scanned"] == 2
    assert row["tasks_started"] == 2
    assert row["tasks_completed"] == 1
    assert row["terminal_confirmed"] is False
    assert secret not in repr(row)
    assert "private-task" not in repr(row)


@pytest.mark.parametrize("payload", [None, {}, [None], [{"status": "bad"}],
                                      [{"status": []}], [{}] * 100])
def test_unverifiable_or_truncated_task_list_blocks(payload):
    row = inspect_tasks(EXEC, payload)
    assert row["task_readback"] == "UNVERIFIABLE"
    assert row["terminal_confirmed"] is False


def test_incorrect_job_cannot_be_inspected():
    with pytest.raises(ValueError):
        inspect_tasks("janus-ingestion-core-123", [])


def test_workflow_is_bounded_read_only_and_never_changes_execution():
    content = (ROOT / ".github/workflows/ghcr-stale-executions-audit.yml").read_text()
    assert "gcloud run jobs executions tasks list" in content
    assert '--execution="$execution"' in content
    assert "--limit=100" in content
    assert "--succeeded" in content  # gcloud must include succeeded tasks too
    assert "ghcr_stale_tasks_summary.py" in content
    assert "task_inspections:" in content
    assert "tasks_terminal_confirmed:false" in content
    for mutation in (
        "gcloud run jobs executions cancel", "gcloud run jobs executions delete",
        "gcloud run jobs execute", "gcloud run jobs update",
        "gcloud scheduler jobs pause", "gcloud scheduler jobs resume",
        "gcloud builds submit",
    ):
        assert mutation not in content


def test_request_explicitly_prohibits_mutation():
    request = (ROOT / "ops/ghcr-stale-executions-audit-request.json").read_text()
    assert '"allow_cancel": false' in request
    assert '"allow_execute": false' in request
    assert '"allow_mutation": false' in request
