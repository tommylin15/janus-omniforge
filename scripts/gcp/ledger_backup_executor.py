"""Run one controller-requested backup on the existing PostgreSQL VM."""
from datetime import date
import json
import re
import subprocess


def sql(statement):
    result = subprocess.run(
        ['docker', 'exec', '-i', '--user', 'postgres', 'janus-postgres',
         'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-d', 'janus_control'],
        input=statement, text=True, capture_output=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError('backup_request_database_unavailable')
    return result.stdout.strip()


def run():
    # A crashed claim remains running. Do not blindly repeat an unknown backup.
    day = sql("""UPDATE control.ledger_backup_requests SET status='running',started_at=now()
                 WHERE backup_date=(SELECT backup_date FROM control.ledger_backup_requests
                   WHERE status='queued' ORDER BY backup_date FOR UPDATE SKIP LOCKED LIMIT 1)
                 RETURNING backup_date""")
    if not day:
        return {'status': 'idle'}
    date.fromisoformat(day)
    try:
        completed = subprocess.run(
            ['/bin/bash', '/var/lib/janus/ledger-durability', 'vm-backup', day],
            capture_output=True, text=True, timeout=600,
        )
        if completed.returncode:
            raise RuntimeError('backup_executor_failed')
        receipt = json.loads(completed.stdout)
        checksum = str(receipt.get('sha256', '')).removeprefix('sha256:')
        size = receipt.get('bytes')
        if (receipt.get('backup_id') != day or not re.fullmatch('[a-f0-9]{64}', checksum)
                or isinstance(size, bool) or not isinstance(size, int) or size < 1024):
            raise ValueError('invalid_backup_receipt')
        sql(f"""UPDATE control.ledger_backup_requests SET status='succeeded',completed_at=now(),
                 size_bytes={size},sha256='{checksum}' WHERE backup_date='{day}' AND status='running'""")
        return {'status': 'succeeded', 'backup_date': day, 'size_bytes': size, 'sha256': checksum}
    except subprocess.TimeoutExpired:
        # Timeout is not a proven failure. Preserve the claim for operator readback.
        return {'status': 'ambiguous', 'backup_date': day}
    except (RuntimeError, ValueError, KeyError, TypeError):
        sql(f"""UPDATE control.ledger_backup_requests SET status='failed',completed_at=now(),
                 error_code='BACKUP_EXECUTOR_FAILED' WHERE backup_date='{day}' AND status='running'""")
        return {'status': 'failed', 'backup_date': day}


if __name__ == '__main__':
    try:
        print(json.dumps(run(), sort_keys=True))
    except Exception:
        print(json.dumps({'status': 'unavailable', 'error_code': 'BACKUP_EXECUTOR_UNAVAILABLE'}))
        raise SystemExit(1)
