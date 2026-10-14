from datetime import date
from decimal import Decimal
from ingestion_core.first_batch import (normalise_monthly_revenue, normalise_financials,
    normalise_tpex_day_trading, normalise_tpex_financing, normalise_tpex_lending)
from packages.web_api import CoreQueryService


def test_revenue_preserves_actual_months_and_units_across_year_boundary():
    rows = normalise_monthly_revenue([{'資料年月': '11501', '出表日期': '1150210',
        '公司代號': '6488', '營業收入-當月營收': '1,234', '營業收入-上月營收': '0'}])
    assert [(row['fiscal_period_end'], row['fiscal_year'], row['value']) for row in rows] == [
        ('2026-01-31', 2026, '1234'), ('2025-12-31', 2025, '0')]
    assert all(row['unit'] == 'TWD_thousands' for row in rows)


def test_tpex_financial_identity_does_not_turn_english_fields_into_metrics():
    rows = normalise_financials([{'Date': '1150814', 'Year': '115', 'Season': '2',
        'SecuritiesCompanyCode': '6488', 'CompanyName': '環球晶', '基本每股盈餘（元）': '-2.5'}])
    assert len(rows) == 1
    assert (rows[0]['symbol'], rows[0]['fiscal_year'], rows[0]['fiscal_quarter']) == ('6488', 2026, 2)
    assert rows[0]['unit'] == 'TWD_per_share' and rows[0]['value'] == '-2.5'


def test_day_trading_ignores_market_summary_and_preserves_per_stock_zero():
    rows = normalise_tpex_day_trading([{'Date': '20261013', '當日沖銷交易總成交股數': '99'},
        {'Date': '20261013', '證券代號': '6488', '當日沖銷交易成交股數': '0',
         '當日沖銷交易買進成交金額': '0', '當日沖銷交易賣出成交金額': '0'}])
    assert len(rows) == 3 and all(row['symbol'] == '6488' and row['market'] == 'TPEX' for row in rows)
    assert rows[0]['value'] == '0' and rows[0]['unit'] == 'shares'


def test_tpex_institutional_uses_requested_day_and_preserves_duplicate_column_groups():
    import json
    import pytest
    from ingestion_core.first_batch import dataset_adapters, normalise_tpex_institutional
    from ingestion_core.adapters import CollectionRequest
    cells = ['6488', '環球晶'] + [str(i) for i in range(2, 24)]
    fields = ['代號', '名稱'] + ['買進股數', '賣出股數', '買賣超股數'] * 7 + ['合計']
    document = {'date': '20261013', 'tables': [{'fields': fields, 'data': [cells]}, {}]}
    urls = []
    def transport(url):
        urls.append(url)
        return json.dumps(document).encode()
    adapter = dataset_adapters(transport)['tpex-institutional']
    request = CollectionRequest('test', 'test', 'tpex', 'institutional', 'TPEX',
                                ('6488',), None, date(2026, 10, 13), 30)
    rows = adapter.fetch(request).rows
    assert 'date=2026%2F10%2F13' in urls[0]
    assert [(r['investor_type'], r['buy_shares'], r['sell_shares'], r['net_shares']) for r in rows] == [
        ('foreign', '2', '3', '4'), ('investment_trust', '11', '12', '13'), ('dealer', '20', '21', '22')]
    assert all(r['trade_date'] == '2026-10-13' and r['market'] == 'TPEX' for r in rows)
    with pytest.raises(ValueError):
        normalise_tpex_institutional([{'代號': '6488', 'Date': '20261013', '_cells': cells[:-1]}])


def test_eps_chart_only_accepts_verified_single_quarter_and_preserves_loss():
    common = {'source_id': 'mops', 'provenance_id': 'official', 'unit': 'TWD_per_share',
              'period_basis': 'single_quarter', 'metric': 'eps_single_quarter'}
    rows = [{**common, 'period_end': '2026-03-31', 'value': '-2.5'},
            {**common, 'period_end': '2026-06-30', 'value': '0'},
            {**common, 'period_end': '2026-09-30', 'value': '9', 'period_basis': 'year_to_date'}]
    service = CoreQueryService(lambda *_: [], serving_series=lambda *_: rows)
    result = service.visual_series('6488', 'eps')
    assert [Decimal(point['value']) for point in result['points']] == [Decimal('-2.5'), Decimal(0)]
    assert result['data_status'] == 'available'


def test_tpex_dated_valuation_uses_historical_official_json_and_roc_request():
    from datetime import datetime, timezone
    import json
    from ingestion_core.first_batch import dataset_adapters
    from ingestion_core.adapters import CollectionRequest
    requests = []
    document = {'date':'20261013', 'stat':'OK', 'tables':[{
        'fields':['股票代號','公司名稱','本益比','殖利率(%)','股價淨值比'],
        'data':[['6488','環球晶','-','0.00','2.64'],
                ['1240','茂生農經','10.33','0.90','1.64']]}]}
    def transport(url):
        requests.append(url)
        return json.dumps(document,ensure_ascii=False).encode()
    adapter = dataset_adapters(transport)['tpex-valuation']
    adapter.clock = lambda: datetime(2026,10,14,tzinfo=timezone.utc)
    request = CollectionRequest('test','test','tpex','valuation','TPEX',
                                ('6488','1240'), None, date(2026,10,13), 30)
    response = adapter.fetch(request)
    assert 'pera_result.php?' in requests[0]
    assert 'o=json' in requests[0] and 'd=115%2F10%2F13' in requests[0]
    assert len(response.rows) == 2
    assert response.rows[0]['symbol'] == '6488'
    assert response.rows[0]['observed_date'] == '2026-10-13'
    assert response.rows[0]['pe_ratio'] is None
    assert response.rows[0]['dividend_yield_percent'] == '0.00'
    assert response.rows[0]['pb_ratio'] == '2.64'
    assert response.raw_payload == json.dumps(document,ensure_ascii=False).encode()


def test_tpex_dated_valuation_never_accepts_wrong_day_even_if_older():
    from datetime import datetime, timezone
    import json
    import pytest
    from ingestion_core.first_batch import dataset_adapters
    from ingestion_core.adapters import CollectionRequest
    document = {'date':'20261013', 'tables':[{'fields':['股票代號','本益比','股價淨值比','殖利率(%)'],
                                               'data':[['6488','22','2.5','0']]}]}
    adapter = dataset_adapters(lambda _:json.dumps(document).encode())['tpex-valuation']
    adapter.clock = lambda: datetime(2026,10,14,tzinfo=timezone.utc)
    request = CollectionRequest('test','test','tpex','valuation','TPEX',
                                ('6488',),None,date(2026,10,13),30)
    assert len(adapter.fetch(request).rows) == 1
    for wrong_day in ('20261012','20261014'):
        document['date'] = wrong_day
        with pytest.raises(ValueError,match='source date differs'):
            adapter.fetch(request)
