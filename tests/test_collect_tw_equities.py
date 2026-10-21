import gzip
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from research.colab.collect_tw_equities import (
    company_universe, parse_twse, parse_tpex, months_between, month_days,
    collect_chunk, finalize_month, digest, json_bytes, read_chunk,
    is_scheduled_closure,
)


def roster():
    return {'2330': {'symbol': '2330', 'market': 'twse', 'name': '台積電'},
            '0062': {'symbol': '0062', 'market': 'twse', 'name': 'ETF測試'}}


def test_company_master_excludes_etf_etn_foreign_nonstock_codes():
    rows = [{'公司代號': '2330', '公司名稱': '台積電'},
            {'公司代號': '0050', '公司名稱': 'ETF基金'},
            {'公司代號': '03001', '公司名稱': '權證'},
            {'公司代號': '9900', '公司名稱': '認購特別股'}]
    assert list(company_universe(rows, 'twse')) == ['2330']
    otc = [{'SecuritiesCompanyCode': '6488', 'CompanyName': '環球晶'},
           {'SecuritiesCompanyCode': '0098', 'CompanyName': 'ETN'}]
    assert list(company_universe(otc, 'tpex')) == ['6488']


def test_twse_table_by_field_name_not_magic_table_number():
    payload = {'stat': 'OK', 'tables': [{
        'fields': ['名稱', '交易統計'], 'data': []
    }, {
        'fields': ['證券代號', '證券名稱', '成交股數', '成交筆數', '成交金額',
                   '開盤價', '最高價', '最低價', '收盤價'],
        'data': [['2330', '台積電', '1,200', '10', '600,000', '500', '510', '490', '505'],
                 ['0050', '台灣50', '3,000', '10', '50,000', '50', '51', '49', '50']]}
    ]}
    bars = parse_twse(payload, date(2026, 10, 19), {'2330': roster()['2330']}, '2026-10-20T00:00:00Z')
    assert len(bars) == 1
    assert bars[0]['symbol'] == '2330'
    assert bars[0]['volume'] == 1200
    assert bars[0]['close'] == 505


def test_tpex_legacy_table_uses_official_layout_only_whitelisted():
    payload = {'tables': [{'data': [
        ['6488', '環球晶', '355', '+1', '352', '356', '349', '', '2,500', '887,500', '40'],
        ['0088', 'ETF', '10', '0', '9', '11', '8', '', '900', '9,000', '4'],
    ]}]}
    bars = parse_tpex(payload, date(2026, 10, 19), {'6488': {}}, 'now')
    assert len(bars) == 1
    assert bars[0]['close'] == 355
    assert bars[0]['volume'] == 2500


def test_parser_refuses_schema_silent_success():
    with pytest.raises(ValueError, match='equity table missing'):
        parse_twse({'stat': 'OK', 'tables': []}, date(2026, 10, 19), {'2330': {}}, 'now')
    with pytest.raises(ValueError, match='data table missing'):
        parse_tpex({'stat': 'OK'}, date(2026, 10, 19), {'6488': {}}, 'now')


def test_calendar_months_and_weekends():
    assert months_between('2026-09', '2026-10') == ['2026-09', '2026-10']
    assert all(day.weekday() < 5 for day in month_days('2026-10', date(2026, 10, 5)))
    with pytest.raises(ValueError):
        months_between('2026-10', '2025-01')


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, url, params, timeout, headers):
        self.calls += 1
        payload = self.payload
        class R:
            status_code = 200
            content = json.dumps(payload).encode()
            def raise_for_status(self):
                pass
            def json(self):
                return payload
        return R()


def test_chunk_restart_no_rerequest_and_pins_universe(tmp_path):
    payload = {'tables': [{'fields': ['證券代號','證券名稱','成交股數','成交筆數','成交金額',
                                     '開盤價','最高價','最低價','收盤價'],
                            'data': [['2330','台積電','100','2','500','5','6','4','5']]}]}
    session = FakeSession(payload)
    path = tmp_path/'chunks'/'twse-000.json.gz'
    dates = [date(2026, 10, 19)]
    budget = [1]
    assert collect_chunk(session, 'twse', dates, {'2330': {}}, 'expected', path,
                         min_interval=0, request_budget=budget)
    assert session.calls == 1 and budget[0] == 0
    assert collect_chunk(session, 'twse', dates, {'2330': {}}, 'expected', path,
                         min_interval=0, request_budget=budget)
    assert session.calls == 1
    with pytest.raises(ValueError, match='universe/schema'):
        read_chunk(path, 'other')


def test_month_folder_gzip_sha_and_immutable(tmp_path):
    month = '2026-10'
    day = date(2026, 10, 19)
    universe = {'twse': {'2330': {'symbol':'2330','market':'twse','name':'台積電'}},
                'tpex': {'6488': {'symbol':'6488','market':'tpex','name':'環球晶'}}}
    for market, symbol in (('twse', '2330'), ('tpex', '6488')):
        path = tmp_path/month/'_checkpoint'/'r1'/f'{market}-000.json.gz'
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {'schema_version': 1, 'universe_hash': 'abc', 'market': market,
                'days': [{'day': day.isoformat(), 'status': 'COLLECTED', 'sha256': 'xy'}],
                'rows': [{'symbol': symbol, 'market': market, 'trade_date': day.isoformat(),
                          'open': 100, 'high': 101, 'low': 99, 'close': 100,
                          'volume': 1000, 'turnover': 100000, 'source': 'official',
                          'observed_at': 'now'}]}
        path.write_bytes(gzip.compress(json_bytes(data), mtime=0))
    hashes = {'universe': 'abc', 'captured_at': 'now'}
    result = finalize_month(tmp_path, month, 'r1', [day], universe, hashes)
    assert result['status'] == 'PROBE_ARCHIVED'
    folder = tmp_path / month
    manifest = json.loads((folder/'manifest-r1.json').read_text())
    for fname, h in manifest['sha256'].items():
        assert digest((folder / fname).read_bytes()) == h
    assert json.loads((folder/'quality-r1.json').read_text())['research_70pct_certified'] is False
    assert finalize_month(tmp_path, month, 'r1', [day], universe, hashes)['status'] == 'ALREADY_ARCHIVED'
    (folder/'ohlcv-r1.csv.gz').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='corrupted'):
        finalize_month(tmp_path, month, 'r1', [day], universe, hashes)


def test_incomplete_month_is_partial_not_pass(tmp_path):
    a = finalize_month(tmp_path, '2026-10', 'r1', [date(2026, 10, 19)],
                       {'twse': {}, 'tpex': {}}, {'universe': 'hash', 'captured_at': 'now'})
    assert a['status'] == 'PARTIAL' and a['pending_chunks'] == 2


def test_risk_folder_reader_accepts_verified_month_and_rejects_corruption(tmp_path):
    from research.colab.monthly_folder_io import load_monthly_folders
    day = date(2026, 10, 19)
    roster = {'twse': {'2330': {'symbol':'2330','market':'twse','name':'台積電'}},
              'tpex': {'6488': {'symbol':'6488','market':'tpex','name':'環球晶'}}}
    for market, symbol in [('twse','2330'), ('tpex','6488')]:
        folder = tmp_path/'2026-10'/'_checkpoint'/'r1'
        folder.mkdir(parents=True, exist_ok=True)
        d = {'schema_version': 1, 'universe_hash': 'H', 'market': market,
             'days': [{'day': day.isoformat(), 'status':'COLLECTED','sha256':'x'}],
             'rows': [{'symbol': symbol, 'market': market, 'trade_date': day.isoformat(),
                       'open': 5, 'high': 6, 'low': 4, 'close': 5, 'volume': 100,
                       'turnover': 500, 'source': 'test', 'observed_at': 'now'}]}
        (folder/f'{market}-000.json.gz').write_bytes(gzip.compress(json_bytes(d), mtime=0))
    finalize_month(tmp_path, '2026-10', 'r1', [day], roster, {'universe':'H','captured_at':'now'})
    combined, source = load_monthly_folders([tmp_path/'2026-10'])
    assert len(combined) == 2 and source[0]['quality_status'] == 'PROBE'
    (tmp_path/'2026-10'/'ohlcv-r1.csv.gz').write_bytes(b'bad')
    with pytest.raises(ValueError, match='SHA256 mismatch'):
        load_monthly_folders([tmp_path/'2026-10'])

def test_2025_new_year_closure_does_not_fetch_or_consume_budget(tmp_path):
    """Regression for real Colab traceback: TPEx 2025-01-01."""
    payload = {'tables': [{'data': [
        ['6488', '環球晶', '355', '+1', '352', '356', '349', '', '2,500', '887,500', '40'],
    ]}]}
    session = FakeSession(payload)
    path = tmp_path/'tpex-000.json.gz'
    budget = [1]
    dates = [date(2025, 1, 1), date(2025, 1, 2)]
    assert is_scheduled_closure(dates[0])
    assert not is_scheduled_closure(dates[1])
    assert collect_chunk(session, 'tpex', dates, {'6488': {}}, 'u1', path,
                         min_interval=0, request_budget=budget)
    assert session.calls == 1 and budget == [0]
    chunk = read_chunk(path, 'u1')
    assert [s['status'] for s in chunk['days']] == ['SCHEDULED_CLOSURE', 'COLLECTED']
    assert chunk['days'][0]['calendar_source'].startswith('TWSE:')
    assert [r['trade_date'] for r in chunk['rows']] == ['2025-01-02']
    assert collect_chunk(session, 'tpex', dates, {'6488': {}}, 'u1', path,
                         min_interval=0, request_budget=budget)
    assert session.calls == 1


def test_2026_typhoon_closure_resumes_without_fetch_or_budget(tmp_path):
    """Both exchanges were closed 2026-07-10 due to Typhoon Bavi."""
    shutdown = date(2026, 7, 10)
    assert is_scheduled_closure(shutdown)
    assert not is_scheduled_closure(date(2026, 7, 13))
    for market in ('twse', 'tpex'):
        session = FakeSession({'tables': [{'data': []}]})
        path = tmp_path / f'{market}-typhoon.json.gz'
        budget = [0]
        assert collect_chunk(session, market, [shutdown], {'6488': {}},
                             'typhoon-evidence', path, min_interval=0, request_budget=budget)
        saved = read_chunk(path, 'typhoon-evidence')
        assert saved['rows'] == []
        assert saved['days'][0]['status'] == 'SCHEDULED_CLOSURE'
        assert '2026-07-09_typhoon_Bavi' in saved['days'][0]['calendar_source']
        assert 'cna.com.tw/news/afe/202607090360.aspx' in saved['days'][0]['calendar_source']
        assert session.calls == 0 and budget == [0]
        # Re-running a saved day is idempotent; it never fetches or rewrites data.
        assert collect_chunk(session, market, [shutdown], {'6488': {}},
                             'typhoon-evidence', path, min_interval=0, request_budget=budget)
        assert session.calls == 0


def test_holiday_only_chunk_with_no_budget_still_checkpoints(tmp_path):
    session = FakeSession({'unexpected': True})
    path = tmp_path/'new-year-2026.json.gz'
    assert collect_chunk(session, 'twse', [date(2026, 1, 1)],
                         {'2330': {}}, 'u2', path, min_interval=0, request_budget=[0])
    assert session.calls == 0
    saved = read_chunk(path, 'u2')
    assert saved['rows'] == [] and saved['days'][0]['status'] == 'SCHEDULED_CLOSURE'


def test_exchange_settlement_only_days_are_not_trading_days():
    assert all(is_scheduled_closure(date(2025, 1, d)) for d in (23, 24, 27, 28, 29, 30, 31))
    assert all(is_scheduled_closure(date(2026, 2, d)) for d in (12, 13, 16, 17, 18, 19, 20))
    assert is_scheduled_closure(date(2026, 9, 28))
    assert not is_scheduled_closure(date(2025, 1, 2))
    assert not is_scheduled_closure(date(2026, 2, 23))


def test_empty_response_on_expected_trading_day_still_fails(tmp_path):
    session = FakeSession({'tables': [{'data': []}]})
    with pytest.raises(ValueError, match='no valid ordinary-stock bars'):
        collect_chunk(session, 'tpex', [date(2025, 1, 2)], {'6488': {}}, 'u3',
                      tmp_path/'bad.json.gz', min_interval=0, request_budget=[1])
    assert session.calls == 1
    assert not (tmp_path/'bad.json.gz').exists()


def test_daily_checkpoint_resumes_inside_ten_day_chunk_without_refetch(tmp_path):
    """A notebook may stop between days and resume without losing the prior day."""
    dates = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    payload = {'tables': [{'data': [
        ['6488', '環球晶', '355', '+1', '352', '356', '349', '', '2,500', '887,500', '40']
    ]}]}
    session = FakeSession(payload)
    path = tmp_path / 'tpex-000.json.gz'
    universe = {'6488': {'symbol': '6488'}}
    for completed in (1, 2):
        budget = [1]
        assert collect_chunk(session, 'tpex', dates, universe, 'H', path,
                             min_interval=0, request_budget=budget) is False
        partial = read_chunk(path, 'H')
        assert len(partial['days']) == completed
        assert len(partial['rows']) == completed
        assert session.calls == completed and budget[0] == 0
    assert collect_chunk(session, 'tpex', dates, universe, 'H', path,
                         min_interval=0, request_budget=[1])
    assert session.calls == 3
    assert [s['day'] for s in read_chunk(path, 'H')['days']] == [d.isoformat() for d in dates]


def test_partial_day_checkpoint_does_not_seal_month(tmp_path):
    day1, day2 = date(2025, 1, 2), date(2025, 1, 3)
    month = tmp_path / '2025-01'
    folder = month / '_checkpoint' / 'r1'
    folder.mkdir(parents=True)
    payload = {'schema_version': 1, 'universe_hash': 'H', 'market': 'twse',
               'days': [{'day': day1.isoformat(), 'status': 'COLLECTED', 'sha256': 'a'}],
               'rows': [{'symbol': '2330', 'trade_date': day1.isoformat()}]}
    (folder / 'twse-000.json.gz').write_bytes(gzip.compress(json_bytes(payload), mtime=0))
    roster = {'twse': {'2330': {'symbol': '2330', 'market': 'twse'}},
              'tpex': {'6488': {'symbol': '6488', 'market': 'tpex'}}}
    result = finalize_month(tmp_path, '2025-01', 'r1', [day1, day2], roster,
                            {'universe': 'H', 'captured_at': 'now'})
    assert result['status'] == 'PARTIAL' and result['pending_chunks'] == 2
    assert not (month / 'manifest-r1.json').exists()


def test_deadline_safely_stops_then_restarts_without_discarding_previous_day(tmp_path, monkeypatch):
    from research.colab import collect_tw_equities as c
    dates = [date(2025, 1, 2), date(2025, 1, 3)]
    payload = {'tables': [{'data': [
        ['6488', '環球晶', '355', '+1', '352', '356', '349', '', '2,500', '887,500', '40']
    ]}]}
    session = FakeSession(payload)
    path = tmp_path / 'tpex-000.json.gz'
    clock = {'now': 100.0}
    monkeypatch.setattr(c.time, 'monotonic', lambda: clock['now'])
    assert not collect_chunk(session, 'tpex', dates, {'6488': {}}, 'H', path,
                             min_interval=0, request_budget=[2], deadline=185.0)
    assert session.calls == 0 and not path.exists()
    clock['now'] = 10.0
    assert not collect_chunk(session, 'tpex', dates, {'6488': {}}, 'H', path,
                             min_interval=0, request_budget=[1], deadline=200.0)
    assert session.calls == 1 and len(read_chunk(path, 'H')['days']) == 1
    assert collect_chunk(session, 'tpex', dates, {'6488': {}}, 'H', path,
                         min_interval=0, request_budget=[1], deadline=200.0)
    assert session.calls == 2


def test_resume_rejects_checkpoint_from_another_calendar_or_market(tmp_path):
    path = tmp_path / 'chunk.gz'
    rows = {'schema_version': 1, 'universe_hash': 'H', 'market': 'twse',
            'days': [{'day': '2025-01-03', 'status': 'COLLECTED', 'sha256': 'x'}],
            'rows': []}
    path.write_bytes(gzip.compress(json_bytes(rows), mtime=0))
    with pytest.raises(ValueError, match='dates/order'):
        collect_chunk(FakeSession({}), 'twse', [date(2025, 1, 2)], {},
                      'H', path, min_interval=0, request_budget=[2])
    with pytest.raises(ValueError, match='market changed'):
        collect_chunk(FakeSession({}), 'tpex', [date(2025, 1, 3)], {},
                      'H', path, min_interval=0, request_budget=[2])


def test_research_ordinary_stock_coverage_thresholds_and_provenance():
    """90% TWSE / 70% TPEx are inclusive research gates, not PIT certification."""
    import pandas as pd
    from research.colab.monthly_folder_io import assess_monthly_ordinary_stock_coverage
    universe = pd.DataFrame([
        {'symbol': str(1000 + i), 'market': 'twse'} for i in range(10)
    ] + [
        {'symbol': str(2000 + i), 'market': 'tpex'} for i in range(10)
    ])
    bars = pd.DataFrame([
        {'symbol': str(1000 + i), 'market': 'twse'} for i in range(9)
    ] + [
        {'symbol': str(2000 + i), 'market': 'tpex'} for i in range(7)
    ])
    quality = {'status': 'PROBE', 'market_counts': {
        'twse': {'snapshot_symbols': 10, 'symbols_with_bars': 9, 'observed_ratio': 0.9},
        'tpex': {'snapshot_symbols': 10, 'symbols_with_bars': 7, 'observed_ratio': 0.7},
    }}
    accepted = assess_monthly_ordinary_stock_coverage(quality, universe, bars)
    assert accepted['status'] == 'RESEARCH_COVERAGE_ACCEPTED_NOT_PIT_CERTIFIED'
    assert all(x['passes'] for x in accepted['markets'].values())
    assert accepted['basis'] == 'CURRENT_MASTER_ONLY'
    for market, remaining, count in [('twse', 8, 8), ('tpex', 6, 6)]:
        reduced = pd.concat([
            bars[bars['market'] != market],
            bars[bars['market'] == market].head(remaining),
        ], ignore_index=True)
        q = json.loads(json.dumps(quality))
        q['market_counts'][market]['symbols_with_bars'] = count
        q['market_counts'][market]['observed_ratio'] = count / 10
        with pytest.raises(ValueError, match='below 90% TWSE / 70% TPEx'):
            assess_monthly_ordinary_stock_coverage(q, universe, reduced)
    with pytest.raises(ValueError, match='disagrees'):
        assess_monthly_ordinary_stock_coverage(quality, universe, bars.iloc[:-1])



def test_market_stock_day_coverage_rejects_sparse_bars_even_with_monthly_symbol_presence():
    import pandas as pd
    from research.colab.monthly_folder_io import assess_monthly_ordinary_stock_coverage
    roster = pd.DataFrame([
        {'symbol': str(1000 + i), 'market': 'twse'} for i in range(10)
    ] + [
        {'symbol': str(2000 + i), 'market': 'tpex'} for i in range(10)
    ])
    daily = pd.DataFrame([
        {'symbol': str(1000 + i), 'market': 'twse'} for i in range(9)
    ] + [
        {'symbol': str(2000 + i), 'market': 'tpex'} for i in range(7)
    ])
    bars = pd.concat([daily] * 10, ignore_index=True)
    manifest = {'source_daily_sha256': [{'status': 'COLLECTED'}] * 20}
    quality = {'market_counts': {
        'twse': {'snapshot_symbols': 10, 'symbols_with_bars': 9, 'observed_ratio': .9},
        'tpex': {'snapshot_symbols': 10, 'symbols_with_bars': 7, 'observed_ratio': .7},
    }}
    status = assess_monthly_ordinary_stock_coverage(quality, roster, bars, manifest)
    assert status['markets']['twse']['stock_day_ratio'] == pytest.approx(.9)
    assert status['markets']['tpex']['stock_day_ratio'] == pytest.approx(.7)
    # Every ordinary stock still has a bar this month, but one trading-day
    # observation vanished; monthly-presence alone must not pass.
    twse_sparse = bars.drop(index=bars[bars['market'] == 'twse'].index[0])
    with pytest.raises(ValueError, match='below 90% TWSE / 70% TPEx'):
        assess_monthly_ordinary_stock_coverage(quality, roster, twse_sparse, manifest)
    tpex_sparse = bars.drop(index=bars[bars['market'] == 'tpex'].index[0])
    with pytest.raises(ValueError, match='below 90% TWSE / 70% TPEx'):
        assess_monthly_ordinary_stock_coverage(quality, roster, tpex_sparse, manifest)
