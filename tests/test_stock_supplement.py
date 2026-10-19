from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path

import pytest

from ingestion_core.supplement_sources import parse_prices, parse_revenue, parse_valuation, parse_eps_history
from ingestion_core.stock_supplement import revenue_months
from ingestion_core.serving_projection import StockServingProjection
from ingestion_core.valuation_history import two_year_profile
from packages.duckdb_query.iceberg import DuckDBIcebergCore
from packages.web_api import CoreQueryService

RECEIVED = '2026-10-19T05:00:00+00:00'


def document(rows):
    return json.dumps({'status':200,'data':rows}).encode()


def test_revenue_keeps_distinct_month_natural_keys_and_serving_units():
    raw = document([{'stock_id':'1513','date':f'2026-{m+1:02d}-01',
        'revenue_year':2026,'revenue_month':m,'revenue':1234000+m} for m in (1,2,3)])
    rows = parse_revenue(raw,'1513',start=date(2026,1,1),end=date(2026,10,19),received_at=RECEIVED)
    assert len({tuple(str(r.get(k)) for k in DuckDBIcebergCore.IDENTIFIERS['financials']) for r in rows})==3
    row = rows[0]
    assert Decimal(row['value'])==Decimal('1234.001') and row['published_at'] is None
    result = StockServingProjection._row('financials',row,execution_id='test',provenance_id='raw',source_id='finmind',core_snapshot_id=1)
    payload = json.loads(result[4])
    assert payload['canonical_metric']=='monthly_revenue_01' and payload['metric']=='monthly_revenue'
    service = CoreQueryService(lambda *_:[],serving_series=lambda *_:[payload])
    assert service.visual_series('1513','revenue')['usable_points']==1


def test_price_identity_dates_and_invalid_candles_fail_closed():
    row = {'stock_id':'1513','date':'2026-10-16','open':10,'max':12,'min':9,'close':11,
           'Trading_Volume':1000,'Trading_money':11000}
    options = dict(start=date(2026,1,1),end=date(2026,10,19),received_at=RECEIVED)
    parsed = parse_prices(document([row]),'1513','TWSE',**options)
    assert parsed[0]['volume_shares']==1000 and parsed[0]['source_id']=='finmind'
    for bad in ({**row,'stock_id':'2330'},{**row,'date':'2026-11-01'},{**row,'max':1}):
        with pytest.raises(ValueError):
            parse_prices(document([bad]),'1513','TWSE',**options)


def test_eps_history_keeps_latest_12_explicit_quarters_and_rejects_wrong_identity():
    quarters = [(2026,2),(2026,1)]+[(y,q) for y in (2025,2024,2023) for q in (4,3,2,1)]
    page = ('<title>亞力(1513.TW) 每股盈餘</title>單季每股盈餘 年度/季別 '+
            ' '.join(f'{y} Q{q} -1.25 0% 0% 10' for y,q in quarters)).encode()
    rows = parse_eps_history(page,'1513','TWSE',received_at=RECEIVED)
    assert len(rows)==12 and rows[-1]['fiscal_period_end']=='2023-09-30'
    assert all(r['value']=='-1.25' and r['share_basis_status']=='provider_reported_unspecified' for r in rows)
    for bad in (page.replace(b'1513.TW',b'2330.TW'),page.replace('單季'.encode(),'累季'.encode()),page+b' 2026 Q2 99'):
        with pytest.raises(ValueError):
            parse_eps_history(bad,'1513','TWSE',received_at=RECEIVED)


def test_revenue_due_window_has_13_months_and_rolls_after_due_date():
    assert len(revenue_months(date(2026,10,10)))==13
    assert max(revenue_months(date(2026,10,10)))==(2026,8)
    assert max(revenue_months(date(2026,10,11)))==(2026,9)


def test_finmind_profile_uses_approved_source_and_keeps_negative_pe_nullable():
    raw = document([{'stock_id':'1513','date':'2026-10-16','PER':-1,'PBR':2,'dividend_yield':3}])
    rows = parse_valuation(raw,'1513','TWSE',start=date(2024,10,1),end=date(2026,10,19),received_at=RECEIVED)
    assert rows[0]['pe_ratio'] is None and rows[0]['pb_ratio']=='2'
    start = date(2024,10,19)
    history = [{'symbol':'1513','observed_date':str(start+timedelta(days=i)),
        'pb_ratio':'2','source_id':'finmind','provenance_id':'raw'} for i in range(731)]
    assert two_year_profile(history,symbol='1513',metric='pb_ratio',as_of=date(2026,10,19))['status']=='ready'


def test_trigger_only_sends_bounded_queue_mode_without_owner_data():
    from services.api.public_runtime import PipelineService
    from unittest.mock import Mock
    service = PipelineService(project='test',region='us-central1',ingestion_job='ingestion',mart_job='mart')
    session = Mock()
    service._authorized_session = lambda:session
    assert service.supplement()=={'status':'accepted'}
    payload = session.post.call_args.kwargs['json']
    env = {r['name']:r['value'] for r in payload['overrides']['containerOverrides'][0]['env']}
    assert env['JANUS_DATA_SUPPLEMENT_MODE']=='demand' and env['MART_JOB']==''
    assert 'user_id' not in json.dumps(payload) and payload['overrides']['taskCount']==1


def test_failed_source_is_partial_and_never_releases_stage_cleanup_fence(monkeypatch):
    from unittest.mock import MagicMock
    from ingestion_core import stock_supplement as worker
    control, core, writer, projection = (MagicMock() for _ in range(4))
    control.connection.cursor.return_value.__enter__.return_value.fetchone.return_value = ('TWSE',None,True)
    monkeypatch.setattr(worker,'still_wanted',lambda *_args,**_kwargs:True)
    monkeypatch.setattr('ingestion_core.data_supplement._rows',lambda *_args,**_kwargs:[])
    def unavailable(_url):
        raise TimeoutError('untrusted request details must never enter a receipt')
    receipt = worker.supplement_one(control,core,writer,projection,('1513',1,'lease'),
        today=date(2026,10,19),fetch=unavailable)
    assert not receipt['ready'] and len(receipt['errors'])==4
    assert 'untrusted' not in json.dumps(receipt)
    core.write.assert_not_called()
    writer.mark_core_committed.assert_not_called()
    control.complete_collection.assert_called_once_with(control.enqueue_collection.return_value.execution_id,None,partial=True)


def test_cancelled_lease_stops_before_source_http(monkeypatch):
    from unittest.mock import MagicMock
    from ingestion_core import stock_supplement as worker
    control, core, writer, projection, fetch = (MagicMock() for _ in range(5))
    control.connection.cursor.return_value.__enter__.return_value.fetchone.return_value = ('TPEX','BOND_ETF',False)
    monkeypatch.setattr(worker,'still_wanted',lambda *_args,**_kwargs:False)
    receipt = worker.supplement_one(control,core,writer,projection,('00719B',1,'lease'),
        today=date(2026,10,19),fetch=fetch)
    assert receipt['cancelled'] and not receipt['ready']
    fetch.assert_not_called()
    writer.mark_core_committed.assert_not_called()
