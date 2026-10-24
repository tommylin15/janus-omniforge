"""Run one controller-requested backup on the existing PostgreSQL VM."""
from datetime import date
import json
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen


def sql(statement):
    result = subprocess.run(
        ['docker', 'exec', '-i', '--user', 'postgres', 'janus-postgres',
         'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-d', 'janus_control'],
        input=statement, text=True, capture_output=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError('backup_request_database_unavailable')
    return result.stdout.strip()


def retain(day):
    """Backup success and cleanup success are separate durable outcomes."""
    import private_ledger_backup_retention as retention
    try:
        request = json.loads(Path("/var/lib/janus/private-ledger-backup-retention-request.json").read_text())
        token_request = Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"})
        with urlopen(token_request, timeout=10) as response:
            token = json.load(response)["access_token"]
        retention.OUT = Path("/var/lib/janus/private-ledger-backup-retention-receipt.json")
        retention.run(mode="dry-run", request=request, token=token)
        receipt = retention.run(mode="apply", request=request, token=token)
        encoded = json.dumps(receipt, sort_keys=True).replace("'", "''")
        sql(f"""UPDATE control.ledger_backup_requests SET retention_status='succeeded',
                 retention_receipt='{encoded}'::jsonb WHERE backup_date='{day}' AND status='succeeded'""")
        return "succeeded"
    except Exception as error:
        # Never log tokens, private dump contents, or transport error payloads.
        code = type(error).__name__.upper()
        sql(f"""UPDATE control.ledger_backup_requests SET retention_status='failed',
                 retention_receipt=jsonb_build_object('error_code','{code}')
                 WHERE backup_date='{day}' AND status='succeeded'""")
        return "failed"


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

    except subprocess.TimeoutExpired:
        # Timeout is not a proven failure. Preserve the claim for operator readback.
        return {'status': 'ambiguous', 'backup_date': day}
    except (RuntimeError, ValueError, KeyError, TypeError):
        sql(f"""UPDATE control.ledger_backup_requests SET status='failed',completed_at=now(),
                 error_code='BACKUP_EXECUTOR_FAILED' WHERE backup_date='{day}' AND status='running'""")
        return {'status': 'failed', 'backup_date': day}

    return {'status': 'succeeded', 'backup_date': day, 'size_bytes': size, 'sha256': checksum,
            'retention_status': retain(day)}


if __name__ == '__main__':
    try:
        print(json.dumps(run(), sort_keys=True))
    except Exception:
        print(json.dumps({'status': 'unavailable', 'error_code': 'BACKUP_EXECUTOR_UNAVAILABLE'}))
        raise SystemExit(1)
