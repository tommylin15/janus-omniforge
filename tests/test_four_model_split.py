"""v3.8.2 separated Colab collector / ChatGPT labeler contract tests.

Parquet integration requires pyarrow; if unavailable those tests skip explicitly.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

BASE=Path(__file__).resolve().parents[1]
SRC=BASE/'research/chatgpt' if (BASE/'research/chatgpt').exists() else BASE/'src'
COLAB=BASE/'research/colab' if (BASE/'research/colab').exists() else BASE
sys.path.insert(0,str(SRC))
import janus_precision as p
from label_four_models import run


def _nb():
    return json.loads((COLAB/'00_資料收集_v3.8.2_Colab.ipynb').read_text(encoding='utf-8'))


def test_colab_notebook_parses_compiles_and_has_no_research_y():
    n=_nb()
    code='\n'.join(''.join(c['source']) for c in n['cells'] if c['cell_type']=='code')
    for i,c in enumerate(n['cells']):
        if c['cell_type']=='code':compile(''.join(c['source']),f'cell_{i}', 'exec')
    assert 'drive.mount' in code
    assert 'build_canonical' in code and 'BatchCollector' in code
    assert 'FACTOR_BUILD' not in code
    assert 'export_dataset' not in code
    assert 'future_rms_vol20' not in code
    assert 'target_next_yoy_pp' not in code
    assert n['metadata']['janus']['labels_in_notebook'] is False
    assert n['metadata']['janus']['stage']=='collect_only'


def test_labeler_does_not_import_colab_or_use_requests():
    code=(SRC/'label_four_models.py').read_text(encoding='utf-8')
    assert 'google.colab' not in code
    assert 'requests' not in code
    assert 'urlopen' not in code
    assert 'current_sha256' in (SRC/'janus_precision.py').read_text()


def test_output_must_not_point_to_canonical(tmp_path):
    data=tmp_path/'input';(data/'canonical').mkdir(parents=True)
    (data/'canonical/CURRENT.json').write_text('{}')
    with pytest.raises(ValueError,match='OUTPUT_MUST_NOT'):
        run(data,data)
    with pytest.raises(ValueError,match='OUTPUT_MUST_NOT'):
        run(data,data/'canonical'/'new')
    with pytest.raises(ValueError,match='OUTPUT_MUST_NOT'):
        run(data,data/'data'/'derived')


def test_missing_real_dataset_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError,match='CURRENT.json'):
        run(tmp_path/'input',tmp_path/'output')


def test_out_of_budget_rejected(tmp_path):
    with pytest.raises(ValueError,match='ROW_LIMIT'):
        run(tmp_path/'input',tmp_path/'output',max_rows=10_000_000)


def _prices(n=150):
    dates=pd.bdate_range('2024-01-01',periods=n)
    rows=[]
    for m in ['twse','tpex']:
        for s in ['1101','2330']:
            for i,d in enumerate(dates):
                v=100*np.exp(.001*i+.02*np.sin(i/7))
                rows.append(dict(market=m,symbol=s,trade_date=d,open=v*.999,
                                 high=v*1.01,low=v*.99,close=v,volume=1000+i,turnover=v*(1000+i)))
    return pd.DataFrame(rows)


def _revenue(n=50):
    return pd.DataFrame([dict(market='twse',symbol='1101',fiscal_month=str(d),
          revenue_twd=100+i,published_at=str((d+1).start_time+pd.Timedelta(days=8)),historical_pit='VERIFIED')
          for i,d in enumerate(pd.period_range('2021-01',periods=n,freq='M'))])


def _release(tmp_path):
    pytest.importorskip('pyarrow')
    root=tmp_path/'JanusDataset_v3_202610'
    rel=root/'canonical/release-1234567890abcdef';rel.mkdir(parents=True)
    files={}
    for kind,df in [('ohlcv',_prices()),('revenue',_revenue())]:
        d=rel/kind;d.mkdir();f=d/'part.parquet';df.to_parquet(f,index=False)
        files[f'{kind}/part.parquet']={'sha256':p.sha(f),'rows':len(df)}
    p.write_json(rel/'manifest.json',dict(format='parquet',files=files,publication_allowed=False,
                                        status='RESEARCH_DATA_ONLY',release_id='1234567890abcdef'))
    p.write_json(root/'canonical/CURRENT.json',dict(release=rel.name,format='parquet',
                manifest='canonical/'+rel.name+'/manifest.json'))
    return root


def test_real_parquet_immutable_export_and_replay(tmp_path):
    root=_release(tmp_path);out_root=tmp_path/'ChatGPT'
    before=p.sha(root/'canonical/CURRENT.json')
    verified=run(root,out_root,verify_only=True)
    assert verified['state']=='INPUT_VERIFIED_ONLY'
    assert not out_root.exists()
    r=run(root,out_root)
    assert r['state']=='RESEARCH_DERIVED_NOT_PROMOTABLE'
    assert r['publication_allowed'] is False
    assert r['version']=='3.8.2'
    assert p.sha(root/'canonical/CURRENT.json')==before
    output=Path(r['output'])
    assert output.is_relative_to(out_root)
    assert (output/'daily_X.parquet').exists()
    assert (output/'price_Y.parquet').exists()
    assert (output/'revenue_Y.parquet').exists()
    daily=pd.read_parquet(output/'daily_X.parquet')
    labels=pd.read_parquet(output/'price_Y.parquet')
    assert 'future_rms_vol20' in labels and 'future_rms_vol20' not in daily
    assert not any(c.startswith('target_') for c in daily)
    assert run(root,out_root)['output']==r['output']
    (root/'canonical/release-1234567890abcdef/ohlcv/part.parquet').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='HASH'):
        run(root,out_root)


def test_price_and_revenue_future_gaps_never_bridge():
    raw=_prices();cut=raw.trade_date.unique()[90]
    x,y,_=p.daily(raw)
    alt=raw.copy();alt.loc[alt.trade_date>cut,'close']*=0.7
    xx,_,_=p.daily(alt)
    pd.testing.assert_frame_equal(x.loc[x.trade_date<=cut].reset_index(drop=True),
                                  xx.loc[xx.trade_date<=cut].reset_index(drop=True))
    missing=_revenue().loc[lambda d:d.fiscal_month!='2022-12']
    a,b=p.monthly(missing)
    row=a.loc[a.fiscal_month=='2023-01'].iloc[0]
    assert pd.isna(row.yoy_3m)
    assert 'target_next_yoy_pp' not in a
    assert 'target_next_yoy_pp' in b
