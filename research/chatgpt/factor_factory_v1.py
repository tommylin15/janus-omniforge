"""D07 research-only four-role feature factory.

Immutable canonical INPUT -> versioned derived/output ONLY. No canonical CURRENT mutation.
Never forward-fill missing observations or backdate publication timestamps.
No Y column enters the daily X feature table. External/time-uncertified factors
are kept separate until each model's PIT + serving feature gate is verified.
"""
from __future__ import annotations
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

FACTORY_VERSION = 'four-model-research-feature-v1'
KEY = ['market', 'symbol']
PRICE_WINDOWS = (5, 10, 20, 60, 120)
LABEL_HORIZONS = (5, 20)


def _numeric(s):
    return pd.to_numeric(s, errors='coerce').replace([np.inf, -np.inf], np.nan)


def _ratio(a, b):
    return (a / b.where(b.abs() > 1e-12)).replace([np.inf, -np.inf], np.nan)


def _require(df, columns, name):
    absent = set(columns) - set(df.columns)
    if absent:
        raise ValueError(f'{name}: missing required fields: {sorted(absent)}')


def _unique(df, columns, name):
    if df.duplicated(columns).any():
        raise ValueError(f'{name}: duplicate keys {columns}')


def _pct(s, n):
    return s / s.shift(n) - 1


def _std(s, n):
    return s.pct_change(fill_method=None).rolling(n, min_periods=n).std(ddof=0)


def build_ohlcv_panel(raw: pd.DataFrame):
    """Return (daily X, separate price/outcome candidate Y, breadth).

    All history is only research-qualified until survivorship, actions and PIT
    are controlled. Trading-day index is market-specific, *not* nth stock row.
    """
    _require(raw, KEY + ['trade_date','open','high','low','close','volume','turnover'], 'ohlcv')
    x = raw[KEY + ['trade_date','open','high','low','close','volume','turnover']].copy()
    x[KEY] = x[KEY].astype(str)
    x['trade_date'] = pd.to_datetime(x['trade_date'], errors='raise').dt.normalize()
    _unique(x, KEY + ['trade_date'], 'ohlcv')
    x.sort_values(KEY + ['trade_date'], inplace=True)
    for field in ['open','high','low','close','volume','turnover']:
        x[field] = _numeric(x[field])
    ok = (x['close']>0) & (x['open']>0) & (x['high']>=x[['open','close']].max(axis=1)) & (x['low']<=x[['open','close']].min(axis=1)) & (x['low']>0) & (x['volume']>=0) & (x['turnover']>=0)
    x['ohlcv_eligible'] = ok
    # Explicitly null suspect values; do not hide entire rows or invent zeros.
    x.loc[~ok,['open','high','low','close','volume','turnover']] = np.nan
    cal = x[['market','trade_date']].drop_duplicates().sort_values(['market','trade_date'])
    cal['session_index'] = cal.groupby('market').cumcount().astype('int32')
    x = x.merge(cal,on=['market','trade_date'],validate='many_to_one',how='left')
    grp=x.groupby(KEY,sort=False,observed=True)
    close=x['close']; op=x['open']; high=x['high']; low=x['low']
    x['ret1'] = grp['close'].pct_change(fill_method=None)
    x['logret1'] = np.log(close).groupby([x['market'],x['symbol']]).diff()
    x['intraday_ret'] = _ratio(close,op)-1
    x['range_pct'] = _ratio(high-low,close)
    prevclose=grp['close'].shift(1)
    x['overnight_gap'] = _ratio(op,prevclose)-1
    true_range=pd.concat([high-low,(high-prevclose).abs(),(low-prevclose).abs()],axis=1).max(axis=1)
    true_range[high.isna() | low.isna() | prevclose.isna()]=np.nan
    x['true_range'] = true_range
    x['dollar_liquidity'] = x['turnover']
    x['amihud_illiquidity'] = _ratio(x['ret1'].abs(), x['turnover'])
    for n in PRICE_WINDOWS:
        # Grouped rolling by stock, using row calculations AND a session-index guard.
        session_start=grp['session_index'].shift(n)
        contiguous=(x['session_index']-session_start)==n
        in_window=(x['session_index']-grp['session_index'].shift(n-1))==n-1
        x[f'session_window_{n}_ok']=contiguous
        x[f'ret{n}']=_ratio(close,grp['close'].shift(n)).sub(1).where(contiguous)
        grp_close=x.groupby(KEY,sort=False,observed=True)['close']
        rmean=grp_close.transform(lambda s:s.rolling(n,min_periods=n).mean())
        x[f'ma{n}_distance']=_ratio(close,rmean).sub(1).where(in_window)
        vmean=grp['volume'].transform(lambda s:s.rolling(n,min_periods=n).mean())
        vstd=grp['volume'].transform(lambda s:s.rolling(n,min_periods=n).std(ddof=0))
        x[f'volume_mean{n}']=vmean.where(in_window)
        x[f'volume_std{n}']=vstd.where(in_window)
        x[f'volume_sum{n}']=grp['volume'].transform(lambda s:s.rolling(n,min_periods=n).sum()).where(in_window)
        x[f'turnover_sum{n}']=grp['turnover'].transform(lambda s:s.rolling(n,min_periods=n).sum()).where(in_window)
        x[f'turnover_mean{n}']=grp['turnover'].transform(lambda s:s.rolling(n,min_periods=n).mean()).where(in_window)
        x[f'realized_vol{n}']=grp['logret1'].transform(lambda s:s.rolling(n,min_periods=n).std(ddof=0) * math.sqrt(252)).where(contiguous)
        rolling_high=grp['close'].transform(lambda s:s.rolling(n,min_periods=n).max())
        rolling_low=grp['close'].transform(lambda s:s.rolling(n,min_periods=n).min())
        x[f'drawdown_from_high{n}']=_ratio(close,rolling_high).sub(1).where(in_window)
        x[f'close_position{n}']=_ratio(close-rolling_low,rolling_high-rolling_low).where(in_window)
        x[f'up_days_sum{n}']=(x['ret1']>0).where(x['ret1'].notna()).groupby([x['market'],x['symbol']]).transform(lambda s:s.rolling(n,min_periods=n).sum()).where(contiguous)
    x['volume_ratio20'] = _ratio(x['volume'], grp['volume'].transform(lambda s:s.shift(1).rolling(20,min_periods=20).mean())).where(x['session_window_20_ok'])
    x['atr14_pct'] = _ratio(grp['true_range'].transform(lambda s:s.rolling(14,min_periods=14).mean()),close)
    x['turnover_log20'] = np.log1p(x['turnover_mean20'].where(x['turnover_mean20']>=0))
    x['volume_change_5_20'] = _ratio(x['volume_mean5'],x['volume_mean20'])-1
    x['turnover_change_5_20'] = _ratio(x['turnover_mean5'],x['turnover_mean20'])-1
    x['abs_overnight_gap5']=grp['overnight_gap'].transform(lambda q:q.abs().rolling(5,min_periods=5).mean())
    x['overnight_gap_sum20']=grp['overnight_gap'].transform(lambda q:q.rolling(20,min_periods=20).sum())
    x['downside_vol20']=grp['logret1'].transform(lambda q:q.clip(upper=0).pow(2).rolling(20,min_periods=20).mean().pow(.5)*math.sqrt(252)).where(x['session_window_20_ok'])
    x['worst_daily_ret20']=grp['ret1'].transform(lambda q:q.rolling(20,min_periods=20).min()).where(x['session_window_20_ok'])
    x['mean_reversion5']=x['ret5'].mul(-1)
    x['bollinger_z20']=_ratio(close-grp_close.transform(lambda s:s.rolling(20,min_periods=20).mean()),grp_close.transform(lambda s:s.rolling(20,min_periods=20).std(ddof=0)))
    # Explicit VWAP from turnover (TWD) / volume (shares), not mean close.
    x['vwap20']=_ratio(x['turnover_sum20'],x['volume_sum20'])
    x['close_to_vwap20']=_ratio(close,x['vwap20'])-1
    changes=close-prevclose
    gains=changes.clip(lower=0)
    losses=(-changes).clip(lower=0)
    avg_gain=gains.groupby([x['market'],x['symbol']]).transform(lambda q:q.rolling(14,min_periods=14).mean())
    avg_loss=losses.groupby([x['market'],x['symbol']]).transform(lambda q:q.rolling(14,min_periods=14).mean())
    x['rsi14']=100-100/(1+_ratio(avg_gain,avg_loss))
    # EMA momentum is based only on the current and preceding observations.
    ema12=grp_close.transform(lambda q:q.ewm(span=12,adjust=False,min_periods=12).mean())
    ema26=grp_close.transform(lambda q:q.ewm(span=26,adjust=False,min_periods=26).mean())
    x['macd12_26']=ema12-ema26
    x['macd_signal9']=x.groupby(KEY,sort=False)['macd12_26'].transform(lambda q:q.ewm(span=9,adjust=False,min_periods=9).mean())
    x['macd_hist9']=x['macd12_26']-x['macd_signal9']
    # Cross-sectional statistics computed from *this* day's available regular universe.
    for col in ['ret20','ret60','realized_vol20','turnover_mean20']:
        x[col+'_market_rank']=x.groupby(['market','trade_date'])[col].rank(pct=True)
    # Market breadth needs a historical PIT survivor caveat. It is a research context, not an index.
    market=x.groupby(['market','trade_date'],sort=True,observed=True).agg(
        n_stock=('symbol','nunique'),n_ret1=('ret1','count'),
        n_up=('ret1',lambda s:int((s>0).sum())),
        n_ma20=('ma20_distance','count'),
        n_above_ma20=('ma20_distance',lambda s:int((s>0).sum())),
        n_ma60=('ma60_distance','count'),
        n_above_ma60=('ma60_distance',lambda s:int((s>0).sum())),
        turnover_total=('turnover','sum')).reset_index()
    market['breadth_up_ratio']=_ratio(market['n_up'],market['n_ret1'])
    market['breadth_above_ma20']=_ratio(market['n_above_ma20'],market['n_ma20'])
    market['breadth_above_ma60']=_ratio(market['n_above_ma60'],market['n_ma60'])
    market['historical_universe_status']='CURRENT_OR_OBSERVED_RESEARCH_NON_PIT'
    # Do not join cross-date future Y into a model input X frame.
    y=x[KEY+['trade_date','session_index','close','logret1']].copy()
    g=y.groupby(KEY,sort=False,observed=True)
    for n in LABEL_HORIZONS:
        end_index=g['session_index'].shift(-n)
        is_complete=(end_index-y['session_index']==n)
        future_date=g['trade_date'].shift(-n)
        y[f'mature_session_{n}']=future_date.where(is_complete)
        y[f'forward_return_{n}']=(_ratio(g['close'].shift(-n),y['close'])-1).where(is_complete)
        y[f'forward_up_{n}']=np.where(y[f'forward_return_{n}'].notna(),
                                      y[f'forward_return_{n}']>0,np.nan)
    n=20
    future_vol=g['logret1'].transform(lambda s:s.iloc[::-1].rolling(n,min_periods=n).std(ddof=0).iloc[::-1].shift(-1)*math.sqrt(252))
    y['future_realized_vol20']=future_vol.where(y['mature_session_20'].notna())
    y['label_state']='RESEARCH_CANDIDATE_NOT_PIT_CERTIFIED'
    x.drop(columns=['logret1','true_range'],inplace=True)
    y.drop(columns=['close','logret1'],inplace=True)
    x['historical_pit']='NOT_VERIFIED'
    x['publication_allowed']=False
    return x,y,market


def build_revenue_panel(raw: pd.DataFrame):
    _require(raw,KEY+['fiscal_month','revenue_twd','published_at'],'revenue')
    x=raw[KEY+['fiscal_month','revenue_twd','published_at','historical_pit']].copy() if 'historical_pit' in raw else raw[KEY+['fiscal_month','revenue_twd','published_at']].copy()
    x['fiscal_month']=pd.PeriodIndex(x['fiscal_month'].astype(str),freq='M').astype(str)
    _unique(x,KEY+['fiscal_month'],'revenue')
    x=x.sort_values(KEY+['fiscal_month']).copy()
    x['revenue_twd']=_numeric(x['revenue_twd'])
    x.loc[x['revenue_twd']<0,'revenue_twd']=np.nan
    g=x.groupby(KEY,sort=False)
    month_num=pd.PeriodIndex(x['fiscal_month'],freq='M').asi8
    for n in (1,3,6,12):
        x[f'revenue_sum{n}m']=g['revenue_twd'].transform(lambda s:s.rolling(n,min_periods=n).sum())
        x[f'revenue_mean{n}m']=g['revenue_twd'].transform(lambda s:s.rolling(n,min_periods=n).mean())
        lag=g['revenue_twd'].shift(n)
        prev_month=g['fiscal_month'].shift(n)
        elapsed=(month_num-pd.PeriodIndex(prev_month.fillna('1970-01'),freq='M').asi8)
        x[f'revenue_growth_{n}m']=(_ratio(x['revenue_twd'],lag)-1).where(elapsed==n)
    x['revenue_yoy']=x['revenue_growth_12m']
    x['revenue_yoy_delta']=x['revenue_yoy']-g['revenue_yoy'].shift(1)
    x['revenue_sum3m_yoy']=(_ratio(x['revenue_sum3m'],g['revenue_sum3m'].shift(12))-1)
    x['revenue_sum12m_yoy']=(_ratio(x['revenue_sum12m'],g['revenue_sum12m'].shift(12))-1)
    x['published_at_verified']=pd.to_datetime(x['published_at'],errors='coerce',utc=True,format='mixed').notna()
    x['pit_eligible']=x['published_at_verified'] & (x.get('historical_pit','NOT_VERIFIED')=='VERIFIED')
    # Research label for *next* fiscal month, isolated from model X and unpromotable without actual publication date.
    fut_month=g['fiscal_month'].shift(-1)
    elapsed_fwd=pd.PeriodIndex(fut_month.fillna('1970-01'),freq='M').asi8-month_num
    y=x[KEY+['fiscal_month']].copy()
    y['target_next_fiscal_month']=fut_month.where(elapsed_fwd==1)
    y['label_next_revenue_yoy']=g['revenue_yoy'].shift(-1).where(elapsed_fwd==1)
    y['label_published_at']=g['published_at'].shift(-1).where(elapsed_fwd==1)
    y['label_maturity_verified']=pd.to_datetime(y['label_published_at'],errors='coerce',utc=True,format='mixed').notna()
    y['status']='RESEARCH_CANDIDATE_NOT_PIT_CERTIFIED'
    x['publication_allowed']=False
    return x,y


def build_valuation_panel(raw:pd.DataFrame):
    _require(raw,KEY+['trade_date','pe_ratio','pb_ratio','published_at'],'valuation')
    x=raw[KEY+['trade_date','pe_ratio','pb_ratio','published_at']].copy()
    x['trade_date']=pd.to_datetime(x['trade_date'],errors='raise').dt.normalize()
    _unique(x,KEY+['trade_date'],'valuation')
    x.sort_values(KEY+['trade_date'],inplace=True)
    x['pe_ratio']=_numeric(x['pe_ratio']); x['pb_ratio']=_numeric(x['pb_ratio'])
    for col in ('pe_ratio','pb_ratio'):
        x[col]=x[col].where(x[col]>0)
    for col in ('pe_ratio','pb_ratio'):
        g=x.groupby(KEY,sort=False)[col]
        for n in (3,6,12):
            x[f'{col}_obs_mean_{n}']=g.transform(lambda s:s.rolling(n,min_periods=n).mean())
            x[f'{col}_obs_min_{n}']=g.transform(lambda s:s.rolling(n,min_periods=n).min())
            x[f'{col}_obs_max_{n}']=g.transform(lambda s:s.rolling(n,min_periods=n).max())
        x[f'{col}_market_rank']=x.groupby(['market','trade_date'])[col].rank(pct=True)
    x['published_at_verified']=pd.to_datetime(x['published_at'],errors='coerce',utc=True,format='mixed').notna()
    x['pit_eligible']=False  # requires genuine first publication/version evidence, not today's observed date
    # Current PE/PB are *targets* for Valuation, cannot enter the same model's X.
    y=x[KEY+['trade_date']].copy()
    y['target_log_pe']=np.log(x['pe_ratio'])
    y['target_log_pb']=np.log(x['pb_ratio'])
    y['status']='RESEARCH_CANDIDATE_NOT_PIT_CERTIFIED'
    x['publication_allowed']=False
    return x,y


FINANCIAL_ITEMS={
 'balance':{'assets':'資產總計','liabilities':'負債總計','equity':'權益總計','current_assets':'流動資產','current_liabilities':'流動負債','cash':'現金及約當現金','bvps':'每股參考淨值'},
 'income':{'sales':'營業收入','gross_profit':'營業毛利（毛損）','op_profit':'營業利益（損失）','net_income':'本期淨利（淨損）','eps':'基本每股盈餘（元）'},
 'cashflow':{'operating_cashflow':'營業活動之淨現金流入（流出）','investing_cashflow':'投資活動之淨現金流入（流出）','financing_cashflow':'籌資活動之淨現金流入（流出）'}
}


def build_financial_panel(raw:pd.DataFrame):
    _require(raw,KEY+['fiscal_quarter','dataset','item','value','published_at','unit_basis','period_basis'],'financials')
    x=raw[KEY+['fiscal_quarter','dataset','item','value','published_at','unit_basis','period_basis']].copy()
    x['value']=_numeric(x['value'])
    x['fiscal_quarter']=x['fiscal_quarter'].astype(str)
    out=x[KEY+['fiscal_quarter']].drop_duplicates().copy()
    summaries=[]
    for family, names in FINANCIAL_ITEMS.items():
        for code, field in names.items():
            part=x.loc[(x['dataset']==family)&(x['item']==field),KEY+['fiscal_quarter','value','unit_basis','period_basis','published_at']]
            # Ambiguous source revisions, unit or periods: do not silently use arbitrary first record.
            duplicates=part.duplicated(KEY+['fiscal_quarter'],keep=False)
            if duplicates.any():
                summaries.append({'factor':code,'status':'DUPLICATE_SOURCE_ROWS','rows':int(duplicates.sum())})
                continue
            part=part.rename(columns={'value':'fin_raw_'+code})
            out=out.merge(part[KEY+['fiscal_quarter','fin_raw_'+code]],on=KEY+['fiscal_quarter'],how='left',validate='one_to_one')
            summaries.append({'factor':code,'status':'RAW_UNIT_AND_PERIOD_BASIS_UNVERIFIED','rows':len(part)})
    if all(s in out for s in ('fin_raw_assets','fin_raw_liabilities')):
        out['fin_debt_to_assets_raw']=_ratio(out['fin_raw_liabilities'],out['fin_raw_assets'])
    if all(s in out for s in ('fin_raw_current_assets','fin_raw_current_liabilities')):
        out['fin_current_ratio_raw']=_ratio(out['fin_raw_current_assets'],out['fin_raw_current_liabilities'])
    # Do not divide mismatched currencies/accounting bases for income margins automatically.
    out['published_at_verified']=False
    out['pit_eligible']=False
    out['status']='RESEARCH_RAW_FINANCIAL_PERIOD_AND_PUBLICATION_UNVERIFIED'
    out['publication_allowed']=False
    return out,pd.DataFrame(summaries)



def build_market_index_panel(raw:pd.DataFrame):
    """Only an index-specific research panel; publication/timing requires separate gate."""
    _require(raw,['market','trade_date','index_id','close','available_at'],'market_index')
    x=raw[['market','trade_date','index_id','close','available_at']].copy()
    x['trade_date']=pd.to_datetime(x['trade_date'],errors='raise').dt.normalize()
    _unique(x,['market','trade_date','index_id'],'market_index')
    x.sort_values(['market','index_id','trade_date'],inplace=True)
    x['close']=_numeric(x['close']).where(lambda s:s>0)
    g=x.groupby(['market','index_id'],sort=False)
    for n in PRICE_WINDOWS:
        x[f'index_ret{n}']=g['close'].pct_change(n,fill_method=None)
        x[f'index_vol{n}']=g['close'].transform(lambda s:np.log(s).diff().rolling(n,min_periods=n).std(ddof=0)*math.sqrt(252))
        x[f'index_ma{n}_distance']=_ratio(x['close'],g['close'].transform(lambda s:s.rolling(n,min_periods=n).mean()))-1
    x['available_at_verified']=pd.to_datetime(x['available_at'],errors='coerce',utc=True,format='mixed').notna()
    x['pit_eligible']=False  # no proof relative to the model EOD cutoff
    x['status']='MARKET_CONTEXT_RESEARCH_NON_PIT'
    x['publication_allowed']=False
    return x


def build_industry_panel(daily:pd.DataFrame,membership:pd.DataFrame):
    """Only use dated, historically observed membership; never retrofit current industry."""
    _require(membership,KEY+['industry_code','valid_from','valid_to','first_observed_at'],'industry_membership')
    members=membership[KEY+['industry_code','valid_from','valid_to','first_observed_at']].copy()
    for key in ['valid_from','valid_to','first_observed_at']:
        members[key]=pd.to_datetime(members[key],errors='coerce',utc=True,format='mixed').dt.tz_convert(None).dt.normalize()
    if members['valid_from'].isna().any() or members['first_observed_at'].isna().any():
        raise ValueError('undated historical industry membership denied')
    z=daily[KEY+['trade_date','ret1','ret20','ret60','realized_vol20','turnover']].copy()
    z=z.merge(members,on=KEY,how='inner',validate='many_to_many')
    valid=(z['trade_date']>=z['valid_from']) & (z['trade_date']>=z['first_observed_at']) & (
           z['valid_to'].isna() | (z['trade_date']<z['valid_to']))
    z=z.loc[valid].copy()
    if z.duplicated(KEY+['trade_date']).any():
        raise ValueError('overlapping industry membership intervals')
    if z.empty:return pd.DataFrame(columns=['market','industry_code','trade_date'])
    out=z.groupby(['market','industry_code','trade_date'],sort=True).agg(
       n_stocks=('symbol','nunique'),industry_ret1_equal_mean=('ret1','mean'),
       industry_ret20_equal_mean=('ret20','mean'),industry_ret60_equal_mean=('ret60','mean'),
       industry_vol20_equal_mean=('realized_vol20','mean'),
       industry_dispersion20=('ret20','std'),industry_turnover=('turnover','sum')).reset_index()
    out['membership_status']='HISTORICAL_VALID_FROM_AND_FIRST_OBSERVED_CHECKED'
    out['publication_allowed']=False
    return out


def build_corporate_event_panel(raw:pd.DataFrame):
    """Events remain separate and UNADJUSTED; never infer split/dividend multiplier."""
    _require(raw,KEY+['dataset','event_payload_json','published_at'],'corporate_actions')
    records=[]
    for row in raw[KEY+['dataset','event_payload_json','published_at']].itertuples(index=False):
        try:
            payload=json.loads(row.event_payload_json)
        except (TypeError,ValueError) as e:
            raise ValueError('corporate event payload cannot be parsed') from e
        if not isinstance(payload,dict):raise ValueError('corporate event payload must be object')
        date_value=payload.get('date') or payload.get('provider_date')
        try:
            when=pd.to_datetime(date_value,errors='raise').normalize()
        except (TypeError, ValueError) as e:
            raise ValueError('corporate event invalid source date') from e
        records.append({'market':row.market,'symbol':row.symbol,'event_date':when,
                        'event_kind':row.dataset,'provider_event_type':payload.get('type'),
                        'adjustment_status':payload.get('adjustment_status','NOT_VERIFIED'),
                        'return_basis':payload.get('return_basis'),
                        'published_at':row.published_at,
                        'source_available_at':payload.get('available_at'),
                        'action_multiplier':np.nan,
                        'pit_eligible':False,'publication_allowed':False})
    result=pd.DataFrame.from_records(records)
    if not result.empty:result.sort_values(KEY+['event_date'],inplace=True)
    return result

def build_factory(root:Path,*, max_rows:int=1500000, chunked:bool=True):
    """Create research derivative only; fail closed if already complete. Never change CURRENT.

    Cross-subject PIT joins are intentionally absent: instead emit compatible
    keyed panels pending validated announcement/membership historical snapshots.
    """
    root=Path(root)
    pointer=root/'canonical'/'CURRENT.json'
    rawptr=pointer.read_bytes()
    spec=json.loads(rawptr)
    release_ref=spec.get('manifest') or spec.get('manifest_path')
    if not isinstance(release_ref,str):
        raise ValueError('CURRENT has no manifest path')
    if Path(release_ref).is_absolute() or '..' in Path(release_ref).parts:
        raise ValueError('unsafe manifest reference')
    manifest_path=root/'canonical'/release_ref if not release_ref.startswith('canonical/') else root/release_ref
    if not manifest_path.exists():
        raise FileNotFoundError(f'CURRENT manifest missing: {manifest_path}')
    manifestbytes=manifest_path.read_bytes()
    manifest=json.loads(manifestbytes)
    if manifest.get('status') not in ('RESEARCH_DATA_ONLY','RESEARCH_ONLY') or manifest.get('publication_allowed') is not False:
        raise ValueError('unexpected canonical research status')
    release=manifest_path.parent
    digest=hashlib.sha256(rawptr+b'\0'+manifestbytes+b'\0'+FACTORY_VERSION.encode()).hexdigest()[:16]
    output=root/'derived'/'four_model_features'/f'{FACTORY_VERSION}-{digest}'
    done=output/'receipt.json'
    if done.exists():
        old=json.loads(done.read_text())
        if old.get('status')=='RESEARCH_FEATURES_BUILT' and old.get('input_id')==digest:
            # Verify actual output bytes before SKIPPED_EXISTING.
            for file, info in old.get('artifacts',{}).items():
                data=(output/file).read_bytes()
                if hashlib.sha256(data).hexdigest()!=info['sha256']:
                    raise ValueError('existing feature artifact hash mismatch: '+file)
            return old
    output.mkdir(parents=True,exist_ok=True)
    artifacts={};statuses={};catalog={}
    def save(key, df):
        name=key+'.parquet';dest=output/name
        if dest.exists():
            raise ValueError('incomplete pre-existing run: '+str(dest))
        df.to_parquet(dest,index=False)
        artifacts[name]={'rows':int(len(df)),'cols':int(len(df.columns)),
                         'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
        catalog[name]={'candidate_roles':['quant','risk_v3','fundamental','valuation'],
                       'semantics':'LABEL_OUTCOME_ONLY_DO_NOT_USE_AS_X' if ('_Y_' in name) else 'RESEARCH_X_OR_CONTEXT_NOT_PIT_CERTIFIED',
                       'columns':list(df.columns),'n_rows':int(len(df)),
                       'publication_allowed':False} 
    # Manifest verifies *all* source sha256, not just first and last month.
    actual_files=manifest.get('files',{})
    def read_kind(kind):
        parts=[]
        for rel,ref in sorted(actual_files.items()):
            if not rel.startswith(kind+'/') or not rel.endswith('.parquet'): continue
            p=release/rel
            data=p.read_bytes();expected=ref.get('sha256')
            if hashlib.sha256(data).hexdigest()!=expected:
                raise ValueError('source SHA mismatch '+rel)
            part=pd.read_parquet(p)
            if len(part)!=ref.get('rows'):raise ValueError('source row count mismatch '+rel)
            parts.append(part)
        if not parts:return None
        merged=pd.concat(parts,ignore_index=True)
        if len(merged)>max_rows:raise ValueError('bounded factory input row limit '+kind)
        return merged
    raw=read_kind('ohlcv')
    if raw is not None:
        xd,yd,br=build_ohlcv_panel(raw)
        save('ohlcv_daily_X_research_non_pit',xd)
        save('price_future_Y_candidates_not_X',yd)
        save('market_breadth_research_non_pit',br)
        statuses['ohlcv']='DERIVED_RESEARCH_NOT_PIT'
    rev=read_kind('revenue')
    if rev is not None:
        xr,yr=build_revenue_panel(rev)
        save('revenue_monthly_research_non_pit',xr)
        save('next_revenue_Y_candidates_not_X',yr)
        statuses['revenue']='DERIVED_RESEARCH_ANNOUNCEMENT_TIME_NOT_VERIFIED'
    val=read_kind('valuation')
    if val is not None:
        xv,yv=build_valuation_panel(val)
        save('valuation_observation_research_non_pit',xv)
        save('valuation_Y_candidates_not_X',yv)
        statuses['valuation']='DERIVED_RESEARCH_ANNOUNCEMENT_TIME_NOT_VERIFIED'
    events=read_kind('corporate_actions')
    if events is not None:
        xe=build_corporate_event_panel(events)
        save('corporate_event_flags_unadjusted_research',xe)
        statuses['corporate_actions']='RAW_EVENTS_ONLY_NO_AUTO_ADJUSTMENT'
    fin=read_kind('financials')
    if fin is not None:
        xf,info=build_financial_panel(fin)
        save('financial_quarterly_raw_research_non_pit',xf)
        (output/'financial_factor_basis_audit.json').write_text(info.to_json(orient='records',force_ascii=False),encoding='utf-8')
        artifacts['financial_factor_basis_audit.json']={'rows':int(len(info)),'cols':int(len(info.columns)),'sha256':hashlib.sha256((output/'financial_factor_basis_audit.json').read_bytes()).hexdigest()}
        statuses['financials']='RAW_UNITS_PUBLICATION_AND_PERIOD_BASIS_UNVERIFIED'
    idx=read_kind('market_index')
    if idx is not None:
        save('market_index_research_non_pit',build_market_index_panel(idx))
        statuses['official_market_index']='RESEARCH_CONTEXT_PRESENT_PIT_NOT_VERIFIED'
    else:
        statuses['official_market_index']='SOURCE_PROBE_PENDING'
    membership=read_kind('industry_membership')
    if membership is not None and raw is not None:
        industry=build_industry_panel(xd,membership)
        if not industry.empty:save('industry_context_historical_research',industry)
        statuses['industry_membership_history']='DATED_HISTORY_AVAILABLE_FOR_RESEARCH'
        statuses['industry_relative_strength']='RESEARCH_CONTEXT_PRESENT_NOT_SERVING_VERIFIED'
    else:
        statuses['industry_membership_history']='SOURCE_PIT_PENDING'
        statuses['industry_relative_strength']='BLOCKED_ON_HISTORICAL_MEMBERSHIP'
    # No fabricated data for other missing source classes.
    statuses.update({
                    'institutional_flows':'SOURCE_NOT_VERIFIED',
                    'shares_outstanding_market_cap':'SOURCE_NOT_VERIFIED',
                    'macro_rates':'SOURCE_NOT_VERIFIED',
                    'company_actions_adjusted_price':'ADJUSTMENT_BASIS_NOT_VERIFIED',
                    'asof_daily_financial_join':'BLOCKED_ON_ANNOUNCEMENT_PIT'})
    catalog_path=output/'factor_catalog.json'
    catalog_path.write_text(json.dumps({'factory_version':FACTORY_VERSION,'data_products':catalog,
                'critical_rule':'Y outcome files are never joined into X or serving feature matrices'},
             ensure_ascii=False,indent=2),encoding='utf8')
    artifacts['factor_catalog.json']={'rows':len(catalog),'cols':0,
        'sha256':hashlib.sha256(catalog_path.read_bytes()).hexdigest()}
    receipt={'status':'RESEARCH_FEATURES_BUILT','input_id':digest,'factory_version':FACTORY_VERSION,
             'source_manifest_sha256':hashlib.sha256(manifestbytes).hexdigest(),
             'source_current_sha256':hashlib.sha256(rawptr).hexdigest(),
             'source_release':release.name,'artifacts':artifacts,'factor_status':statuses,
             'publication_allowed':False,'canonical_current_modified':False,
             'training_features_do_not_include_future_labels':True,
             'all_four_models_deployable':False,
             'created_at_utc':datetime.now(timezone.utc).isoformat()}
    done.write_text(json.dumps(receipt,indent=2,ensure_ascii=False,sort_keys=True),encoding='utf8')
    return receipt

if __name__=='__main__':
    raise SystemExit('Call build_factory(ROOT) via the controlled Colab Notebook (or pytest).')
