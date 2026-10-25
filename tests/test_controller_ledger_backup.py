from datetime import datetime, timezone
from pathlib import Path
import runpy
from types import SimpleNamespace

from ingestion_core.batch_controller import due_batches
from ingestion_core.ledger_backup import poll_backup


def test_backup_has_one_controller_occurrence_and_missing_receipt_is_ambiguous():
    rows = [row for row in due_batches(datetime(2026, 10, 14, tzinfo=timezone.utc))
            if row[1].name == 'ledger-backup']
    assert len(rows) == 1 and rows[0][2].hour == 2
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, *_): pass
        def fetchone(self): return None
    result = poll_backup(SimpleNamespace(cursor=Cursor), {'backup_date': '2026-10-14'})
    assert result['status'] == 'ambiguous'


def executor():
    return runpy.run_path(str(Path(__file__).parents[1] / 'scripts/gcp/ledger_backup_executor.py'))


def test_vm_worker_without_controller_request_never_runs_backup(monkeypatch):
    import subprocess
    def command(args, **kwargs):
        assert 'psql' in args and 'SKIP LOCKED' in kwargs['input']
        return SimpleNamespace(returncode=0, stdout='')
    monkeypatch.setattr(subprocess, 'run', command)
    assert executor()['run']() == {'status': 'idle'}


def test_vm_timeout_keeps_claim_and_never_blindly_retries(monkeypatch):
    import subprocess
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        if 'psql' in args:
            return SimpleNamespace(returncode=0, stdout='2026-10-14')
        raise subprocess.TimeoutExpired(args, 600)
    monkeypatch.setattr(subprocess, 'run', command)
    assert executor()['run']() == {'status': 'ambiguous', 'backup_date': '2026-10-14'}
    assert len(calls) == 2


def test_vm_worker_rejects_wrong_day_and_secret_payload_without_logging_it(monkeypatch):
    import subprocess
    statements = []
    def command(args, **kwargs):
        if 'psql' in args:
            statements.append(kwargs['input'])
            return SimpleNamespace(returncode=0, stdout='2026-10-14' if len(statements) == 1 else '')
        return SimpleNamespace(returncode=0, stdout='{"backup_id":"2026-10-13","bytes":1024,"sha256":"secret"}')
    monkeypatch.setattr(subprocess, 'run', command)
    result = executor()['run']()
    assert result['status'] == 'failed' and 'secret' not in str(result)
    assert "status='failed'" in statements[-1]


def test_backup_handoff_push_requires_explicit_phase_and_verified_full_release():
    """Existing guarded workflow accepts an owner-approved GitHub request."""
    source = (Path(__file__).parents[1] / '.github/workflows/ledger-backup-controller-dev.yml').read_text()
    assert "ops/ledger-backup-controller-request.json" in source
    assert '.intent == "dev-ledger-backup-handoff" and .approved == true' in source
    assert 'test "$sha" = "$EXPECTED_RELEASE_SHA"' in source
    assert 'gh run view "$RELEASE_RUN" --json headSha,conclusion,status,workflowName' in source
    assert 'git diff --exit-code "$sha" HEAD -- scripts/gcp/ledger_backup_executor.py' in source
    assert "if: steps.request.outputs.phase == 'install'" in source
    assert "if: steps.request.outputs.phase == 'handoff'" in source
    assert "sudo systemctl disable --now janus-ledger-backup.timer" in source
    assert source.index("Restore verified immutable backup") < source.index("Handoff only after executor")
    # gcloud's first-use key generation writes prose to stdout, corrupting JSON receipts.
    assert source.index('ssh-keygen -q') < source.index('>/tmp/backup-receipt.json')


def test_d04_access_preflight_only_tests_permissions_without_granting_them():
    import ast
    import re
    import yaml
    path = Path(__file__).parents[1] / '.github/workflows/d04-backup-access-readback.yml'
    text = path.read_text()
    assert 'testIamPermissions' in text and 'compute.instances.osLogin' in text
    assert 'setIamPolicy' not in text.replace('compute.instances.setIamPolicy', '')
    steps = yaml.safe_load(text)['jobs']['d04-readonly']['steps']
    for step in steps:
        for embedded in re.findall(r"python - <<'PY'\n(.*?)\nPY", step.get('run', ''), re.S):
            ast.parse(embedded)


def test_vm_immutable_daily_collision_and_weekly_monthly_reuse_contract():
    """Same-date objects must match source; later days keep the first period archive."""
    src = (Path(__file__).parents[1] / 'scripts/gcp/ledger-durability-dev.sh').read_text()
    assert 'ifGenerationMatch' in src and '"0"' in src
    assert 'print("EXISTS")' in src and 'print("CREATED")' in src
    assert "open(os.environ['GCS_FILE'], 'wb')" in src  # actual download only
    assert "daily immutable collision or readback mismatch" in src
    assert "existing period archive invalid" in src
    assert 'weekly_state="${period_state}"' in src
    assert 'monthly_state="${period_state}"' in src
    assert 'pg_restore --list' in src
    assert 'cmp "${temporary}/period.dump"' in src
    assert src.index("daily immutable collision or readback mismatch") < src.index('for period in')
