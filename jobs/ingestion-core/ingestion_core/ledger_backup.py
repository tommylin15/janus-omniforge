"""Controller-owned requests for the existing PostgreSQL VM backup executor."""
from datetime import datetime, timedelta
import json
import os
import re
from zoneinfo import ZoneInfo

BACKUP_BUCKET = "gen-lang-client-0593591102-dev-private"
BACKUP_PREFIX = "pilot-ledger-backups/daily/"
BACKUP_KEEP_DAYS = 7


def request_backup(connection, state):
    day = datetime.fromisoformat(state['scheduled_at']).astimezone(ZoneInfo('Asia/Taipei')).date()
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("INSERT INTO control.ledger_backup_requests(backup_date,status) VALUES (%s,'queued') ON CONFLICT DO NOTHING", (day,))
    return {**state, 'status': 'running', 'executor': 'existing_postgres_vm', 'backup_date': day.isoformat()}


def poll_backup(connection, state):
    with connection.cursor() as cursor:
        cursor.execute('SELECT status,size_bytes,sha256,completed_at,error_code FROM control.ledger_backup_requests WHERE backup_date=%s', (state['backup_date'],))
        row = cursor.fetchone()
    if row is None:
        return {**state, 'status': 'ambiguous', 'reason': 'backup_request_missing'}
    status, size, checksum, completed, error = row
    if status == 'succeeded':
        if size is None or size < 1024 or not checksum or len(checksum) != 64 or completed is None:
            raise ValueError('invalid completed backup receipt')
        # Confirmation is read-only: never couple the Controller occurrence
        # transition to GCS retention inventory/deletion permissions. A storage
        # failure used to leave completed VM backups stuck in 'running'.
        # Backup retention is a separate guarded operation, not a poll side effect.
        return {**state, 'status': 'succeeded', 'size_bytes': size, 'sha256': checksum,
                'completion_time': completed.isoformat(),
                'retention_cleanup': {'status': 'not_run_in_reconcile'}}
    if status == 'failed':
        return {**state, 'status': 'failed', 'reason': 'backup_executor_failed'}
    return {**state, 'status': 'running', 'backup_status': status}


def cleanup_old_backups(storage_client=None):
    """Remove daily backups older than BACKUP_KEEP_DAYS, keeping at least 3."""
    if storage_client is None:
        from google.cloud import storage
        storage_client = storage.Client(project=os.environ.get("GCP_PROJECT_ID", "gen-lang-client-0593591102"))
    
    bucket = storage_client.bucket(BACKUP_BUCKET)
    
    # List all daily backups
    blobs = list(bucket.list_blobs(prefix=BACKUP_PREFIX))
    pattern = re.compile(r'^pilot-ledger-backups/daily/(\d{4}-\d{2}-\d{2})\.dump$')
    
    backups = []
    for blob in blobs:
        match = pattern.match(blob.name)
        if match:
            backups.append((match.group(1), blob))
    
    if len(backups) <= 3:
        return {"status": "skipped", "reason": "minimum_retention", "count": len(backups)}
    
    # Sort by date descending
    backups.sort(key=lambda x: x[0], reverse=True)
    
    # Keep the newest BACKUP_KEEP_DAYS, but always keep at least 3
    keep_count = max(BACKUP_KEEP_DAYS, 3)
    to_delete = backups[keep_count:]
    
    deleted = []
    for date_str, blob in to_delete:
        try:
            blob.delete()
            deleted.append(date_str)
        except Exception:
            pass  # Ignore deletion failures, will retry next cycle
    
    return {
        "status": "completed",
        "kept": len(backups) - len(deleted),
        "deleted": deleted,
        "policy_days": BACKUP_KEEP_DAYS,
    }
