"""No-mutation defaults and bounded recovery contract for Scheduler IAM drill."""
from pathlib import Path

ROOT=Path(__file__).parents[1]

def test_operator_drill_is_exact_job_only_and_has_fail_safe_controls():
    text=(ROOT/".github/workflows/ghcr-scheduler-operator-drill.yml").read_text()
    assert 'JOB: janus-ingestion-daily' in text
    assert 'group: janus-dev-scheduler-operator-drill' in text
    assert "until_next_tick < 15" in text
    assert 'gcloud run jobs executions list --job=janus-batch-controller' in text
    assert 'gcloud scheduler jobs pause "$JOB"' in text
    assert 'gcloud scheduler jobs resume "$JOB"' in text
    assert "trap cleanup EXIT" in text
    assert "lock_acquired=1" in text
    assert "independent-recovery:" in text
    assert "if: always()" in text
    assert '[[ "$after" == "ENABLED" ]]' in text
    assert "gcloud scheduler jobs run" not in text
    assert "gcloud run jobs update" not in text
    assert "gcloud run jobs execute" not in text
    assert "gcloud scheduler jobs delete" not in text


def test_emergency_recovery_requires_lease_and_exact_whitelist():
    text=(ROOT/".github/workflows/ghcr-scheduler-recover-dev.yml").read_text()
    assert 'JOB: janus-ingestion-daily' in text
    assert 'resume-existing-janus-drill' in text
    assert 'git/ref/tags/$LOCK' in text
    assert 'gcloud scheduler jobs resume "$JOB"' in text
    assert 'state == "PAUSED"' not in text or "PAUSED" in text
    assert 'gcloud run jobs execute' not in text
    assert 'gcloud scheduler jobs create' not in text
    assert 'gcloud scheduler jobs run' not in text
