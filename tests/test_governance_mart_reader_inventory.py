"""Bounded code/Cloud Run metadata inventory safety assertions."""
import ast
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "scripts/gcp/governance_mart_reader_inventory.py"
CODE = P.read_text(encoding="utf-8")

def test_mart_reader_inventory_is_fixed_and_readonly():
    ast.parse(CODE)
    assert "MAX_CODE_FILES = 2000" in CODE
    assert "MAX_FILE_BYTES = 1_000_000" in CODE
    assert "MAX_MATCHES = 400" in CODE
    assert "gcp.cloud(path)  # GET only" in CODE
    assert "actual_per_table_reader_usage" in CODE
    assert '"UNKNOWN_NO_TABLE_LEVEL_RUNTIME_TRACE"' in CODE
    assert "no_literal_hit_means_no_reader" in CODE
    assert '"source_git_sha"' in CODE
    assert CODE.count('"_v1"') == 0 or "mart_screening_signals_v1" in CODE
    for dangerous in ("jobs:run", "gcp.cloud(path, ", "cloud scheduler jobs run", "DELETE FROM",
                      "UPDATE control.executions", "private.positions"):
        assert dangerous not in CODE

def test_scanner_excludes_self_and_marks_handle_declarations():
    assert "path.resolve() == Path(__file__).resolve()" in CODE
    assert '"DECLARATION_ONLY"' in CODE
    assert 'jobs/intelligence-mart/intelligence_mart/storage.py' in CODE
