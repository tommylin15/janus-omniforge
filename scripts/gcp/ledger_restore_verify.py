"""Restore a private backup into a disposable database on the existing dev VM."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import uuid4

CHECKS = """SELECT json_build_object(
 'owners',(SELECT count(*) FROM private.users),
 'ledger_events',(SELECT count(*) FROM private.ledger_events),
 'owner_boundary_valid',NOT EXISTS(
   SELECT 1 FROM private.ledger_events e LEFT JOIN private.users u USING(user_id) WHERE u.user_id IS NULL),
 'latest_versions_valid',NOT EXISTS(
   SELECT 1 FROM private.users u WHERE u.ledger_version <>
     COALESCE((SELECT max(e.ledger_version) FROM private.ledger_events e WHERE e.user_id=u.user_id),0)),
 'correction_links_valid',NOT EXISTS(
   SELECT 1 FROM private.ledger_events e LEFT JOIN private.ledger_events original
     ON original.event_id=COALESCE(e.reverses_event_id,e.replaces_event_id)
   WHERE e.event_action<>'ORIGINAL' AND (original.event_id IS NULL OR original.user_id<>e.user_id))
);"""


def command(args, *, stdin=None, timeout=30):
    result = subprocess.run(['docker', 'exec', '-i', '--user', 'postgres', 'janus-postgres', *args],
                            stdin=stdin, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('isolated_restore_'+args[0]+'_failed')
    return result.stdout.strip()


def verify(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 1024:
        raise ValueError('bounded_backup_file_required')
    database = 'janus_restore_verify_'+uuid4().hex
    if not re.fullmatch(r'janus_restore_verify_[0-9a-f]{32}', database):
        raise ValueError('isolated_database_name_invalid')
    source_size = int(command(['psql', '-XqAt', '-U', 'postgres', '-d', 'janus_control', '-c',
                               'SELECT pg_database_size(current_database())']))
    if shutil.disk_usage('/var/lib/janus').free < source_size*2+128*1024*1024:
        raise RuntimeError('isolated_restore_insufficient_disk')
    created = False
    try:
        command(['createdb', '-U', 'postgres', '-T', 'template0', '--', database])
        created = True
        command(['psql', '-XqAt', '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1',
                 '-c', f'REVOKE ALL ON DATABASE {database} FROM PUBLIC'])
        with path.open('rb') as stream:
            command(['pg_restore', '--single-transaction', '--exit-on-error', '--no-owner', '--no-acl',
                     '-U', 'postgres', '-d', database], stdin=stream, timeout=600)
        result = json.loads(command(['psql', '-XqAt', '-U', 'postgres', '-d', database,
                                     '-v', 'ON_ERROR_STOP=1', '-c', CHECKS]))
        if (not all(result.get(key) is True for key in
                    ('owner_boundary_valid', 'latest_versions_valid', 'correction_links_valid'))
                or result.get('owners', 0) < 1 or result.get('ledger_events', 0) < 1):
            raise RuntimeError('isolated_restore_integrity_failed')
        return {'restore': 'PASS', 'checks': result, 'original_database_unchanged': True}
    finally:
        if created:
            command(['dropdb', '--if-exists', '--force', '-U', 'postgres', '--', database])


if __name__ == '__main__':
    try:
        print(json.dumps(verify(sys.argv[1]), sort_keys=True))
    except Exception as error:
        print(json.dumps({'restore': 'FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(1)
