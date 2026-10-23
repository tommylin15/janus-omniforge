from __future__ import annotations
import json,sys,hashlib
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'/'colab'))
import valuation_backfill as v


def task():
    identity={'source':'finmind','dataset':'income','market':'twse','symbol':'2330',
              'start':'2025-03-31','end':'2025-03-31'}
    return dict(identity,task_id=v.digest(v.canonical_json(identity))[:24])


class FakeResponse:
    def __init__(self, status=200, data=None, retry=None):
        self.status_code=status
        self.headers={'Retry-After':str(retry)} if retry is not None else {}
        self._data={'status':200,'data':[{'date':'2025-03-31','stock_id':'2330','type':'Revenue','value':42}]} if data is None else data
        self.content=json.dumps(self._data).encode()
    def json(self):return self._data

class Session:
    def __init__(self,responses):self.responses=list(responses);self.calls=[]
    def get(self,url,**kw):
        self.calls.append((url,kw));return self.responses.pop(0)


def test_429_honors_retry_after_and_no_token_leak():
    s=Session([FakeResponse(429,retry=9),FakeResponse()]);wait=[]
    result=v.fetch_finmind(s,task(),'EXAMPLE_TOKEN',max_retries=1,sleeper=wait.append)
    assert wait==[9] and len(s.calls)==2
    assert s.calls[0][1]['headers']['Authorization']=='Bearer EXAMPLE_TOKEN'
    assert result['status']=='SUCCESS' and 'EXAMPLE_TOKEN' not in str(result)

@pytest.mark.parametrize('code',[401,403])
def test_access_denied_not_retried(code):
    s=Session([FakeResponse(code)])
    with pytest.raises(v.SourceError,match='ACCESS_DENIED'):
        v.fetch_finmind(s,task(),'TOPSECRET',max_retries=3,sleeper=lambda _:None)
    assert len(s.calls)==1


def test_schema_changed_and_empty_response():
    s=Session([FakeResponse(data={'data':{'unexpected':1}})])
    with pytest.raises(v.SourceError,match='SCHEMA_ERROR'):
        v.fetch_finmind(s,task(),None,max_retries=0)
    assert v.fetch_finmind(Session([FakeResponse(data={'data':[],'status':200})]),task(),None,max_retries=0)['status']=='EMPTY_CONFIRMED'


def test_checkpoint_corruption_refetch_needed(tmp_path):
    t=task();d=tmp_path/t['task_id'];r=v.fetch_finmind(Session([FakeResponse()]),t,None,max_retries=0)
    v.finish_task(d,t,r)
    assert v.valid_checkpoint(d,t)
    (d/'rows.json').write_text('[]')
    assert not v.valid_checkpoint(d,t)
    with pytest.raises(ValueError,match='CORRUPT'):
        v.finish_task(d,t,r)


def test_lock_rejects_second_writer_even_expired(tmp_path):
    f=v.writer_lock(tmp_path,'run123')
    with pytest.raises(RuntimeError,match='WRITER_LOCK_EXISTS'):
        v.writer_lock(tmp_path,'run123')
    f.unlink()


def test_no_wrong_root_created(tmp_path):
    with pytest.raises(FileNotFoundError):v.checked_root(tmp_path/'個人用'/'janusChatGPT')
    assert not (tmp_path/'個人用').exists()


def test_ytd_diff_valid_invalid_and_eps_blocked():
    common=dict(fiscal_year=2025,statement_scope='consolidated',currency='TWD',unit_multiplier=1,
                item_standard='revenue',revision_id='R1',period_basis='YTD')
    p=dict(common,value_numeric=100,fiscal_quarter=1)
    c=dict(common,value_numeric=250,fiscal_quarter=2)
    assert v.ytd_to_quarter(c,p)==(150,'OK')
    assert v.ytd_to_quarter({**c,'statement_scope':'individual'},p)[0] is None
    assert v.ytd_to_quarter({**c,'item_standard':'basic_eps'},p)[1]=='EPS_CANNOT_DIFFERENCE'
    assert v.ytd_to_quarter(c,None)[1]=='PREVIOUS_YTD_MISSING'


def test_negative_net_income_allowed_nonpositive_denominator_blocked():
    assert v.safe_div(-5,100)==(-.05,'OK')
    assert v.safe_div(20,0)[0] is None
    assert v.safe_div(20,-10)[0] is None


def test_unknown_announcement_is_not_pit_verified():
    x={'dataset':'income','_dataset':'financials','item':'Revenue','value':'23',
       'unit_basis':'RETAIN_SOURCE_HEADER_VERIFY_BEFORE_TRAINING','period_basis':'UNKNOWN'}
    assert v.classify_existing(x)[0]=='MAPPING_REQUIRED'
    assert v.redact('Bearer SECRET','SECRET')=='Bearer [REDACTED]'


def test_inventory_plan_only_no_fetch_with_existing(tmp_path):
    root=tmp_path/'janusChatGPT';base=root/'資料源'/'JanusDataset_v3_202610'/'canonical';rel=base/'release-test';rel.mkdir(parents=True)
    (base/'CURRENT.json').write_text('{"release":"release-test","format":"parquet"}')
    (rel/'manifest.json').write_text('{"files":{}}')
    run=root/'模型研究'/'valuation'/'backfill_candidates'/'TEST1';run.mkdir(parents=True)
    inv=v.inventory(root,run,rows=[dict(_dataset='financials',_file='financials/2025-03.parquet',
        market='twse',symbol='2330',dataset='income',fiscal_quarter='2025Q1',item='Revenue',value=1,
        period_basis='UNKNOWN',unit_basis='UNKNOWN')])
    planned=v.plan(root,run,inv,symbols=['2330'],start='2025-01-01',end='2025-03-31',markets={'2330':'twse'},as_of='2026-10-23')
    assert len(planned)>0 and (run/'gap_plan.csv').exists()
    assert v.fetch(root,run,run_fetch=False,dry_run=True)['actual_requests']==0
    assert (base/'CURRENT.json').read_text()=='{"release":"release-test","format":"parquet"}'


def test_not_yet_available_not_fetch_required(tmp_path):
    root=tmp_path/'janusChatGPT';base=root/'資料源'/'JanusDataset_v3_202610'/'canonical';rel=base/'release-test';rel.mkdir(parents=True)
    (base/'CURRENT.json').write_text('{"release":"release-test","format":"parquet"}')
    (rel/'manifest.json').write_text('{"files":{}}')
    run=root/'tmp';run.mkdir()
    inv=v.inventory(root,run,rows=[])
    assert v.plan(root,run,inv,symbols=['2330'],start='2027-01-01',end='2027-03-31',markets={'2330':'twse'},as_of='2026-10-23')==[]


def test_month_and_quarter_window():
    assert v.quarters('2025-01-01','2025-09-30')==['2025Q1','2025Q2','2025Q3']
    assert v.months('2025-01-01','2025-03-31')==['2025-01','2025-02','2025-03']


def test_explicit_unit_conversion_only():
    assert v.unit_to_base('1,250','TWD_THOUSAND')==(1250000,'OK')
    assert v.unit_to_base(-5,'TWD')==(-5,'OK')
    assert v.unit_to_base(5,'UNSPECIFIED')[0] is None
    assert v.unit_to_base(5,'TWD',1000)[1]=='UNIT_CONFLICT'


def test_strict_http_budget_including_retries(tmp_path):
    s=Session([FakeResponse(429,retry=1),FakeResponse()]);t=task()
    # The global counter callback refuses to exceed even if adapter wants a retry.
    used=[0]
    def count():
        if used[0]>=1:raise v.SourceError('BUDGET_PAUSED','HTTP_REQUEST_LIMIT')
        used[0]+=1
    with pytest.raises(v.SourceError,match='BUDGET_PAUSED'):
        v.fetch_finmind(s,t,None,max_retries=1,sleeper=lambda _:None,on_request=count)
    assert len(s.calls)==1
