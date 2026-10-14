"""Controller-owned requests for the existing PostgreSQL VM backup executor."""
from datetime import datetime
from zoneinfo import ZoneInfo


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
        return {**state, 'status': 'succeeded', 'size_bytes': size, 'sha256': checksum,
                'completion_time': completed.isoformat()}
    if status == 'failed':
        return {**state, 'status': 'failed', 'reason': 'backup_executor_failed'}
    return {**state, 'status': 'running', 'backup_status': status}
