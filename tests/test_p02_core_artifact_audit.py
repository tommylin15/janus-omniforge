"""P0-2 live audit source: no mutation and bounded immutable Core checks."""
from __future__ import annotations
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/gcp/p02_core_artifact_audit.py"
def test_readonly_probe_is_scoped_and_bounded():
    s=SOURCE.read_text()
    ast.parse(s)
    import sys
    sys.path.insert(0,str(ROOT/"scripts/gcp"))
    import p02_core_artifact_audit as p
    ast.parse(p.PROBE)
    assert "default_transaction_read_only=on" in p.PROBE
    assert "BEGIN READ ONLY" in p.PROBE
    assert "control.core_ready_events" in p.PROBE
    assert "control.execution_items" in p.PROBE
    assert "e.requested_at >= now()-interval '30 days'" in p.PROBE
    assert "LIMIT 301" in p.PROBE
    assert "sha256:"+"" in p.PROBE
    assert "core_snapshot_hash" in p.PROBE
    assert "core_snapshot_id" in p.PROBE
    assert "AuthorizedSession(credentials)" in p.PROBE
    assert '"ifGenerationMatch":generation' in p.PROBE
    assert "google.cloud" not in p.PROBE
    assert "r'/executions/" not in p.PROBE
    assert '"QUEUE_CONSUMER","value":"false"' in s
    assert "before!=gcp.fingerprint(gcp.job(JOB))" in s
    assert "job_template_unchanged" in s
    for dangerous in ("UPDATE control.", "DELETE FROM", "DROP TABLE", "TRUNCATE",
                      ".delete(", ".upload_from_", "dispatch_job(",
                      "private.ledger", "private.positions"):
        assert dangerous not in p.PROBE
