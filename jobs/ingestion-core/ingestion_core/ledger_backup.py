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
        cursor.execute('SELECT status,size_bytes,sha256,completed_at,error_code,retention_status FROM control.ledger_backup_requests WHERE backup_date=%s', (state['backup_date'],))
        row = cursor.fetchone()
    if row is None:
        return {**state, 'status': 'ambiguous', 'reason': 'backup_request_missing'}
    status, size, checksum, completed, error, retention_status = row
    if status == 'succeeded':
        if size is None or size < 1024 or not checksum or len(checksum) != 64 or completed is None:
            raise ValueError('invalid completed backup receipt')
        # Confirmation is read-only: never couple the Controller occurrence
        # transition to GCS retention inventory/deletion permissions. A storage
        # failure used to leave completed VM backups stuck in 'running'.
        # Backup retention is a separate guarded operation, not a poll side effect.
        return {**state, 'status': ('running' if retention_status == 'pending' else
                                  'succeeded' if retention_status == 'succeeded' else 'failed'),
                'backup_status': 'succeeded',
                'reason': 'backup_retention_' + retention_status, 'size_bytes': size, 'sha256': checksum,
                'completion_time': completed.isoformat(),
                'retention_cleanup': {'status': retention_status, 'executor': 'existing_postgres_vm'}}
    if status == 'failed':
        return {**state, 'status': 'failed', 'reason': 'backup_executor_failed'}
    return {**state, 'status': 'running', 'backup_status': status}

