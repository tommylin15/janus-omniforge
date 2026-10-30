from datetime import datetime, timedelta
from io import BytesIO
import json
from unittest.mock import patch

from services.api.intraday_quotes import MisQuotes, TAIPEI, market_phase, value_holdings
from services.api.app import create_app
from fastapi.testclient import TestClient
from tests.test_portfolio_api_completeness import Repository, Store, USER_ID, auth


def test_decimal_values_missing_stale_and_canonical_snapshot_unchanged():
    now = datetime(2026, 10, 1, 10, 0, tzinfo=TAIPEI)
    rows = [{'symbol':'2330', 'currency':'TWD', 'shares':'1234', 'average_cost':'100.25', 'market_price':'90'}]
    quotes = {'2330': {'price':'101.35', 'quote_at':now.isoformat()}}
    result = value_holdings(rows, quotes, now)
    assert result['positions'][0]['unrealized_pnl'] == '1357.40'
    assert result['items'][0]['market_value'] == '125065.90'
    assert rows[0]['market_price'] == '90'
    quotes['2330']['quote_at'] = (now-timedelta(seconds=121)).isoformat()
    stale = value_holdings(rows, quotes, now)['items'][0]
    # Last success remains visible on the holding, but an expired observation
    # must not be presented as a complete, current portfolio total.
    assert stale['market_value'] is None
    assert stale['unrealized_pnl'] is None
    assert stale['aggregate_status'] == 'withheld'
    assert stale['valuation_status'] == 'stale'
    assert stale['priced_market_value'] == '0'
    assert stale['stale_price_count'] == 1
    assert value_holdings(rows, quotes, now)['positions'][0]['price_status'] == 'stale'
    assert value_holdings(rows, {}, now)['positions'][0]['price_status'] == 'missing'
    mixed = rows + [{'symbol':'6488', 'currency':'TWD', 'shares':'1', 'average_cost':'5'}]
    quotes['2330']['quote_at'] = now.isoformat()
    assert value_holdings(mixed, quotes, now)['items'][0]['affected_symbols'] == ['6488']
    assert value_holdings(mixed, quotes, now)['items'][0]['market_value'] is None
    assert value_holdings(rows, quotes, now)['market_open'] is True
    assert value_holdings(rows, quotes, now.replace(hour=14))['market_open'] is False
    assert value_holdings(rows, quotes, now.replace(day=3))['market_open'] is False


def test_mis_verifies_otc_exchange_echo_and_throttles_same_symbols(monkeypatch):
    monkeypatch.setenv('JANUS_MIS_QUOTES_ENABLED','true')
    data = {'rtcode':'0000','msgArray':[
        {'c':'2330','ex':'tse','d':'20261001','t':'10:00:05','z':'-', 'a':'110_',
         'trade':{'z':'101.35','t':'10:00:00'}},
        {'c':'t00','ex':'tse','d':'20261001','t':'10:00:05','z':'23001.25'},
        {'c':'6488','ex':'otc','d':'20261001','t':'10:00:00','z':'200','y':'195'}]}
    identities = {
        '2330':{'market':'TWSE'},
        'TAIEX':{'market':'TWSE_INDEX'},
        '6488':{'market':'TPEX'},
    }
    with patch('services.api.intraday_quotes.urlopen', return_value=BytesIO(json.dumps(data).encode())) as fetch:
        service = MisQuotes()
        first = service.prices(identities)
        second = service.prices(identities)
        assert fetch.call_count == 1
        assert 'tse_2330.tw' in fetch.call_args.args[0].full_url
        assert 'tse_t00.tw' in fetch.call_args.args[0].full_url
        assert 'otc_6488.tw' in fetch.call_args.args[0].full_url
        assert first == second
        assert first['2330']['price'] == '101.35'
        assert first['TAIEX']['price'] == '23001.25'
        assert first['2330']['quote_at'].endswith('10:00:00+08:00')
        assert first['6488']['price'] == '200'
        assert first['6488']['previous_close'] == '195'


def test_market_phase_keeps_post_close_bridge_until_eod_slot():
    assert market_phase(datetime(2026, 10, 6, 9, 0, tzinfo=TAIPEI)) == 'regular'
    assert market_phase(datetime(2026, 10, 6, 13, 29, tzinfo=TAIPEI)) == 'regular'
    assert market_phase(datetime(2026, 10, 6, 13, 30, tzinfo=TAIPEI)) == 'closing_pending_eod'
    assert market_phase(datetime(2026, 10, 6, 14, 29, tzinfo=TAIPEI)) == 'closing_pending_eod'
    assert market_phase(datetime(2026, 10, 6, 14, 30, tzinfo=TAIPEI)) == 'closed'


def test_authenticated_quotes_read_only_owned_snapshot_and_pending_ledger_blocks():
    repository, store = Repository(), Store()
    repository.latest_ledger_version = lambda owner: 7
    repository.positions = lambda owner: [{'symbol':'2330','currency':'TWD','shares':'1','average_cost':'100','ledger_version':7}]
    repository.last_quotes = lambda identities: {'2330': {'price':'123.45','quote_at':datetime.now(TAIPEI).isoformat()}}
    repository.save_last_quotes = lambda rows: None
    class Quotes:
        market_date = '20261009'
        def prices(self, identities):
            assert set(identities) == {'2330'}
            return {'2330': {'price':'123.45','quote_at':datetime.now(TAIPEI).isoformat()}}
    class Calendar:
        def setting(self, key):
            assert key == 'schedule'
            return {'value': {'holiday_overrides': ['2026-10-09']}}
    claims = {'iss':'https://accounts.google.com','aud':'user-client','sub':'google-a',
              'email':'owner@example.com','email_verified':True,'exp':1_900_000_000}
    api = TestClient(create_app(repository,store,lambda _token,_audience: claims,
                               audience='user-client', quotes=Quotes(), admin_service=Calendar()))
    assert api.get('/api/v1/me/portfolio/quotes').status_code == 401
    response = api.get('/api/v1/me/portfolio/quotes',headers=auth())
    assert response.status_code == 200
    assert response.json()['positions'][0]['unrealized_pnl'] == '23.45'
    assert all(owner == USER_ID for _,owner,_ in store.calls)
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 9, 10, tzinfo=tz or TAIPEI)

    with patch('services.api.app.datetime', FixedDateTime):
        holiday = api.get('/api/v1/me/portfolio/quotes', headers=auth())
        assert holiday.status_code == 200
        assert holiday.json()['market_open'] is False
        assert holiday.json()['positions'][0]['market_price'] == '123.45'
    repository.latest_ledger_version = lambda owner: 8
    assert api.get('/api/v1/me/portfolio/quotes',headers=auth()).status_code == 409


def test_manual_owner_quote_refresh_works_during_closing_eod_handoff():
    """13:30-14:30 explicit POST must refresh MIS; GET must not poll."""
    from services.api.app import create_app
    from tests.test_quote_router_broker import QuoteRepository
    from unittest.mock import patch

    now = datetime(2026, 10, 30, 14, 5, tzinfo=TAIPEI)
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz or TAIPEI)

    repo = QuoteRepository()
    class Quotes:
        def __init__(self):
            self.calls = 0
        def prices(self, identities):
            self.calls += 1
            assert set(identities) == {"2330"}
            return {"2330": {
                "price": "102.5",
                "previous_close": "100.0",
                "quote_at": "2026-10-30T13:25:00+08:00",
                "received_at": "2026-10-30T14:05:00+08:00",
            }}

    class Calendar:
        def setting(self, _):
            return {"value": {}}

    source = Quotes()
    claims = {"iss": "https://accounts.google.com", "aud": "user-client", "sub": "google-a",
              "email": "owner@example.com", "email_verified": True, "exp": 1900000000}
    api = TestClient(create_app(repo, Store(), lambda *_: claims, audience="user-client",
                                quotes=source, admin_service=Calendar()))
    with patch("services.api.app.datetime", FrozenDateTime), \
         patch.dict("os.environ", {"JANUS_MIS_QUOTES_ENABLED": "true"}), \
         patch("services.api.quote_router.QuoteRouter.refresh_tpex",
               return_value={"status": "idle", "requested": 0, "updated": 0}) as tpex_calls:
        passive = api.get("/api/v1/me/portfolio/quotes", headers=auth())
        assert passive.status_code == 200
        assert source.calls == 0
        manual = api.post("/api/v1/me/portfolio/quotes/refresh", json={}, headers=auth())
        assert manual.status_code == 200
        assert manual.json()["refresh_status"] == "updated"
        assert manual.json()["positions"][0]["market_price"] == "102.5"
        assert source.calls == 1
        assert manual.json()["positions"][0]["quote_state"] == "closing_pending_eod"
        # Non-force GET is the EOD handoff; manual POST does not serially
        # block on TPEx's pair of 12s official endpoints.
        assert tpex_calls.call_count == 1
        # Repeat manual call within 10-second persistent throttle is a no-op.
        api.post("/api/v1/me/portfolio/quotes/refresh", json={}, headers=auth())
        assert source.calls == 1
        # After 14:30 a late EOD projection must not disable explicit owner
        # refresh. MIS still carries its actual trade date (not a fake EOD).
        now = datetime(2026, 10, 30, 15, 10, tzinfo=TAIPEI)
        late = api.post("/api/v1/me/portfolio/quotes/refresh", json={}, headers=auth())
        assert late.status_code == 200
        assert late.json()["refresh_status"] == "updated"
        assert source.calls == 2
        assert late.json()["positions"][0]["price_date"] == "2026-10-30"
        assert late.json()["positions"][0]["quote_state"] == "closing_pending_eod"
        assert tpex_calls.call_count == 1


def test_owner_off_session_manual_refresh_all_hours_without_background_mis():
    """Early morning, evening, weekend and holidays permit only explicit refresh.

    Last exchange observation can be prior-day: response must not label it as
    today's intraday tick, and must not invent today's price change.
    """
    from unittest.mock import patch
    import pytest
    from tests.test_quote_router_broker import QuoteRepository

    scenarios = [
        ("2026-10-30T06:10:00+08:00", False, "closed"),  # premarket
        ("2026-10-30T08:59:00+08:00", False, "closed"),
        ("2026-10-30T22:15:00+08:00", False, "closed"),  # evening
        ("2026-10-31T11:00:00+08:00", False, "closed"),  # Saturday
        ("2026-11-01T03:05:00+08:00", False, "closed"),  # Sunday night
        ("2026-10-30T10:20:00+08:00", True, "closed"),   # calendar holiday
    ]
    for timestamp, holiday, expected_session in scenarios:
        simulated = datetime.fromisoformat(timestamp)

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return simulated.astimezone(tz or TAIPEI)

        class Source:
            calls = 0

            def prices(self, identities):
                self.calls += 1
                assert set(identities) == {"2330"}
                return {"2330": {
                    "price": "101.25",
                    "previous_close": "101.00",
                    "quote_at": "2026-10-29T13:23:00+08:00",
                }}

        class Calendar:
            def setting(self, name):
                assert name == "schedule"
                return {"value": {"holiday_overrides": ["2026-10-30"] if holiday else []}}

        source = Source()
        claims = {"iss": "https://accounts.google.com", "aud": "user-client",
                  "sub": "google-a", "email": "owner@example.com",
                  "email_verified": True, "exp": 1_900_000_000}
        api = TestClient(create_app(QuoteRepository(), Store(),
                                    lambda *_: claims, audience="user-client",
                                    quotes=source, admin_service=Calendar()))
        with patch("services.api.app.datetime", FrozenDateTime), \
             patch.dict("os.environ", {"JANUS_MIS_QUOTES_ENABLED": "true"}), \
             patch("services.api.quote_router.QuoteRouter.refresh_tpex",
                   return_value={"status": "idle", "requested": 0, "updated": 0}):
            normal = api.get("/api/v1/me/portfolio/quotes", headers=auth())
            assert normal.status_code == 200
            assert normal.json()["session"] == expected_session
            assert normal.json()["market_open"] is False
            assert source.calls == 0, timestamp  # no periodic/off-hours MIS
            assert api.get("/api/v1/me/portfolio/quotes", headers=auth()).status_code == 200
            assert source.calls == 0

            manual = api.post("/api/v1/me/portfolio/quotes/refresh",
                              json={}, headers=auth())
            assert manual.status_code == 200
            assert manual.json()["refresh_status"] == "updated"
            assert source.calls == 1, timestamp
            p = manual.json()["positions"][0]
            assert p["price_date"] == "2026-10-29"
            assert p["quote_state"] == "stale"
            assert p["market_price"] == "101.25"
            assert p["day_change_amount"] is None
            assert manual.json()["market_open"] is False
