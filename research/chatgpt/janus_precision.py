"""Janus v3.8.1 research contracts. No network, CURRENT write or publication."""
from __future__ import annotations
import ast, hashlib, json, re, sys
from pathlib import Path
import numpy as np
import pandas as pd
import factor_factory_v1 as legacy

VERSION = '3.8.2'
KEY = ['market', 'symbol']
RISK = ['vol20','vol60','drawdown60','abs_return5','volume_ratio20',
        'atr14_pct','abs_overnight_gap5','log_turnover20']
QUANT = ['ret5','ret20','ret60','ma20_distance','ma60_distance','vol20','vol60',
         'drawdown60','volume_ratio20','log_turnover20','market_code']
FUND = ['yoy_m','yoy_3m','yoy_change1','growth_acceleration','mom_m','log_revenue',
        'season_sin','season_cos','revenue_vol3','market_code']
VAL = ['roe','debt_ratio','log_total_assets','revenue_yoy','market_code']

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def write_json(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,
                            default=str,allow_nan=False)+'\n',encoding='utf-8')

def safe_path(root,rel):
    root=Path(root).resolve(); p=(root/rel).resolve()
    if not p.is_relative_to(root) or Path(rel).is_absolute():
        raise ValueError('UNSAFE_PATH '+str(rel))
    return p

def load_release(root,kinds=None,max_rows=1500000):
    """CURRENT pinned once, hash every selected partition, quarantine reported conflicts."""
    root=Path(root); pointer=root/'canonical/CURRENT.json'
    raw=pointer.read_bytes();cur=json.loads(raw)
    rel=cur.get('manifest')
    if not rel or cur.get('format')!='parquet': raise ValueError('CURRENT_SCHEMA')
    mp=safe_path(root,rel);m=json.loads(mp.read_bytes())
    if (m.get('publication_allowed') is not False or
        m.get('status') not in ('RESEARCH_DATA_ONLY','RESEARCH_ONLY') or
        cur.get('release')!=mp.parent.name or
        m.get('release_id')!=mp.parent.name.removeprefix('release-')):
        raise ValueError('MANIFEST_CONTRACT')
    kinds=kinds or ['ohlcv','revenue','financials','valuation','corporate_actions']
    out={};audit=[];verified={}
    conflicts=None
    if 'conflicts.csv' in m['files']:
        p=safe_path(mp.parent,'conflicts.csv');ref=m['files']['conflicts.csv']
        if sha(p)!=ref['sha256']: raise ValueError('HASH conflicts.csv')
        conflicts=pd.read_csv(p)
        if len(conflicts)!=ref['rows']:raise ValueError('ROWS conflicts.csv')
        verified['conflicts.csv']=ref
    keys={'ohlcv':['symbol','market','trade_date'],
          'revenue':['symbol','market','fiscal_month'],
          'valuation':['symbol','market','trade_date'],
          'financials':['symbol','market','dataset','fiscal_quarter','item','unit_basis']}
    for kind in kinds:
        parts=[];total=0
        for rel,ref in sorted(m['files'].items()):
            if not rel.startswith(kind+'/') or not rel.endswith('.parquet'):continue
            total+=ref['rows']
            if total>max_rows:raise ValueError('ROW_BUDGET '+kind)
            p=safe_path(mp.parent,rel)
            if sha(p)!=ref['sha256']:raise ValueError('HASH '+rel)
            d=pd.read_parquet(p)
            if len(d)!=ref['rows']:raise ValueError('ROWS '+rel)
            d['_source_partition']=rel;parts.append(d);verified[rel]=ref
        if not parts: out[kind]=pd.DataFrame();continue
        d=pd.concat(parts,ignore_index=True)
        for c in KEY:d[c]=d[c].astype(str).str.strip()
        d['market']=d.market.str.lower()
        if not d.market.isin(['twse','tpex']).all():raise ValueError('UNKNOWN_MARKET')
        # Existing collector ordinary-share universe; do not infer historical membership.
        invalid=~d.symbol.str.fullmatch('[1-9][0-9]{3}')
        audit.append({'table':kind,'reason':'NON_ORDINARY_CODE','rows':int(invalid.sum())})
        d=d.loc[~invalid].copy()
        if kind in keys and conflicts is not None and not conflicts.empty:
            bad=set()
            for row in conflicts.loc[conflicts.dataset.eq(kind)].itertuples():
                k=ast.literal_eval(row.key)
                if not isinstance(k,tuple) or len(k)!=len(keys[kind]):
                    raise ValueError('CONFLICT_KEY_SCHEMA '+kind)
                bad.add(tuple(str(v) for v in k))
            mask=pd.Series([tuple(str(v) for v in row) in bad for row in
                             d[keys[kind]].itertuples(index=False,name=None)],index=d.index)
            audit.append({'table':kind,'reason':'SOURCE_VALUE_CONFLICT','rows':int(mask.sum())})
            d=d.loc[~mask].copy()
        if kind in keys and d.duplicated(keys[kind]).any():raise ValueError('REVISION_CONFLICT '+kind)
        out[kind]=d
    receipt={'release':cur['release'],'current_sha256':hashlib.sha256(raw).hexdigest(),
             'manifest_sha256':sha(mp),'files':verified,'declared_tables':m.get('tables'),
             'historical_pit':m.get('historical_pit'),'quarantine':audit,
             'publication_allowed':False,'validation_scope':'selected partitions, not all source rights/PIT'}
    return out,receipt

def daily(raw,sessions=None):
    """Reindex full market sessions before ALL rolling/EMA computations."""
    r=raw.copy();r['trade_date']=pd.to_datetime(r.trade_date).dt.normalize()
    if r.duplicated(KEY+['trade_date']).any():raise ValueError('duplicate OHLCV')
    grids={m:pd.DatetimeIndex(sorted(g.trade_date.unique())) for m,g in r.groupby('market')}
    if sessions is not None:
        for m in grids:
            grid=pd.DatetimeIndex(pd.to_datetime(sessions[m]))
            if grid.has_duplicates or not grid.is_monotonic_increasing or len(grids[m].difference(grid)):
                raise ValueError('SESSION_CONTRACT')
            grids[m]=grid
    pieces=[]
    for (m,s),g in r.groupby(KEY,sort=False):
        # Preserve gaps inside each observed lifetime, without fabricating pre-IPO data.
        grid=grids[m][(grids[m]>=g.trade_date.min())&(grids[m]<=g.trade_date.max())]
        a=g.set_index('trade_date').reindex(grid).rename_axis('trade_date').reset_index()
        a['market']=m;a['symbol']=s;pieces.append(a)
    r=pd.concat(pieces,ignore_index=True)
    x,y,breadth=legacy.build_ohlcv_panel(r)
    x=x.copy()
    x['market_code']=x.market.map({'twse':0.,'tpex':1.})
    g=x.groupby(KEY,sort=False)
    logret=np.log(x.close/g.close.shift(1))
    for n in (20,60):
        x[f'vol{n}']=logret.groupby([x.market,x.symbol]).transform(
            lambda z:np.sqrt(z.pow(2).rolling(n,min_periods=n).mean()*252))
    x['drawdown60']=x.drawdown_from_high60
    x['abs_return5']=x.ret5.abs();x['log_turnover20']=x.turnover_log20
    x['warmup60_ok']=g.close.transform(lambda z:z.rolling(61,min_periods=61).count()).eq(61)
    # Gap-induced EMA carries are not valid: expose only after fresh 60-session warmup.
    for c in ['macd12_26','macd_signal9','macd_hist9']:x[c]=x[c].where(x.warmup60_ok)
    y['future_rms_vol20']=logret.groupby([x.market,x.symbol]).transform(
        lambda z:np.sqrt(z.pow(2).shift(-1).rolling(20,min_periods=20).mean().shift(-19)*252))
    # Existing std target stays separately named; never rename it to RMS silently.
    y['label_version']='price-logreturn-rms-v3.8.1'
    x['calendar_basis']='EXPLICIT_MARKET_SESSIONS' if sessions is not None else 'OBSERVED_MARKET_UNION_NON_PIT'
    x['price_basis']='RAW_UNADJUSTED_NOT_TOTAL_RETURN'
    x['feature_available_at']=pd.NaT
    meta=[c for c in ['source_id','observed_at','_source_partition'] if c in r]
    if meta:x=x.merge(r[KEY+['trade_date']+meta],on=KEY+['trade_date'],validate='one_to_one',how='left')
    return x,y,breadth

def monthly(raw):
    """Calendar reindex avoids nth-observation lag across missing months."""
    parts=[]
    for (m,s),g in raw.groupby(KEY,sort=False):
        a=g.copy();a['period']=pd.PeriodIndex(a.fiscal_month.astype(str),freq='M')
        if a.period.duplicated().any():raise ValueError('duplicate revenue revision')
        lo,hi=a.period.min(),a.period.max()
        a=a.set_index('period').reindex(pd.period_range(lo,hi,freq='M'))
        a['fiscal_month']=a.index.astype(str);a['market']=m;a['symbol']=s
        parts.append(a.reset_index(drop=True))
    z=pd.concat(parts,ignore_index=True)
    x,y=legacy.build_revenue_panel(z)
    x['yoy_m']=100*x.revenue_yoy;x['yoy_3m']=100*x.revenue_sum3m_yoy
    x['yoy_change1']=100*x.revenue_yoy_delta;x['growth_acceleration']=x.yoy_m-x.yoy_3m
    x['mom_m']=100*x.revenue_growth_1m;x['log_revenue']=np.log1p(x.revenue_twd)
    month=pd.PeriodIndex(x.fiscal_month,freq='M').month
    x['season_sin']=np.sin(2*np.pi*month/12);x['season_cos']=np.cos(2*np.pi*month/12)
    x['revenue_vol3']=x.groupby(KEY).log_revenue.transform(lambda s:s.rolling(3,min_periods=3).std(ddof=0))
    x['market_code']=x.market.map({'twse':0.,'tpex':1.})
    x['feature_available_at']=pd.to_datetime(x.published_at,utc=True,errors='coerce',format='mixed')
    # Require availability of every value participating in the 15-month window.
    def window_latest(s):
        v=s.astype('int64').astype(float);v[s.isna()]=np.nan
        return pd.to_datetime(v.rolling(15,min_periods=15).max(),utc=True)
    x['feature_available_at']=x.groupby(KEY).feature_available_at.transform(window_latest)
    y['target_next_yoy_pp']=100*y.label_next_revenue_yoy
    y['label_available_at']=pd.to_datetime(y.label_published_at,utc=True,errors='coerce',format='mixed')
    y['label_version']='next-month-yoy-percentage-points-v3.8.1'
    return x,y

def training_panel(data,role,mode='retrospective',horizon=20,financial_mapping=None):
    if mode not in ('retrospective','strict'):raise ValueError('MODE')
    if role in ('quant','risk'):
        if horizon not in (5,20) or (role=='risk' and horizon!=20):raise ValueError('HORIZON')
        x,y,_=daily(data['ohlcv'])
        p=x.merge(y,on=KEY+['trade_date','session_index'],validate='one_to_one')
        p['signal_group']=p.trade_date;p['signal_at']=p.trade_date
        p['y']=p[f'forward_up_{horizon}'] if role=='quant' else p.future_rms_vol20
        p['mature_at']=p[f'mature_session_{horizon}']
        p['reason']=np.where(p.warmup60_ok,'OK','WARMUP_OR_MISSING_SESSION')
        if mode=='strict':p['reason']='BLOCKED_PRICE_AVAILABILITY_ACTIONS_UNVERIFIED'
        return p, QUANT if role=='quant' else RISK
    if role=='fundamental':
        x,y=monthly(data['revenue']);p=x.merge(y,on=KEY+['fiscal_month'],validate='one_to_one')
        p['signal_group']=pd.PeriodIndex(p.fiscal_month,freq='M').to_timestamp()
        p['signal_at']=p.feature_available_at.dt.tz_convert(None)
        p['mature_at']=p.label_available_at.dt.tz_convert(None)
        p['y']=p.target_next_yoy_pp
        p['reason']='OK'
        known=p.signal_at.notna()&p.mature_at.notna()
        p.loc[known & (p.mature_at<=p.signal_at),'reason']='ANSWER_ALREADY_KNOWN'
        if mode=='strict':
            # Existence of a timestamp alone is insufficient historical provenance.
            trusted=p.pit_eligible & p.groupby(KEY).pit_eligible.transform(
                lambda s:s.rolling(15,min_periods=15).min()).eq(1)
            next_pit=p.groupby(KEY).pit_eligible.shift(-1).eq(True)
            p.loc[(~known|~trusted|~next_pit)&p.reason.eq('OK'),'reason']='BLOCKED_HISTORICAL_PIT'
        else:
            # These are calendar dependency bounds, explicitly NOT publication dates.
            p['signal_at']=p.signal_group
            p['mature_at']=(pd.PeriodIndex(p.fiscal_month,freq='M')+1).to_timestamp()
        return p,FUND
    if role=='valuation':return valuation_panel(data,financial_mapping or {})
    raise ValueError('ROLE')

def valuation_panel(data,mapping):
    v=data['valuation'].copy();v['trade_date']=pd.to_datetime(v.trade_date)
    v['signal_group']=v.trade_date.dt.to_period('M').dt.to_timestamp()
    v=v.sort_values('trade_date').drop_duplicates(KEY+['signal_group'],keep='last')
    # No claim that latest available is true market month-end without session evidence.
    v['signal_at']=v.trade_date;v['mature_at']=v.trade_date
    v['market_code']=v.market.map({'twse':0.,'tpex':1.})
    v['reason']='BLOCKED_VERIFIED_FINANCIAL_MAPPING_OR_COHORT'
    for c in ['roe','debt_ratio','log_total_assets','revenue_yoy']:v[c]=np.nan
    v['cohort']='UNKNOWN'
    # Mapping entries must describe direct VERIFIED metrics, never infer accounting ratios.
    # Cohort mapping is effective-dated, not a current symbol dictionary.
    metrics=mapping.get('metrics',{})
    f=data.get('financials',pd.DataFrame())
    for name,cfg in metrics.items():
        if name not in VAL:raise ValueError('VALUATION_X_ALLOWLIST')
        if not all(cfg.get(c) for c in ['dataset','item','unit_basis','period_basis','evidence']):
            raise ValueError('MAPPING_REQUIRES_EXACT_BASIS_AND_EVIDENCE')
        if f.empty:continue
        q=f.copy()
        for c in ['dataset','item','unit_basis','period_basis']:q=q.loc[q[c].eq(cfg[c])]
        q=q.loc[q.historical_pit.eq('VERIFIED')].copy()
        q['available']=pd.to_datetime(q.published_at,utc=True,errors='coerce',format='mixed').dt.tz_convert(None)
        q['value']=pd.to_numeric(q.value,errors='coerce')*float(cfg.get('scale',1))
        q=q.dropna(subset=['available','value'])
        if q.empty:continue
        if q.duplicated(KEY+['available']).any():raise ValueError('AMBIGUOUS_FINANCIAL_VERSION')
        left=v[KEY+['signal_at']].copy();left['rid']=v.index
        j=pd.merge_asof(left.sort_values('signal_at'),q[KEY+['available','value']].sort_values('available'),
                        by=KEY,left_on='signal_at',right_on='available',direction='backward',
                        tolerance=pd.Timedelta(days=cfg.get('max_age_days',550)))
        values=j.value
        if name=='log_total_assets':values=np.log1p(values.where(values>0))
        v.loc[j.rid,name]=values.to_numpy()
    for rec in mapping.get('cohorts',[]):
        if not all(rec.get(c) for c in ['market','symbol','cohort','valid_from','available_at','evidence']):
            raise ValueError('COHORT_EVIDENCE_REQUIRED')
        mask=(v.market.eq(rec['market'])&v.symbol.eq(str(rec['symbol']))&
              v.signal_at.ge(pd.Timestamp(rec['valid_from']))&v.signal_at.ge(pd.Timestamp(rec['available_at'])))
        if rec.get('valid_to'):mask &= v.signal_at.lt(pd.Timestamp(rec['valid_to']))
        if v.loc[mask,'cohort'].ne('UNKNOWN').any():raise ValueError('OVERLAPPING_COHORT')
        v.loc[mask,'cohort']=rec['cohort']
    valid=v[VAL].notna().all(axis=1)&v.cohort.ne('UNKNOWN')
    # A lone early-month observation is not a month-end snapshot.
    calendar=mapping.get('market_month_ends',[])
    if calendar:
        if not mapping.get('calendar_evidence'):raise ValueError('CALENDAR_EVIDENCE_REQUIRED')
        ends=pd.DataFrame(calendar)
        ends['trade_date']=pd.to_datetime(ends.trade_date)
    elif not data.get('ohlcv',pd.DataFrame()).empty:
        ends=data['ohlcv'][['market','trade_date']].copy()
        ends['trade_date']=pd.to_datetime(ends.trade_date)
        ends['_month']=ends.trade_date.dt.to_period('M')
        ends=ends.groupby(['market','_month'],as_index=False).trade_date.max()
    else:
        ends=pd.DataFrame(columns=['market','trade_date'])
    endkeys=set(ends[['market','trade_date']].itertuples(index=False,name=None))
    valid &= pd.Series([(m,d) in endkeys for m,d in v[['market','trade_date']].itertuples(index=False,name=None)],index=v.index)
    v.loc[valid,'reason']='OK'
    for t in ['pe','pb']:
        n=pd.to_numeric(v[t+'_ratio'],errors='coerce')
        v['y_'+t]=np.log(n.where(n>0))
    return v,VAL

def export_dataset(root,max_rows=1500000,output_root=None):
    """Shared X/Y package; original canonical release remains immutable."""
    data,receipt=load_release(root,max_rows=max_rows)
    code_sha=hashlib.sha256((sha(__file__)+sha(legacy.__file__)+pd.__version__+np.__version__).encode()).hexdigest()
    ident=hashlib.sha256(json.dumps([receipt,code_sha],sort_keys=True).encode()).hexdigest()[:16]
    out=Path(output_root if output_root is not None else root)/'derived/four_model_precision'/('v3.8.2-'+ident)
    done=out/'manifest.json'
    if done.exists():
        m=json.loads(done.read_text())
        for p,h in m['files'].items():
            if sha(safe_path(out,p))!=h:raise ValueError('OUTPUT_HASH '+p)
        return out,m
    if out.exists():raise ValueError('INCOMPLETE_RUN_REMOVE_ONLY_AFTER_INSPECTION '+str(out))
    out.mkdir(parents=True)
    write_json(out/'input_manifest.json',receipt)
    catalog={};status={}
    def save(name,frame,kind):
        frame.to_parquet(out/(name+'.parquet'),index=False)
        catalog[name]={'kind':kind,'rows':len(frame),'columns':list(frame),
            'missing_rate':{c:float(frame[c].isna().mean()) for c in frame},'publication_allowed':False}
    for role,kind in [('quant','ohlcv'),('fundamental','revenue')]:
        if data[kind].empty:status[kind]='MISSING';continue
        if kind=='ohlcv':
            x,y,b=daily(data[kind]);save('daily_X',x,'X_RESEARCH');save('price_Y',y,'Y_NOT_X');save('breadth_context',b,'CONTEXT_NON_PIT')
        else:
            x,y=monthly(data[kind]);save('monthly_X',x,'X_RESEARCH');save('revenue_Y',y,'Y_NOT_X')
        status[kind]='RESEARCH_DERIVED'
    if not data['valuation'].empty:
        x,y=legacy.build_valuation_panel(data['valuation'])
        save('valuation_descriptive_NOT_MODEL_X',x,'TARGET_DERIVED_CONTEXT_FORBIDDEN_AS_VALUATION_X')
        save('valuation_Y',y,'Y_NOT_X')
    if not data['financials'].empty:
        x,a=legacy.build_financial_panel(data['financials']);save('financial_RAW_NOT_MODEL_X',x,'UNVERIFIED_ACCOUNTING_BASIS')
        a.to_csv(out/'financial_mapping_audit.csv',index=False,encoding='utf-8-sig')
    write_json(out/'factor_catalog.json',catalog)
    write_json(out/'readiness.json',{'status':status,'historical_pit':'NOT_VERIFIED',
        'market_index':'NOT_IN_CURRENT_RELEASE','industry':'NOT_IN_CURRENT_RELEASE',
        'valuation_training':'REQUIRES_VERIFIED_FINANCIAL_MAPPING_AND_COHORT',
        'publication_allowed':False})
    files={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    m={'version':VERSION,'code_sha256':code_sha,'files':files,'input':receipt,
       'state':'RESEARCH_DERIVED_NOT_PROMOTABLE','publication_allowed':False}
    write_json(done,m);return out,m
