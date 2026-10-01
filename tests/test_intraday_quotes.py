from datetime import datetime, timedelta
from io import BytesIO
import json
from unittest.mock import patch

from services.api.intraday_quotes import MisQuotes, TAIPEI, value_holdings
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
    assert stale['market_value'] == '125065.90'
    assert stale['unrealized_pnl'] == '1357.40'
    assert stale['aggregate_status'] == 'stale'
    assert stale['stale_price_count'] == 1
    assert value_holdings(rows, quotes, now)['positions'][0]['price_status'] == 'stale'
    assert value_holdings(rows, {}, now)['positions'][0]['price_status'] == 'missing'
    mixed = rows + [{'symbol':'6488', 'currency':'TWD', 'shares':'1', 'average_cost':'5'}]
    quotes['2330']['quote_at'] = now.isoformat()
    assert value_holdings(mixed, quotes, now)['items'][0]['affected_symbols'] == ['6488']
    assert value_holdings(mixed, quotes, now)['items'][0]['market_value'] is None


def test_mis_batches_exchanges_uses_trade_not_asks_and_throttles_manual_clicks(monkeypatch):
    monkeypatch.setenv('JANUS_MIS_QUOTES_ENABLED','true')
    data = {'rtcode':'0000','msgArray':[
        {'c':'2330','ex':'tse','d':'20261001','t':'10:00:05','z':'-', 'a':'110_',
         'trade':{'z':'101.35','t':'10:00:00'}},
        {'c':'6488','ex':'otc','d':'20261001','t':'10:00:00','z':'-', 'b':'200_'}]}
    identities = {'2330':{'market':'TWSE'},'6488':{'market':'TPEx'}}
    with patch('services.api.intraday_quotes.urlopen', return_value=BytesIO(json.dumps(data).encode())) as fetch:
        service = MisQuotes()
        first = service.prices(identities)
        second = service.prices(identities)
        assert fetch.call_count == 1
        assert 'tse_2330.tw' in fetch.call_args.args[0].full_url
        assert 'otc_6488.tw' in fetch.call_args.args[0].full_url
        assert first == second
        assert first['2330']['price'] == '101.35'
        assert first['2330']['quote_at'].endswith('10:00:00+08:00')
        assert '6488' not in first


def test_authenticated_quotes_read_only_owned_snapshot_and_pending_ledger_blocks():
    repository, store = Repository(), Store()
    repository.latest_ledger_version = lambda owner: 7
    class Quotes:
        def prices(self, identities):
            assert set(identities) == {'2330'}
            return {'2330': {'price':'123.45','quote_at':datetime.now(TAIPEI).isoformat()}}
    claims = {'iss':'https://accounts.google.com','aud':'user-client','sub':'google-a',
              'email':'owner@example.com','email_verified':True,'exp':1_900_000_000}
    api = TestClient(create_app(repository,store,lambda _token,_audience: claims,
                               audience='user-client', quotes=Quotes()))
    assert api.get('/api/v1/me/portfolio/quotes').status_code == 401
    response = api.get('/api/v1/me/portfolio/quotes',headers=auth())
    assert response.status_code == 200
    assert response.json()['positions'][0]['unrealized_pnl'] == '23.45'
    assert all(owner == USER_ID for _,owner,_ in store.calls)
    repository.latest_ledger_version = lambda owner: 8
    assert api.get('/api/v1/me/portfolio/quotes',headers=auth()).status_code == 409
