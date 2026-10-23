import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'research' / 'colab'))
import official_index_backfill as c


def market_fixture():
    return {'stat':'OK','fields':['日期','開盤指數','最高指數','最低指數','收盤指數'],
            'data':[['114/01/02','23,000','23,020','22,920','22,960'],
                    ['114/01/03','22,970','23,050','22,900','23,010']]}


def sector_fixture():
    return {'stat':'OK','date':'20250102','tables':[
        {'title':'價格指數(臺灣證券交易所)', 'fields':['指數','收盤指數','漲跌(+/-)'],
         'data':[['電子工業類指數','2,700.21','+'],['半導體類指數','1,410.00','+'],
                 ['發行量加權股價指數','22,960.00','-'],['臺指日報酬兩倍指數','100','-']]}]}


def tpex_market_fixture():
    return {'stat':'OK','tables':[{'title':'日成交量值、指數',
     'fields':['資料日期','開市','最高價','最低價','收市'],
     'data':[['114/01/02','260','268','258','265'],['114/01/03','266','270','265','269']]}]}


def tpex_sector_fixture():
    return {'stat':'OK','tables':[{'title':'產業分類股價指數一覽表',
     'fields':['資料日期','半導體類指數','航運類指數','全月平均'],
     'data':[['114/01/02','1,452.30','210.5','100'],['114/01/03','1,489.20','211.5','100']]}]}


def test_twse_index_good():
    v=c.parse_twse_market(market_fixture(),'2025-01')
    assert len(v)==2 and v[0]['trade_date']=='2025-01-02' and v[1]['close']==23010


def test_twse_month_mismatch_refused():
    with pytest.raises(c.SchemaBlocked, match='WRONG_MONTH'):
        c.parse_twse_market(market_fixture(),'2025-02')


def test_twse_bad_ohlc_refused():
    p=market_fixture();p['data'][0][3]='24,000'
    with pytest.raises(c.SchemaBlocked, match='OHLC_INVALID'):
        c.parse_twse_market(p,'2025-01')


def test_twse_duplicate_refused():
    p=market_fixture();p['data'].append(p['data'][0])
    with pytest.raises(c.SchemaBlocked,match='DUPLICATE'):
        c.parse_twse_market(p,'2025-01')


def test_twse_sector_filters_non_sector_and_date():
    rows=c.parse_twse_sector(sector_fixture(),'2025-01-02')
    assert len(rows)==2 and all(x['type']=='sector_price_index' for x in rows)
    p=sector_fixture();p['date']='20250103'
    with pytest.raises(c.SchemaBlocked,match='DATE_NOT_VERIFIED'):
        c.parse_twse_sector(p,'2025-01-02')


def test_twse_sector_schema_failure_refused():
    with pytest.raises(c.SchemaBlocked,match='TABLE_NOT_CONFIRMED'):
        c.parse_twse_sector({'stat':'OK','date':'20250102','tables':[]},'2025-01-02')


def test_tpex_market():
    rows=c.parse_tpex_market(tpex_market_fixture(),'2025-01')
    assert len(rows)==2 and rows[0]['open']==260 and rows[1]['close']==269


def test_tpex_wrong_date():
    with pytest.raises(c.SchemaBlocked,match='WRONG_MONTH'):
        c.parse_tpex_market(tpex_market_fixture(),'2025-02')


def test_tpex_sector_daily_wide():
    rows=c.parse_tpex_sector(tpex_sector_fixture(),'2025-01')
    assert len(rows)==4
    assert {r['index_id'] for r in rows}=={'半導體類指數','航運類指數'}


def test_tpex_sector_missing_date_refused():
    p=tpex_sector_fixture();p['tables'][0]['data'][0][0]='全月平均'
    p['tables'][0]['data'][1][0]='全月平均'
    with pytest.raises(c.SchemaBlocked, match='NO_VERIFIED_DAILY_ROWS'):
        c.parse_tpex_sector(p,'2025-01')


def test_urls_and_rate_guards():
    assert parse_qs(urlparse(c.url_for('twse_market','2025-01')).query)['date']==['20250101']
    assert parse_qs(urlparse(c.url_for('twse_sector','2025-01-02')).query)['date']==['20250102']
    assert parse_qs(urlparse(c.url_for('tpex_sector','2025-01')).query)['date']==['114/01/01']
    with pytest.raises(ValueError,match='AT_LEAST_2'):
        c.RunOptions(interval_seconds=0).validate()
    now=datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y-%m')
    with pytest.raises(ValueError,match='CANNOT_COLLECT_CURRENT'):
        c.RunOptions(start_month=now,end_month=now).validate()


def test_immutable_conflict(tmp_path):
    p=tmp_path/'immutable'
    c.write_new(p,b'first')
    assert c.write_new(p,b'first')==hashlib.sha256(b'first').hexdigest()
    with pytest.raises(ValueError,match='IMMUTABLE_CONFLICT'):
        c.write_new(p,b'second')


def test_verified_receipt_hash_readback(tmp_path):
    f=tmp_path/'a';f.mkdir()
    (f/'raw.json').write_bytes(b'data')
    (f/'receipt.json').write_text(json.dumps({'version':c.VERSION,'status':'VERIFIED','checksums':{
        'raw.json':hashlib.sha256(b'data').hexdigest()},'normalized':'raw.json'}))
    assert c._verify_receipt(f)['status']=='VERIFIED'
    (f/'raw.json').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='HASH_MISMATCH'):
        c._verify_receipt(f)


class Response:
    def __init__(self,payload,status_code=200):
        self.status_code=status_code; self.content=json.dumps(payload).encode()


def test_budget_and_provider_block(tmp_path, monkeypatch):
    # We can test full driver without pyarrow by injecting a controlled fake writer.
    seen=[]
    def fake_writer(folder,raw,rows,receipt):
        x=c.json_bytes(rows);f='normalized.json';c.write_new(folder/f,x)
        receipt.update({'status':'VERIFIED','rows':len(rows),'normalized':f,
            'checksums':{f:c.sha_bytes(x)}})
        c._save_receipt(folder,receipt)
    monkeypatch.setattr(c,'write_partition',fake_writer)
    def fetch(url,timeout=None,headers=None):
        src=urlparse(url).path
        seen.append(src)
        if 'daily-indices' in src:return Response({},status_code=403)
        
        payload=market_fixture()
        payload['data']=[
            [f'114/01/{d:02d}','23,000','23,020','22,920','22,960']
            for d in range(2,17)]
        return Response(payload)
    options=c.RunOptions(start_month='2025-01',end_month='2025-01',max_requests=2,
                         max_minutes=15,include_twse_sector=False,include_tpex_sector=True)
    result=c.backfill(tmp_path,options,fetch=fetch,sleep=lambda s:None)
    assert result['requests_used']==2
    assert result['current_run_status_counts']['SOURCE_BLOCKED']==1
    assert result['partition_verified_counts']['twse_market']==1
    assert result['status']!='ALL_SAVED'
    result2=c.backfill(tmp_path,options,fetch=fetch,sleep=lambda s:None)
    assert result2['partition_verified_counts']['twse_market']==1
    assert 'twse_market_SKIPPED_VERIFIED' not in result2['current_run_status_counts']
    assert len(seen)==3  # on second run, TWSE reused and TPEx still blocked


def test_market_calendar_gates_daily_sector(tmp_path):
    base=tmp_path/'derived/factor_inputs/official_index_backfill'/c.VERSION
    assert list(c._job_list(['2025-01'],base,include_twse_sector=True,include_tpex_sector=False))==[
        ('twse_market','2025-01'),('tpex_market','2025-01')]


def test_actual_parquet_roundtrip_if_available(tmp_path):
    pytest.importorskip('pyarrow')
    rows=c.parse_twse_market(market_fixture(),'2025-01')
    now='2026-10-23T05:00:00+00:00'
    receipt={'attempt_id':'20261023-abc','version':c.VERSION,'status':'UNKNOWN'}
    c.write_partition(tmp_path,b'{"stat":"OK"}',rows,receipt)
    assert c._verify_receipt(tmp_path)['rows']==2

class RawResponse:
    def __init__(self, raw, status_code=200, content_type='text/html'):
        self.status_code=status_code
        self.content=raw
        self.headers={'Content-Type':content_type}


def test_html_404_one_probe_per_source(tmp_path):
    seen=[]
    def fetch(url,timeout=None,headers=None):
        seen.append(url)
        return RawResponse(b'<!DOCTYPE html><html><head><title>404</title></head><body>gone</body></html>')
    got=c.backfill(tmp_path,c.RunOptions(start_month='2025-01',end_month='2025-03',max_requests=70,
                include_twse_sector=True,include_tpex_sector=True),fetch=fetch,sleep=lambda x:None)
    assert len(seen)==3
    assert got['current_run_status_counts']['SOURCE_ENDPOINT_INVALID']==3
    assert got['current_run_status_counts']['SKIPPED_INVALID_SOURCE']==6
    assert got['partition_verified_counts']['twse_market']==0
    assert got['outstanding_partition_count']==12
    rec=json.loads((tmp_path/'derived'/'factor_inputs'/'official_index_backfill'/c.VERSION/'twse_market'/'2025-01'/'receipt.json').read_text())
    assert rec['response_content_type']=='text/html'
    assert rec['detail']=='HTTP_200_HTML_404'
    assert rec['publication_allowed'] is False


def test_real_404_one_probe_per_source(tmp_path):
    seen=[]
    def fetch(url,timeout=None,headers=None):
        seen.append(url)
        return RawResponse(b'Not Found',status_code=404)
    got=c.backfill(tmp_path,c.RunOptions(start_month='2025-01',end_month='2025-03',max_requests=70),fetch=fetch,sleep=lambda x:None)
    assert len(seen)==3
    assert got['current_run_status_counts']['SOURCE_ENDPOINT_INVALID']==3
    assert got['current_run_status_counts']['SKIPPED_INVALID_SOURCE']==6


def test_html_landing_page_distinguished_from_404(tmp_path):
    def fetch(url,timeout=None,headers=None):
        return RawResponse(b'<!doctype html><html><title>Daily indices</title></html>')
    got=c.backfill(tmp_path,c.RunOptions(start_month='2025-01',end_month='2025-01',max_requests=4),fetch=fetch,sleep=lambda x:None)
    assert got['current_run_status_counts']['SOURCE_FORMAT_UNSUPPORTED']==3
    assert got['status']!='SOURCE_DATA_VERIFIED_COMPLETE'
