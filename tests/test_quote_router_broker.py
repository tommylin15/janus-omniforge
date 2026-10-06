from datetime import datetime, timedelta
from uuid import UUID
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.api.app import create_app
from services.api.intraday_quotes import TAIPEI
from services.api.models import BrokerProfileIn
from services.api.quote_router import QuoteRouter
from services.api.repository import PostgresWorkspaceRepository, ConflictError
from tests.test_portfolio_api_completeness import Repository, Store, auth, USER_ID


class QuoteRepository(Repository):
    def __init__(self):
        self.saved = {}
        self.eod = {}

    def positions(self, owner):
        assert owner == USER_ID
        return [{'symbol':'2330','currency':'TWD','shares':'1','average_cost':'100','ledger_version':7}]

    def last_quotes(self, identities):
        return {s: dict(r) for s, r in self.saved.items() if s in identities}

    def save_last_quotes(self, quotes):
        self.saved.update(quotes)

    def eod_quotes(self, identities):
        return {s: dict(r) for s, r in self.eod.items() if s in identities}


def test_last_success_survives_source_failure_and_new_router_instance():
    repository = QuoteRepository()
    at = (datetime.now(TAIPEI) - timedelta(seconds=10)).isoformat()
    class Source:
        fail = False
        def prices(self, identities):
            assert identities == {'2330': {'market': 'TWSE'}}
            if self.fail:
                raise RuntimeError('upstream unavailable')
            return {'2330': {'price': '100.25', 'quote_at': at},
                    '9999': {'price': '999', 'quote_at': at}}
    source = Source()
    identities = {'2330': {'market': 'TWSE'}}
    router = QuoteRouter(repository, source)
    assert router.read(identities) == {}
    router.refresh(identities)
    saved = router.read(identities)
    assert saved['2330']['received_at']
    assert saved['2330']['route_version'] == 'latest-price.v2'
    source.fail = True
    router.refresh(identities)
    assert QuoteRouter(repository, source).read(identities) == saved
    assert '9999' not in repository.saved


def test_router_preserves_actual_source_receipt_time():
    repository = QuoteRepository()
    receipts = []
    class Source:
        def prices(self, _):
            receipt = datetime.now(TAIPEI)
            receipts.append(receipt.isoformat())
            return {'2330': {'price':'100', 'quote_at':(receipt-timedelta(seconds=10)).isoformat(),
                             'received_at':receipt.isoformat()}}
    QuoteRouter(repository, Source()).refresh({'2330': {'market':'TWSE'}})
    assert repository.saved['2330']['received_at'] == receipts[0]


@pytest.mark.parametrize('price,at', [
    ('0', datetime.now(TAIPEI).isoformat()), ('NaN', datetime.now(TAIPEI).isoformat()),
    ('100', (datetime.now(TAIPEI) + timedelta(days=1)).isoformat()),
    ('100', '2026-10-05T10:00:00'), ('100', 'bad'),
])
def test_router_rejects_invalid_trade_without_overwriting_last_success(price, at):
    repository = QuoteRepository()
    repository.saved = {'2330': {'price': '99', 'quote_at': '2026-10-01T10:00:00+08:00'}}
    class Source:
        def prices(self, _): return {'2330': {'price': price, 'quote_at': at}}
    QuoteRouter(repository, Source()).refresh({'2330': {'market':'TWSE'}})
    assert repository.saved['2330']['price'] == '99'


def test_resolver_prefers_same_day_eod_and_uses_persistent_sixty_second_ttl():
    repository = QuoteRepository()
    now = datetime(2026, 10, 6, 10, 0, tzinfo=TAIPEI)
    calls = []
    class Source:
        def prices(self, identities):
            calls.append(tuple(sorted(identities)))
            return {'2330': {'price':'101', 'quote_at':now.isoformat(),
                             'received_at':now.isoformat()}}

    router = QuoteRouter(repository, Source())
    identities = {'2330': {'market':'TWSE', 'enabled':True}}
    prices, refresh = router.resolve(identities, refresh=True, now=now)
    assert refresh == {'status':'updated', 'requested':1, 'updated':1}
    assert prices['2330']['state'] == 'intraday'
    assert prices['2330']['price'] == '101'

    # Under 60 seconds the persisted DB receipt suppresses an upstream fetch.
    prices, refresh = router.resolve(
        identities, refresh=True, now=now + timedelta(seconds=59))
    assert refresh['requested'] == 0
    assert len(calls) == 1

    # A manual refresh has a 10-second hard throttle, not the normal 60-second TTL.
    _, refresh = router.resolve(
        identities, refresh=True, force=True, now=now + timedelta(seconds=11))
    assert refresh['requested'] == 1
    assert len(calls) == 2

    repository.eod['2330'] = {
        'price':'102', 'price_date':'2026-10-06',
        'received_at':'2026-10-06T14:30:00+08:00',
        'source':'core_ohlcv', 'is_final':True,
    }
    final = router.read(identities, now=datetime(2026, 10, 6, 14, 31, tzinfo=TAIPEI))
    assert final['2330']['price'] == '102'
    assert final['2330']['state'] == 'eod_final'
    assert final['2330']['is_final'] is True


def test_router_never_requests_tpex_symbols():
    repository = QuoteRepository()
    class Source:
        def prices(self, identities):
            raise AssertionError('TPEx must never reach MIS')
    result = QuoteRouter(repository, Source()).refresh(
        {'6488': {'market':'TPEX', 'enabled':True}},
        now=datetime(2026, 10, 6, 10, 0, tzinfo=TAIPEI),
    )
    assert result == {'status':'fresh', 'requested':0, 'updated':0}


def test_profile_validation_forbids_owner_override_and_incomplete_cash():
    payload = dict(fee_discount_multiplier='0.6', minimum_fee='20', cash_strategy='balanced', expected_version=0)
    assert BrokerProfileIn(**payload).declared_cash is None
    for extra in ({'user_id': str(USER_ID)}, {'declared_cash': '100'},
                  {'cash_as_of':'2026-10-05'}, {'fee_discount_multiplier':'1.1'}, {'minimum_fee':'-1'}):
        with pytest.raises(ValidationError):
            BrokerProfileIn(**{**payload, **extra})


def test_profile_api_uses_authenticated_owner_and_rejects_unauthenticated_calls():
    class Profiles(QuoteRepository):
        def resolve_user(self, sub, email): return UUID(int=1 if sub == 'a' else 2)
        def broker_profile(self, owner): return {'version':0, 'owner':str(owner)}
        def save_broker_profile(self, owner, value, key): return {'version':1, 'owner':str(owner)}
    def verifier(token, audience):
        return {'iss':'https://accounts.google.com','aud':audience,'sub':token,
                'email':'owner@example.com','email_verified':True,'exp':1900000000}
    api = TestClient(create_app(Profiles(),Store(),verifier,audience='user-client'))
    assert api.get('/api/v1/me/broker-profile').status_code == 401
    a = api.get('/api/v1/me/broker-profile',headers={'Authorization':'Bearer a'}).json()
    b = api.get('/api/v1/me/broker-profile',headers={'Authorization':'Bearer b'}).json()
    assert a['owner'] != b['owner']
    payload = dict(fee_discount_multiplier='0.6',minimum_fee='20',cash_strategy='reserve',expected_version=0)
    assert api.put('/api/v1/me/broker-profile',json=payload,headers=auth()).status_code == 422
    response = api.put('/api/v1/me/broker-profile',json=payload,
        headers={'Authorization':'Bearer a','Idempotency-Key':'profile-1'})
    assert response.status_code == 200
    assert response.json()['owner'] == a['owner']


def test_missing_quote_is_explicit_and_upstream_failure_does_not_fail_db_read():
    repository = QuoteRepository()
    repository.latest_ledger_version = lambda owner: 7
    class Source:
        def prices(self, _): raise RuntimeError('unavailable')
    class Calendar:
        def setting(self, _): return {'value':{}}
    claims = {'iss':'https://accounts.google.com','aud':'user-client','sub':'a',
              'email':'owner@example.com','email_verified':True,'exp':1900000000}
    api = TestClient(create_app(repository,Store(),lambda *_:claims,audience='user-client',
                               quotes=Source(),admin_service=Calendar()))
    response = api.get('/api/v1/me/portfolio/quotes',headers=auth())
    assert response.status_code == 200
    assert response.json()['fallback'] == 'missing'
    assert response.json()['positions'][0]['market_price'] is None
    assert response.json()['items'][0]['aggregate_status'] == 'withheld'
    assert response.json()['refresh_status'] == 'blocked'
    assert api.get('/api/v1/me/portfolio/quotes').status_code == 401


def test_quote_read_does_not_scan_private_mart(monkeypatch):
    repository = QuoteRepository()
    repository.latest_ledger_version = lambda _: 7
    class NoMart:
        def mart(self, *_args, **_kwargs): raise AssertionError('quote path scanned Private Mart')
    claims = {'iss':'https://accounts.google.com','aud':'user-client','sub':'a',
              'email':'owner@example.com','email_verified':True,'exp':1900000000}
    monkeypatch.setenv('JANUS_MIS_QUOTES_ENABLED', 'false')
    api = TestClient(create_app(repository,NoMart(),lambda *_:claims,audience='user-client'))
    assert api.get('/api/v1/me/portfolio/quotes',headers=auth()).status_code == 200


def test_profile_repository_replays_original_revision_and_guards_conflicts():
    rows = []
    class Connection:
        result = None
        def execute(self, sql, params):
            self.result = None
            if 'SELECT user_id FROM private.users' in sql:
                self.result = {'user_id':params[0]}
            elif 'idempotency_key=%s' in sql:
                self.result = next((r for r in rows if r['user_id']==params[0] and r['key']==params[1]), None)
            elif 'MAX(version)' in sql:
                self.result = {'version':max((r['version'] for r in rows if r['user_id']==params[0]),default=0)}
            elif 'INSERT INTO private.broker_profile_revisions' in sql:
                self.result = {'user_id':params[0],'version':params[1],'key':params[-1], 'minimum_fee':params[3]}
                rows.append(self.result)
            return self
        def fetchone(self): return self.result
    repository = PostgresWorkspaceRepository('not-used')
    repository._connection = lambda: nullcontext(Connection())
    repository._next_change_version = lambda *_: 1
    repository._change = lambda *_: None
    payload = dict(fee_discount_multiplier='0.6',minimum_fee='20',cash_strategy='reserve',expected_version=0)
    first = repository.save_broker_profile(USER_ID,BrokerProfileIn(**payload),'first')
    second = repository.save_broker_profile(USER_ID,BrokerProfileIn(**{**payload,'expected_version':1,'minimum_fee':'10'}),'second')
    assert second['version'] == 2
    assert repository.save_broker_profile(USER_ID,BrokerProfileIn(**payload),'first') == first
    with pytest.raises(ConflictError):
        repository.save_broker_profile(USER_ID,BrokerProfileIn(**payload),'third')
    other = UUID(int=2)
    assert repository.save_broker_profile(other,BrokerProfileIn(**payload),'first')['version'] == 1
    assert len(rows) == 3


def test_owner_deletion_clears_profile_before_user_and_keeps_shared_quotes():
    statements = []
    class Connection:
        def execute(self, sql, params):
            statements.append((sql,params))
    repository = PostgresWorkspaceRepository('not-used')
    repository._connection = lambda: nullcontext(Connection())
    repository.complete_deletion(UUID(int=10),USER_ID)
    sql = [s for s,_ in statements]
    assert sql.index('DELETE FROM private.broker_profile_revisions WHERE user_id=%s') < sql.index('DELETE FROM private.users WHERE user_id=%s')
    assert all(params[0] == USER_ID for _,params in statements[:-1])
    assert not any('operational_last_quotes' in s for s in sql)
