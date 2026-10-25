from uuid import UUID
import pytest

from fastapi.testclient import TestClient

from services.api.app import create_app
from services.api.analysis import CEOProfileIn

OWNER_A = UUID('00000000-0000-0000-0000-000000000001')
OWNER_B = UUID('00000000-0000-0000-0000-000000000002')
REQUEST = UUID('00000000-0000-0000-0000-000000000003')


def test_profiles_reject_paid_models_and_duplicate_provider_routes():
    from packages.analysis_models import DEFAULT_MODELS
    for change in ({'models': {**DEFAULT_MODELS, 'openrouter': 'paid/model'}},
                   {'providers': ['codex_cli', 'codex_cli', 'gemini']}):
        with pytest.raises(ValueError):
            CEOProfileIn(approved=True, expected_version=1, reason='test', **change)


def test_ceo_quota_50_is_allowed_and_51_rejected():
    from services.api.analysis import CEOCapabilityIn
    value = dict(email='owner@example.com', enabled=True, daily_quota=50,
                 cooldown_seconds=300, expected_version=0, reason='owner approval')
    assert CEOCapabilityIn(**value).daily_quota == 50
    with pytest.raises(ValueError):
        CEOCapabilityIn(**{**value, 'daily_quota': 51})



class Repository:
    def resolve_user(self, sub, email): return OWNER_A if sub == 'a' else OWNER_B


class Public:
    def require_enabled_symbol(self, symbol): return symbol.upper()


class Service:
    def __init__(self): self.calls = []
    def baseline(self, symbol, execution_id=None):
        self.calls.append(('baseline', symbol, execution_id))
        return {'symbol': symbol, 'data_status': 'waiting', 'specialists': []}
    def capability(self, owner): return {'can_request': False}
    def changes(self, symbol, session):
        self.calls.append(('changes', symbol, session))
        return {'symbol': symbol, 'observations': []}
    def today_changes(self, owner, session):
        self.calls.append(('today_changes', owner, session))
        return {'items': []}
    def history(self, owner, symbol, limit):
        self.calls.append(('history', owner, symbol, limit))
        return []
    def enqueue(self, owner, symbol, profile, key):
        self.calls.append(('enqueue', owner, symbol, profile, key))
        return {'request_id': str(REQUEST), 'status': 'QUEUED'}
    def request_status(self, owner, request):
        self.calls.append(('status', owner, request))
        if owner != OWNER_A:
            from services.api.repository import NotFoundError
            raise NotFoundError('analysis request not found')
        return {'status': 'RUNNING'}
    def cancel(self, owner, request):
        self.calls.append(('cancel', owner, request))
        return {'status': 'CANCEL_REQUESTED'}
    def reconcile(self, owner, request):
        self.calls.append(('reconcile', owner, request))
        return self.request_status(owner, request)
    def admin_summary(self): return {'profiles': []}
    def save_capability(self, value, actor):
        self.calls.append(('grant', value, actor))
        return {'version': 1}


def client():
    service = Service()
    def verify(token, audience):
        return {'iss': 'https://accounts.google.com', 'aud': audience, 'sub': token,
            'email': 'admin@example.com' if token == 'admin' else f'{token}@example.com',
            'email_verified': True, 'exp': 1_900_000_000}
    api = create_app(repository=Repository(), store=object(), public=Public(), core=object(),
        verifier=verify, audience='user', admin_verifier=verify, admin_audience='admin',
        admin_emails=frozenset({'admin@example.com'}), private_recalculator=object(), analysis_service=service)
    return TestClient(api), service


def auth(token='a'): return {'Authorization': 'Bearer '+token, 'Idempotency-Key': 'same-request-1'}


def test_reads_never_dispatch_and_requests_require_verified_owner():
    api, service = client()
    assert api.get('/api/v1/me/analysis/2330').status_code == 401
    assert api.get('/api/v1/me/analysis/2330', headers=auth()).status_code == 200
    assert api.get('/api/v1/me/analysis/2330/ceo?owner_id=other', headers=auth()).status_code == 200
    assert all(call[0] != 'enqueue' for call in service.calls)
    assert service.calls[-1] == ('history', OWNER_A, '2330', 10)
    result = api.post('/api/v1/me/analysis/2330/ceo', headers=auth(), json={'profile_id': 'default'})
    assert result.status_code == 202
    assert service.calls[-1] == ('enqueue', OWNER_A, '2330', 'default', 'same-request-1')


def test_post_cannot_supply_owner_route_or_provider_and_requires_idempotency():
    api, service = client()
    for field in ('user_id', 'owner_id', 'route', 'provider'):
        assert api.post('/api/v1/me/analysis/2330/ceo', headers=auth(),
            json={'profile_id': 'default', field: 'attacker'}).status_code == 422
    assert api.post('/api/v1/me/analysis/2330/ceo', headers={'Authorization': 'Bearer a'}, json={}).status_code == 422
    assert service.calls == []


def test_request_history_status_and_cancel_scope_to_token_owner():
    api, service = client()
    assert api.get(f'/api/v1/me/ceo-requests/{REQUEST}', headers=auth('b')).status_code == 404
    assert api.post(f'/api/v1/me/ceo-requests/{REQUEST}/reconcile', headers=auth('b'), json={}).status_code == 404
    assert api.post(f'/api/v1/me/ceo-requests/{REQUEST}/cancel', headers=auth()).status_code == 200
    assert service.calls[-1] == ('cancel', OWNER_A, REQUEST)


def test_admin_capability_mutation_is_separate_from_user_auth():
    api, service = client()
    payload = {'email': 'a@example.com', 'enabled': True, 'daily_quota': 3,
               'cooldown_seconds': 300, 'expected_version': 0, 'reason': 'explicit grant'}
    assert api.put('/api/v1/admin/analysis/capability', headers=auth(), json=payload).status_code == 403
    assert service.calls == []
    assert api.put('/api/v1/admin/analysis/capability', headers=auth('admin'), json=payload).status_code == 200
    assert service.calls[-1][-1] == 'admin@example.com'


def test_change_reads_bind_owner_and_validate_session_without_dispatch():
    api, service = client()
    assert api.get('/api/v1/me/today-changes').status_code == 401
    assert api.get('/api/v1/me/analysis/2330/changes').status_code == 401
    assert api.get('/api/v1/me/today-changes?owner_id=b&session=premarket', headers=auth()).status_code == 200
    assert service.calls[-1] == ('today_changes', OWNER_A, 'premarket')
    assert api.get('/api/v1/me/analysis/2330/changes', headers=auth()).status_code == 200
    assert service.calls[-1] == ('changes', '2330', 'postmarket')
    assert api.get('/api/v1/me/today-changes?session=intraday', headers=auth()).status_code == 422


def test_seq05_valuation_reference_requires_authenticated_read_only_fact_pack():
    api, service = client()
    route = '/api/v1/me/analysis/2330/valuation-reference'
    assert api.get(route).status_code == 401
    response = api.get(route, headers=auth())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "missing"
    assert payload["excluded_reasons"] == ["valuation_reference_not_published"]
    assert payload["lower"] is payload["mid"] is payload["upper"] is None
    assert service.calls == [('baseline', '2330', None)]
