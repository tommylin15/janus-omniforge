import json,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
SRC=REPO/'research/chatgpt' if (REPO/'research/chatgpt').exists() else REPO/'src'
sys.path.insert(0,str(SRC))
import numpy as np
import pandas as pd
import pytest
import janus_precision as p
import janus_train as t

def prices(n=260):
    rows=[];dates=pd.bdate_range('2024-01-01',periods=n)
    for m in ['twse','tpex']:
        for s in ['1101','2330']:
            for i,d in enumerate(dates):
                c=100*np.exp(.001*i+.02*np.sin(i/7))
                rows.append(dict(market=m,symbol=s,trade_date=d,open=c*.999,high=c*1.01,
                    low=c*.99,close=c,volume=1000+i,turnover=c*(1000+i)))
    return pd.DataFrame(rows)

def revenue(n=55):
    rows=[]
    for m in ['twse','tpex']:
        for s in ['1101','2330']:
            for i,d in enumerate(pd.period_range('2020-01',periods=n,freq='M')):
                rows.append(dict(market=m,symbol=s,fiscal_month=str(d),revenue_twd=100+i,
                    published_at=str((d+1).start_time+pd.Timedelta(days=8)),historical_pit='VERIFIED'))
    return pd.DataFrame(rows)

def test_rms_and_daily_gap():
    raw=prices();x,y,_=p.daily(raw)
    a=x.query("market=='twse' and symbol=='1101'").reset_index(drop=True)
    b=y.query("market=='twse' and symbol=='1101'").reset_index(drop=True)
    log=np.log(a.close/a.close.shift(1))
    assert a.loc[100,'vol20']==pytest.approx(np.sqrt(np.mean(log.iloc[81:101]**2)*252))
    assert b.loc[100,'future_rms_vol20']==pytest.approx(np.sqrt(np.mean(log.iloc[101:121]**2)*252))
    assert not np.isclose(a.loc[100,'vol20'],a.loc[100,'realized_vol20'])
    raw=raw.loc[~(raw.symbol.eq('1101') & raw.trade_date.eq(raw.trade_date.unique()[90]))]
    a,b,_=p.daily(raw);a=a.query("market=='twse' and symbol=='1101'").reset_index(drop=True)
    b=b.query("market=='twse' and symbol=='1101'").reset_index(drop=True)
    assert pd.isna(a.loc[95,'atr14_pct'])
    assert pd.isna(a.loc[92,'abs_overnight_gap5'])
    assert pd.isna(b.loc[80,'future_rms_vol20'])
    assert not a.loc[100,'warmup60_ok']

def test_future_does_not_change_x():
    raw=prices();cut=raw.trade_date.unique()[130]
    x,_,_=p.daily(raw)
    edited=raw.copy();sel=edited.trade_date>cut
    edited.loc[sel,['open','high','low','close']]*=.5
    z,_,_=p.daily(edited)
    pd.testing.assert_frame_equal(x.loc[x.trade_date<=cut],z.loc[z.trade_date<=cut])

def test_missing_month_never_bridges_and_label_units():
    raw=revenue();x,y=p.monthly(raw)
    row=y.query("market=='twse' and symbol=='1101' and fiscal_month=='2022-01'").iloc[0]
    assert row.target_next_yoy_pp==pytest.approx(100*((100+25)/(100+13)-1))
    raw=raw.loc[raw.fiscal_month!='2021-12']
    x,y=p.monthly(raw)
    q=x.query("market=='twse' and symbol=='1101' and fiscal_month=='2022-01'").iloc[0]
    assert pd.isna(q.yoy_3m)
    assert pd.isna(q.yoy_change1)
    assert pd.isna(q.revenue_vol3)

def test_strict_missing_and_answer_known():
    raw=revenue();raw['published_at']=None
    z,f=p.training_panel({'revenue':raw},'fundamental','strict')
    assert not z.reason.eq('OK').any()
    raw=revenue();raw.loc[raw.fiscal_month=='2022-01','published_at']='2022-06-01'
    z,f=p.training_panel({'revenue':raw},'fundamental','strict')
    assert z.loc[z.fiscal_month.eq('2022-01'),'reason'].eq('ANSWER_ALREADY_KNOWN').all()

def test_purge_post_counts():
    frame=pd.DataFrame({'signal_group':pd.bdate_range('2020-01-01',periods=320)})
    frame['signal_at']=frame.signal_group;frame['mature_at']=frame.signal_group+pd.offsets.BDay(20);frame['symbol']='1101'
    masks,meta=t.split(frame,'risk');assert masks is not None
    a,b,c=masks
    assert frame.loc[a,'mature_at'].max()<frame.loc[b,'signal_at'].min()
    assert frame.loc[b,'mature_at'].max()<frame.loc[c,'signal_at'].min()
    assert not (a&b).any() and not (b&c).any()

def test_valuation_mapping_cannot_inject_price():
    v=pd.DataFrame([dict(symbol='1101',market='twse',trade_date='2025-01-31',pe_ratio=10,pb_ratio=1)])
    z,cols=p.valuation_panel({'valuation':v},{})
    assert z.reason.str.startswith('BLOCKED').all()
    assert not set(cols)&{'pe_ratio','pb_ratio','close','market_cap','eps','bvps'}
    with pytest.raises(ValueError,match='ALLOWLIST'):
        p.valuation_panel({'valuation':v},{'metrics':{'close':{}}})

def test_financial_asof_and_cohort():
    v=pd.DataFrame([dict(symbol='1101',market='twse',trade_date='2025-01-31',pe_ratio=10,pb_ratio=1),
                    dict(symbol='1101',market='twse',trade_date='2025-02-28',pe_ratio=11,pb_ratio=1.1)])
    f=pd.DataFrame([dict(symbol='1101',market='twse',dataset='ratio',item='ROE',unit_basis='RATIO',period_basis='TTM',
                        historical_pit='VERIFIED',published_at='2025-02-10',value=.1)])
    z,_=p.valuation_panel({'valuation':v,'financials':f},{'metrics':{'roe':dict(dataset='ratio',item='ROE',unit_basis='RATIO',period_basis='TTM',evidence='fixture')}})
    assert pd.isna(z.iloc[0].roe);assert z.iloc[1].roe==.1

def make_release(tmp,data):
    root=tmp/'input';rel=root/'canonical/release-1234567890abcdef';rel.mkdir(parents=True)
    files={}
    for kind,frame in data.items():
        (rel/kind).mkdir();dest=rel/kind/'test.parquet';frame.to_parquet(dest,index=False)
        files[kind+'/test.parquet']={'rows':len(frame),'sha256':p.sha(dest)}
    p.write_json(rel/'manifest.json',{'files':files,'publication_allowed':False,'status':'RESEARCH_DATA_ONLY',
        'format':'parquet','release_id':'1234567890abcdef'})
    p.write_json(root/'canonical/CURRENT.json',{'release':rel.name,'format':'parquet','manifest':'canonical/'+rel.name+'/manifest.json'})
    return root

def test_release_hash_and_x_y_export(tmp_path):
    pytest.importorskip('pyarrow', reason='real Parquet engine required')
    root=make_release(tmp_path,{'ohlcv':prices(),'revenue':revenue()})
    before=p.sha(root/'canonical/CURRENT.json');out,m=p.export_dataset(root)
    assert p.sha(root/'canonical/CURRENT.json')==before
    assert not any(c.startswith(('future','target','forward','label')) for c in pd.read_parquet(out/'daily_X.parquet'))
    assert p.export_dataset(root)[0]==out
    f=root/'canonical/release-1234567890abcdef/ohlcv/test.parquet';f.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='HASH'):p.load_release(root)

@pytest.mark.parametrize('role',['quant','risk','fundamental'])
def test_three_models_fit_reload_and_cache(tmp_path,role):
    pytest.importorskip('pyarrow', reason='real Parquet engine required')
    root=make_release(tmp_path,{'ohlcv':prices(400),'revenue':revenue(70)})
    report,out=t.run(root,tmp_path/'out',role,max_trees=8)
    assert report['state']=='RESEARCH_EVALUATED',report
    assert report['publication_allowed'] is False
    assert (out/'models/main/model.ubj').is_file()
    assert t.run(root,tmp_path/'out',role,max_trees=8)[0]==report

def test_valuation_fit_two_targets_separate_cohorts(tmp_path):
    pytest.importorskip('pyarrow', reason='real Parquet engine required')
    rows=[]
    for i,d in enumerate(pd.date_range('2020-01-31',periods=48,freq='ME')):
        for j in range(12):
            rows.append(dict(market='twse',symbol=str(1100+j),signal_group=d.to_period('M').start_time,
                signal_at=d,mature_at=d,reason='OK',roe=.1+j*.001,debt_ratio=.3,
                log_total_assets=10+j/10,revenue_yoy=i/100,market_code=0.,
                y_pe=np.log(10+i/100+j/10),y_pb=np.log(1+j/100)))
    d=pd.DataFrame(rows)
    for target in ['y_pe','y_pb']:
        r=t.fit_one(d,p.VAL,'valuation',tmp_path/target,target,max_trees=8)
        assert r['state']=='RESEARCH_EVALUATED'
        assert (tmp_path/target/'model.ubj').is_file()
