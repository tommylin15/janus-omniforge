import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

MODULE = Path(__file__).parents[1]/'scripts/gcp/ledger_restore_verify.py'


@pytest.mark.parametrize('failure', [None, 'restore', 'checks', 'create'])
def test_restore_never_writes_original_database_and_cleans_its_own_copy(tmp_path, monkeypatch, failure):
    module = runpy.run_path(str(MODULE))
    backup = tmp_path/'ledger.dump'
    backup.write_bytes(b'x'*1024)
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        if args[0]=='createdb' and failure=='create':
            raise RuntimeError('create_failed')
        if args[0]=='pg_restore':
            assert kwargs['stdin'].read(1)==b'x'
            if failure=='restore':
                raise RuntimeError('restore_failed')
        if args[-1].startswith('SELECT pg_database_size'):
            return '1024'
        if args[-1]==module['CHECKS']:
            return json.dumps(dict(owners=1, ledger_events=352, owner_boundary_valid=True,
                latest_versions_valid=True, correction_links_valid=failure!='checks'))
        return ''
    module['verify'].__globals__['command'] = command
    monkeypatch.setattr(module['shutil'], 'disk_usage', lambda _: SimpleNamespace(free=10**9))
    if failure:
        with pytest.raises(RuntimeError):
            module['verify'](backup)
    else:
        assert module['verify'](backup)['restore']=='PASS'
    for args in calls:
        if args[0] in {'createdb', 'dropdb'}:
            assert args[-1].startswith('janus_restore_verify_') and len(args[-1])==53
        if '-d' in args and args[args.index('-d')+1]=='janus_control':
            assert args[-1]=='SELECT pg_database_size(current_database())'
    assert any(args[0]=='dropdb' for args in calls) is (failure!='create')
    assert any('REVOKE ALL ON DATABASE' in args[-1] for args in calls) is (failure!='create')


def test_invalid_name_or_small_backup_never_creates_database(tmp_path):
    module = runpy.run_path(str(MODULE))
    backup = tmp_path/'ledger.dump'
    backup.write_bytes(b'x')
    with pytest.raises(ValueError, match='backup_file_required'):
        module['verify'](backup)
    backup.write_bytes(b'x'*1024)
    module['verify'].__globals__['uuid4'] = lambda: SimpleNamespace(hex='janus_control')
    with pytest.raises(ValueError, match='database_name_invalid'):
        module['verify'](backup)


def test_command_failure_never_exposes_raw_database_error(monkeypatch):
    module = runpy.run_path(str(MODULE))
    monkeypatch.setattr(module['subprocess'], 'run', lambda *_, **__: SimpleNamespace(
        returncode=1, stdout='private payload', stderr='secret credential'))
    with pytest.raises(RuntimeError) as error:
        module['command'](['pg_restore'])
    assert str(error.value)=='isolated_restore_pg_restore_failed'
