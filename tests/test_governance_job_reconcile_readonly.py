"""Offline security and classification tests for bounded governance job reconciliation."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/gcp/governance_job_reconcile_readonly.py"
CODE = SCRIPT.read_text(encoding="utf-8")

def test_reconcile_script_is_get_only_and_bounded():
    ast.parse(CODE)
    assert "MAX_PAGES_PER_JOB = 12" in CODE
    assert "MAX_ACTIVE_REFS = 100" in CODE
    assert "ALLOWED_JOBS = tuple(sorted(gcp.REQUIRED_JOBS))" in CODE
    assert "gcp.cloud(execution)  # GET only" in CODE
    assert "gcp.cloud(gcp.ROOT + \"/jobs/\" + job + \"/executions\" + suffix)  # GET only" in CODE
    for unsafe in ("subprocess.run(", "gcp.cloud(execution, ", "requests.post(",
                   "job:run", "UPDATE control", "DELETE FROM", "private.positions"):
        assert unsafe not in CODE

def test_join_is_not_claimed_when_missing():
    assert "NOT_AVAILABLE_WITHOUT_EXPLICIT_OCCURRENCE_LINK" in CODE
    assert "NO_EXECUTION_REFERENCE" in CODE
    assert "cloud_execution_ref_invalid" in CODE
    assert "pg_receipt_sha_mismatch" in CODE
    assert "pg_active_reference_section_incomplete" in CODE
    assert "pagination_complete" in CODE
