"""No persistent Job mutation or ledger-writing in the bounded dev queue canary."""
import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/gcp/private_recalc_ghcr_canary.py"


def test_canary_is_one_synthetic_queue_request_with_original_verifier():
    source = SCRIPT.read_text()
    ast.parse(source)
    assert "runWithOverrides" not in source  # Uses Cloud Run v2 jobs.run JSON overrides
    assert 'f"{rollout.ROOT}/jobs/{name}:run"' in source
    assert '"etag":job["etag"]' in source
    assert '"taskCount":task_count' in source
    assert "JANUS_PRIVATE_RECALC_ACCEPTANCE_MODE" in source
    assert '"seed"' in source and '"verify"' in source and '"cleanup"' in source
    assert '"PRIVATE_RECALC_QUEUE_MODE":"true"' in source
    assert "seeded_requests" in source and "worker_tasks" in source
    assert "rollout.fence()" in source
    assert 'rollout.LEASE + ["acquire"]' in source
    assert 'rollout.LEASE + ["release","--safe-to-release"]' in source


def test_canary_never_changes_persistent_job_ledger_or_owner_metadata():
    source = SCRIPT.read_text()
    for forbidden in ("--update-env-vars", "jobs/patch", "jobs:patch",
                      "INSERT INTO private.ledger_events", "DELETE FROM private.ledger_events",
                      "private.users INSERT", "add-iam-policy-binding"):
        assert forbidden not in source
    assert "derived_mart_may_refresh" in source
    assert "source_image_or_job_drift" in source
    assert "execution_not_verified_retain_lease" in source
    assert "rollout.fence()" in source.split("finally:",1)[-1]


def test_canary_uses_verifiable_migration_and_existing_live_job_gate():
    workflow = (ROOT / ".github/workflows/private-recalc-ghcr-canary.yml").read_text()
    assert "ops/private-recalc-ghcr-canary-request.json" in workflow
    assert "Janus official TPEx ETF owner Mart reconciliation" in workflow
    assert "38652846263" in workflow
    assert "janus-dev-runtime-writers" in workflow
    assert "tests/test_private_recalc_queue.py" in workflow
    assert "schedule:" not in workflow
