"""Offline contract tests for the bounded governance metadata collector.

No GCP/PG/Cloud Run access; these tests must never trigger a live Job.
"""
from __future__ import annotations

import ast
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/gcp/governance_metadata_readonly.py"
spec = spec_from_file_location("governance_metadata_readonly", SCRIPT)
module = module_from_spec(spec)
spec.loader.exec_module(module)

SAFE = {
    "intent": "c0-live-readonly-governance-metadata",
    "scope": "existing-dev",
    "read_only": True,
    "no_data_mutation": True,
    "no_template_mutation": True,
    "no_private_row_data": True,
    "job": "janus-ingestion-core",
}

def test_probe_code_parses_and_has_readonly_transaction():
    ast.parse(module.PROBE)
    assert module.PROBE.count('BEGIN READ ONLY') == 1
    assert 'default_transaction_read_only=on' in module.PROBE
    assert 'table.scan(' not in module.PROBE
    assert '.to_arrow(' not in module.PROBE
    assert 'catalog.create_' not in module.PROBE
    assert 'SET LOCAL statement_timeout' in module.PROBE
    assert 'pg_catalog.pg_class' in module.PROBE
    assert 'information_schema.columns' in module.PROBE
    assert 'catalog.iceberg_tables' in module.PROBE
    assert 'control.schema_migrations' in module.PROBE
    assert 'metadata_location' in module.PROBE

def test_request_contract_enforces_readonly_scope():
    module.validate_request(SAFE)
    for key, value in SAFE.items():
        invalid = dict(SAFE)
        invalid[key] = "UNSAFE" if isinstance(value, str) else False
        with pytest.raises(ValueError):
            module.validate_request(invalid)

def test_override_uses_existing_job_and_disables_consumer():
    job = {"template": {"template": {"containers": [{"name":"job","command":["python"]}]}}}
    result = module.override(job, "a" * 40)
    assert result["name"] == "job"
    assert result["args"] == ["-c",module.PROBE]
    assert result["env"] == [
        {"name":"QUEUE_CONSUMER","value":"false"},
        {"name":"JANUS_GOVERNANCE_SOURCE_SHA","value":"a"*40}]
    job["template"]["template"]["containers"][0]["command"] = ["bash"]
    with pytest.raises(ValueError):
        module.override(job, "a" * 40)

def test_output_has_no_secret_bearing_diagnostics():
    # Error code is type + SQLSTATE, not exception text or credential payload.
    assert '"sqlstate"' in module.PROBE
    assert '"error_class"' in module.PROBE
    assert "print(traceback" not in module.PROBE
    assert "print(os.environ)" not in module.PROBE
    assert "SELECT * FROM private." not in module.PROBE


def test_reader_dependency_probe_limits_scope_to_aggregates():
    assert '"control_execution_30d"' in module.PROBE
    assert '"mart_table_identifier_constraint"' in module.PROBE
    assert '"publication_pg_scan_cumulative"' in module.PROBE
    assert "interval '30 days'" in module.PROBE
    assert "GROUP BY trigger_type,status" in module.PROBE
    assert "pg_catalog.pg_get_constraintdef" in module.PROBE
    assert "pg_catalog.pg_stat_user_tables" in module.PROBE
    assert "requested_symbols" not in module.PROBE
    assert "scope_id" not in module.PROBE

def test_nonterminal_lease_probe_is_bounded_and_metadata_only():
    assert '"control_nonterminal_lease_30d"' in module.PROBE
    assert '"control_nonterminal_occurrence_link_30d"' in module.PROBE
    assert '"control_active_batch_occurrences_30d"' in module.PROBE
    assert "claimed_until > clock_timestamp()" in module.PROBE
    assert "NO_LEASE" in module.PROBE and "EXPIRED_LEASE" in module.PROBE
    assert "OCCURRENCE_LINKED" in module.PROBE
    assert "interval '48 hours'" in module.PROBE
    assert "LIMIT 101" in module.PROBE
    assert "execution_id::text" in module.PROBE
    # Only the join key is used inside PG; no raw UUID is selected.
    assert "SELECT execution_id,trigger_type,status,claimed_until" in module.PROBE
    assert "SELECT state->>'job',state->>'status',state->>'execution'" in module.PROBE
    assert "UPDATE control.executions" not in module.PROBE
