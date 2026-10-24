"""Janus Valuation research-only PE/PB Ridge/XGBoost study.
Real Janus existing CURRENT pinned Parquet + P0/P1 inventory; no network/canonical writes.
Four-factor 2023 re-run or five-factor 2024-2026 expanding-period experiment.
"""
from __future__ import annotations
import argparse,zipfile,gzip,csv,json,hashlib,math,platform,datetime as dt,os,sys
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error,mean_squared_error
import xgboost as xgb

ITEMS={'資產總計':'assets','負債總計':'liabilities','權益總計':'equity','本期淨利（淨損）':'net_income','營業收入':'revenue_ytd'}
FIVE=['roe_proxy','debt_ratio','log_total_assets','revenue_yoy','market_code']
FOUR=['roe_proxy','debt_ratio','log_total_assets','market_code']
LABELS=['pe_ratio','pb_ratio']
V23_SNAPSHOT='output/01b_all_actual_prehistory_finmind_last_observations.csv.gz'
SEED=20261024

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def read_valuation_month(path):
 try:
  return pd.read_parquet(path,columns=['symbol','market','trade_date','pe_ratio','pb_ratio'])
 except ImportError:
  # environment lacks pyarrow: strict minimal flat zstd reader for verified release schema
  from janus_parquet_min import read
  return pd.DataFrame(read(path,selected=['symbol','market','trade_date','pe_ratio','pb_ratio']))

def read_current(root,manifest,mode):
 files=[];evidence=[]
 if mode=='v26':
  for year in range(2024,2027):
   for month in range(1,13 if year<2026 else 10):
    name=f'{year}-{month:02d}';p=root/(name+'.parquet.bin')
    if not p.is_file():raise FileNotFoundError(f'MISSING_MONTHLY_SOURCE_{name}')
    ref=manifest['files'].get('valuation/'+name+'.parquet')
    if not ref or sha(p)!=ref['sha256']:raise ValueError(f'SOURCE_HASH_MISMATCH_{name}')
    x=read_valuation_month(p)
    if len(x)!=ref['rows']:raise ValueError(f'RELEASE_ROW_COUNT_{name}')
    files.append(x)
    evidence.append({'name':name+'.parquet','rows':len(x),'sha256':sha(p)})
  df=pd.concat(files,ignore_index=True)
 else:
  zip_path=root/'Janus_Valuation_04_v23_歷史月末整併與模型准入_20261024.zip'
  if not zip_path.exists():raise FileNotFoundError('V23_SOURCE_ZIP')
  with zipfile.ZipFile(zip_path) as z:
   with z.open(V23_SNAPSHOT) as f:
    with gzip.open(f,'rt',encoding='utf-8-sig',newline='') as inp:
     df=pd.read_csv(inp,dtype={'symbol':str})
  df=df.rename(columns={'pe_ratio':'pe_ratio','pb_ratio':'pb_ratio'})
  evidence.append({'name':V23_SNAPSHOT,'rows':len(df),'container_sha256':sha(zip_path)})
 df['market']=df.market.astype(str).str.lower();df['symbol']=df.symbol.astype(str)
 df['trade_date']=pd.to_datetime(df.trade_date,errors='coerce');df['month']=df.trade_date.dt.to_period('M').astype(str)
 df=df.dropna(subset=['trade_date']).sort_values('trade_date')
 df=df.drop_duplicates(['market','symbol','month'],keep='last')
 if mode=='v26':
  # Reject early-month snapshots; true market last observation is visible in sourced monthly file.
  market_max=df.groupby(['market','month']).trade_date.transform('max')
  df=df[df.trade_date.eq(market_max)].copy()
 df=df.sort_values(['trade_date','market','symbol']).reset_index(drop=True)
 return df,evidence

def load_financials(finzip):
 """Use only actual MOPS records; duplicates rejected, not resolved by silent aggregation."""
 parsed={};dupe=set();stock_quarters=set()
 counts=Counter()
 with zipfile.ZipFile(finzip) as z:
  with z.open('P0_P1_實測報告/inventory.csv.gz') as raw:
   with gzip.open(raw,'rt',encoding='utf-8-sig',newline='') as f:
    for x in csv.DictReader(f):
     if x['source_id']!='mops' or x['item_raw'] not in ITEMS:continue
     if x['dataset'] not in ('income','balance'):continue
     if not x.get('value_parseable','').lower()=='true':continue
     symbol=str(x['symbol']).strip();market=x['market'].lower().strip();quarter=x['fiscal_quarter'];metric=ITEMS[x['item_raw']]
     try:v=float(x['value_raw'])
     except (TypeError,ValueError):continue
     if not math.isfinite(v):continue
     k=(market,symbol,quarter,metric)
     if k in parsed:dupe.add(k)
     parsed[k]=v;counts[metric]+=1
 for k in dupe:parsed.pop(k,None)
 rows=defaultdict(dict)
 for (market,sym,q,metric),v in parsed.items():rows[(market,sym,q)][metric]=v
 records=[]
 for (market,sym,q),v in rows.items():
  qnum=int(q[-1]);year=int(q[:4]);date=dt.date(year,qnum*3+1,1) if qnum<4 else dt.date(year+1,1,1)
  date=date-dt.timedelta(days=1)
  available=date+dt.timedelta(days=90) # explicit NON-PIT study-only lag assumption
  fin={'market':market,'symbol':sym,'quarter':q,'quarter_end':date.isoformat(),'available_at':available.isoformat(),**v}
  if v.get('equity',0)>0 and 'net_income' in v:fin['roe_proxy']=v['net_income']/v['equity']
  if v.get('assets',0)>0:
   if 'liabilities' in v:fin['debt_ratio']=v['liabilities']/v['assets']
   fin['log_total_assets']=math.log(v['assets']*1000)
  # Query-period MOPS income is used as cumulative YTD revenue; SAME-Q annual growth proxy.
  ly=f'{year-1}Q{qnum}'
  old=rows.get((market,sym,ly),{}).get('revenue_ytd')
  if old is not None and old>0 and math.isfinite(old) and math.isfinite(v.get('revenue_ytd',float('nan'))):
   fin['revenue_yoy']=v['revenue_ytd']/old-1
  records.append(fin)
 df=pd.DataFrame.from_records(records)
 df['available_at']=pd.to_datetime(df.available_at)
 return df,{'metric_rows':dict(counts),'duplicate_raw_keys_excluded':len(dupe),'distinct_stock_quarters':len(df),
   'quarters_with_revenue_yoy':int(df.revenue_yoy.notna().sum()) if 'revenue_yoy' in df else 0}

def create_panel(valuation,finance,mode):
 feats=FOUR if mode=='v25_replay' else FIVE
 a=valuation.sort_values('trade_date').copy();b=finance.sort_values('available_at').copy()
 joined=pd.merge_asof(a,b,by=['market','symbol'],left_on='trade_date',right_on='available_at',direction='backward',tolerance=pd.Timedelta(days=550))
 joined['market_code']=joined.market.map({'twse':0.,'tpex':1.})
 for col in feats:
  if col not in joined:joined[col]=np.nan
  joined[col]=pd.to_numeric(joined[col],errors='coerce')
 good=joined[feats].replace([np.inf,-np.inf],np.nan).notna().all(axis=1)
 excluded=int((~good).sum());df=joined[good].copy()
 df['non_pit_assumption']='quarter_end_plus_90days'
 return df,feats,{'valuation_rows':len(valuation),'financial_join_complete':len(df),'missing_five_feature_rows':excluded,
                 'by_month_feature_complete':{str(x):int(n) for x,n in df.groupby('month').size().items()}}

def group_model(train,val,test,feats,branch,out,fold):
 label=branch+'_ratio';t=train[pd.to_numeric(train[label],errors='coerce')>0].copy();v=val[pd.to_numeric(val[label],errors='coerce')>0].copy();s=test[pd.to_numeric(test[label],errors='coerce')>0].copy()
 if len(t)<250 or len(v)<100 or len(s)<100 or t.month.nunique()<4 or v.month.nunique()<1 or s.month.nunique()<1:
  return {'status':'INSUFFICIENT','train':len(t),'validation':len(v),'test':len(s)},None
 if not (t.trade_date.max()<v.trade_date.min() and v.trade_date.max()<s.trade_date.min()):raise ValueError('TIME_OVERLAP')
 Xtr=t[feats].to_numpy(float);Xva=v[feats].to_numpy(float);Xte=s[feats].to_numpy(float)
 ytr=np.log(t[label].astype(float).to_numpy());yva=np.log(v[label].astype(float).to_numpy());yte=np.log(s[label].astype(float).to_numpy())
 market_median={int(m):float(np.median(ytr[t.market_code.to_numpy().astype(int)==int(m)])) for m in sorted(t.market_code.dropna().unique())}
 overall=float(np.median(ytr));base=lambda f: np.array([market_median.get(int(m),overall) for m in f.market_code])
 scaler=StandardScaler().fit(Xtr);ridge=Ridge(alpha=30).fit(scaler.transform(Xtr),ytr)
 boost=xgb.XGBRegressor(objective='reg:squarederror',tree_method='hist',device='cpu',max_depth=2,
   learning_rate=0.05,n_estimators=140,min_child_weight=50,subsample=.8,colsample_bytree=.8,
   reg_lambda=20,random_state=SEED,n_jobs=2)
 boost.fit(Xtr,ytr)
 bva=base(v); bte=base(s);rva=ridge.predict(scaler.transform(Xva));rte=ridge.predict(scaler.transform(Xte));gva=boost.predict(Xva);gte=boost.predict(Xte)
 def scores(yy,p):return {'log_mae':float(mean_absolute_error(yy,p)),'log_rmse':float(np.sqrt(mean_squared_error(yy,p)))}
 metrics={'baseline':{'validation':scores(yva,bva),'test':scores(yte,bte)},
          'ridge':{'validation':scores(yva,rva),'test':scores(yte,rte)},
          'xgboost':{'validation':scores(yva,gva),'test':scores(yte,gte)}}
 out=Path(out);d=out/fold/branch;d.mkdir(parents=True,exist_ok=True)
 modelpath=d/'xgboost.ubj';boost.save_model(str(modelpath));fresh=xgb.XGBRegressor();fresh.load_model(str(modelpath))
 maxerr=float(np.max(np.abs(fresh.predict(Xte)-gte)))
 if maxerr>1e-6:raise AssertionError('UBJ_RELOAD_PREDICTION_MISMATCH')
 (d/'ridge.json').write_text(json.dumps({'alpha':30,'coef':ridge.coef_.tolist(),'intercept':float(ridge.intercept_),
  'scaler_mean':scaler.mean_.tolist(),'scaler_scale':scaler.scale_.tolist(),'features':feats},indent=2),encoding='utf-8')
 (d/'test_vectors.json').write_text(json.dumps({'features':feats,'X':Xte[:5].tolist(),
   'expected_prediction':gte[:5].tolist(),'max_reload_error':maxerr},indent=2),encoding='utf-8')
 pred=s[['market','symbol','month','trade_date']].copy();pred['actual_log_multiple']=yte;pred['baseline']=bte;pred['ridge']=rte;pred['xgboost']=gte
 pred.to_csv(d/'test_predictions.csv',index=False)
 pd.DataFrame({'month':s.month,'market':s.market,'actual':yte,'xgboost':gte,'baseline':bte}).groupby(['month','market']).apply(
   lambda q:pd.Series({'rows':len(q),'xgb_log_mae':np.mean(abs(q.actual-q.xgboost)),'base_log_mae':np.mean(abs(q.actual-q.baseline))}),include_groups=False).to_csv(d/'test_month_market.csv')
 return {'status':'RESEARCH_NON_PIT_FITTED','features':feats,'split':{label:{'rows':len(frame),'symbols':int(frame.symbol.nunique()),'months':sorted(frame.month.unique().tolist())} for label,frame in [('train',t),('validation',v),('test',s)]},
    'metrics':metrics,'ubj_reload_max_abs_err':maxerr,'publication_allowed':False},pred

def run(root,output,mode='v26'):
 root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
 valuation,files=read_current(root,manifest,mode)
 finzip=root/'Valuation_P0_P1_實測資料與程式_20261024.zip'
 fin,stats=load_financials(finzip)
 panel,feats,coverage=create_panel(valuation,fin,mode)
 if mode=='v25_replay':splits={'original_2023':(('2023-03','2023-06'),('2023-07','2023-07'),('2023-08','2023-09'))}
 else:splits={'fold_2025h2':(('2024-07','2025-06'),('2025-07','2025-09'),('2025-10','2025-12')),
              'fold_2026':(('2024-07','2025-09'),('2025-10','2025-12'),('2026-01','2026-09'))}
 panel.to_csv(output/'study_XY_panel.csv.gz',index=False,compression='gzip')
 reports={}
 for fold,(train,val,test) in splits.items():
  d=lambda a,b:panel[(panel.month>=a)&(panel.month<=b)]
  tr,va,te=d(*train),d(*val),d(*test)
  reports[fold]={}
  for b in ('pe','pb'):
   report,_=group_model(tr,va,te,feats,b,output,fold);reports[fold][b]=report
  print(fold, {k:{s:round(v['metrics']['xgboost']['test']['log_mae'],4) for s in ['x']} if v.get('status')!='INSUFFICIENT' else 'INSUFFICIENT' for k,v in reports[fold].items()})
 info={'state':'RESEARCH_NON_PIT_DIAGNOSTIC','publication_allowed':False,'mode':mode,'features':feats,
       'target_label':'log(PE/PB)','valuation_input':files,'financial_inventory_sha256':sha(finzip),
       'research_assumptions':['MOPS query_period unspecified; YTD revenue year-over-year same-quarter proxy',
        'fiscal quarter_end+90 days availability assumed, not historical published_at',
        'roe_proxy=reported cumulative net income / equity; not annualized ROE',
        'cohort not effective dated; only market baseline','monthly last available date, not exchange official close'],
       'financial_stats':stats,'panel_coverage':coverage,'folds':reports,
       'versions':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'xgboost':xgb.__version__},
       'limitations':['NON_PIT','not production or promotion','2024-2026 backtest over existing research release only'],
       'generated_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
 (output/'report.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False,default=str),encoding='utf-8')
 hashes={str(f.relative_to(output)):sha(f) for f in output.rglob('*') if f.is_file()}
 (output/'artifact_manifest.json').write_text(json.dumps({'status':'SEALED','publication_allowed':False,'sha256':hashes},indent=2,ensure_ascii=False),encoding='utf-8')
 return info

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=['v26','v25_replay'],default='v26');a=p.parse_args()
 run(a.root,a.output,a.mode)
