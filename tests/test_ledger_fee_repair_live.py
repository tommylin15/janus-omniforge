from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]/'scripts/gcp'))
import ledger_fee_repair_live as live


def request():
    return dict(intent='checkpoint-bound-owner-fee-repair', approved=True,
                scope='single-real-owner-holding-00719B', mode='preview', source_sha='a'*40,
                image='ghcr.io/tommylin15/janus-private-pipeline@sha256:'+'b'*64,
                configuration_hash='c'*64,
                preview_run='4', preview_effective_events=154, preview_corrections=88,
                release_run='1', rollout_run='2', boundary_run='3', ledger_version=176, profile_version=3)


@pytest.mark.parametrize('key,value', [('approved', False), ('mode', 'retry'), ('ledger_version', True),
    ('profile_version', -1), ('source_sha', 'main'), ('image', 'mutable:latest'), ('rollout_run', 2),
    ('scope', 'all-owners'), ('configuration_hash', '')])
def test_repair_refuses_drift_before_any_runtime_access(key, value):
    value_request = request()
    value_request[key] = value
    with pytest.raises(ValueError, match='request_invalid'):
        live.validate_request(value_request)


def test_request_accepts_only_the_three_bounded_modes():
    for mode in ('preview', 'apply', 'reconcile'):
        value = {**request(), 'mode': mode}
        assert live.validate_request(value) == value
    compile(live.RUNTIME, '<fee-repair-runtime>', 'exec')


def test_apply_requires_a_bounded_successful_preview_request():
    for changed in ({'preview_run': None}, {'preview_corrections': 155}, {'preview_effective_events': True}):
        with pytest.raises(ValueError, match='preview_required'):
            live.validate_request({**request(), 'mode': 'apply', **changed})


def test_runtime_refuses_changed_correction_count_before_any_money_write(monkeypatch):
    from contextlib import nullcontext
    import json
    from packages import postgres_bundle
    from services.api import repository
    from scripts.gcp import ledger_fee_repair
    class Connection:
        def execute(self, statement, *_):
            self.role = 'current_user' in statement
            return self
        def fetchone(self):
            return {'role': 'janus_private_api'}
        def fetchall(self):
            return [{'user_id': 'synthetic-owner'}]
    class Repo:
        def _connection(self):
            return nullcontext(Connection())
        def stock_identities(self, _):
            return {'00719B': {'name': '元大美債1-3', 'market': 'TPEX'}}
    calls = []
    def repair(*_, **options):
        calls.append(options.get('apply', False))
        return {'status': 'preview', 'effective_events': 154, 'corrections': 87}
    monkeypatch.setattr(postgres_bundle, 'load_postgres_bundle', lambda *_: None)
    monkeypatch.setattr(repository, 'PostgresWorkspaceRepository', lambda _: Repo())
    monkeypatch.setattr(ledger_fee_repair, 'repair_owner_fees', repair)
    monkeypatch.setenv('MOBILE_LEDGER_DATABASE_URL', 'test')
    monkeypatch.setenv('JANUS_FEE_REPAIR_CHECKPOINT', json.dumps({**request(), 'mode': 'apply'}))
    with pytest.raises(RuntimeError, match='preview_counts_changed'):
        exec(live.RUNTIME, {})
    assert calls == [False]


def test_failed_release_cannot_dispatch_a_private_job(monkeypatch, tmp_path):
    import json
    path = tmp_path/'request.json'
    path.write_text(json.dumps(request()))
    monkeypatch.setenv('GITHUB_REF', 'refs/heads/main')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'tommylin15/janus-omniforge')
    monkeypatch.setattr(sys, 'argv', ['repair', '--request', str(path), '--receipt', str(tmp_path/'receipt.json')])
    monkeypatch.setattr(live.jobs, 'automated_oauth_acceptance', lambda *_: None)
    monkeypatch.setattr(live.jobs, 'command', lambda *_: json.dumps({'status': 'completed', 'conclusion': 'failure'}))
    monkeypatch.setattr(live.jobs, 'cloud', lambda *_: pytest.fail('must not dispatch'))
    with pytest.raises(ValueError, match='provenance_incomplete'):
        live.main()


@pytest.mark.parametrize('failed', [False, True])
def test_execution_failure_retains_lease_and_success_releases_it(monkeypatch, tmp_path, failed):
    import json
    value = request()
    path = tmp_path/'request.json'
    path.write_text(json.dumps(value))
    monkeypatch.setenv('GITHUB_REF', 'refs/heads/main')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'tommylin15/janus-omniforge')
    monkeypatch.setattr(sys, 'argv', ['repair', '--request', str(path), '--receipt', str(tmp_path/'receipt.json')])
    monkeypatch.setattr(live.jobs, 'automated_oauth_acceptance', lambda *_: None)
    commands = []
    def command(args):
        commands.append(args)
        if args[:3] == ['gh', 'run', 'view']:
            return json.dumps(dict(status='completed', conclusion='success', headSha='a'*40,
                workflowName='Janus GHCR full-test image publication' if args[3]=='1' else 'Janus GHCR controlled Jobs rollout'))
        if args[0]=='git':
            return json.dumps({'sha': 'a'*40})
        if args[0]=='skopeo':
            return json.dumps({'Labels': {'org.opencontainers.image.revision': 'a'*40}})
        return ''
    monkeypatch.setattr(live.jobs, 'command', command)
    data = {'etag': 'fixed', 'template': {'template': {'containers': [{}]}}}
    monkeypatch.setattr(live.jobs, 'checked_image', lambda *_: data)
    monkeypatch.setattr(live.jobs, 'fingerprint', lambda *_: 'c'*64)
    monkeypatch.setattr(live.jobs, 'fence', lambda: None)
    monkeypatch.setattr(live.jobs, 'terminal', lambda _: True)
    monkeypatch.setattr(live.jobs, 'cloud', lambda *_: dict(name=live.jobs.ROOT+'/operations/fixed', done=True,
        **({'error': {'code': 1}} if failed else {'response': {'name': 'verified', 'succeededCount': 1}})))
    if failed:
        with pytest.raises(RuntimeError, match='inspect_before_retry'):
            live.main()
    else:
        live.main()
    assert (live.jobs.LEASE+['acquire']) in commands
    assert ((live.jobs.LEASE+['release', '--safe-to-release']) in commands) is (not failed)
