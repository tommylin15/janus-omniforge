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
