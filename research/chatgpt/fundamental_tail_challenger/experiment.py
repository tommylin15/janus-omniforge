"""Fundamental bounded tail-first retrospective trial: NO promotion/canonical writes.
Requires pre-existing pinned local research CSV; no outside calls. Usage:
  python experiment.py run 2025-09 2025-10
  python experiment.py finalize
Historic PIT not verified; evaluation months already exposed.
"""
from __future__ import annotations
import sys,json,hashlib,platform
from pathlib import Path
import numpy as np,pandas as pd
import lightgbm,catboost,xgboost,sklearn,scipy
from lightgbm import LGBMRegressor
from catboost import CatBoostRegressor
from xgboost import XGBRegressor
S=20261023
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PANEL=ROOT/'research_panel_reconstructed.csv'
OLD=ROOT/'walkforward_predictions.csv'
MONTHS=pd.period_range('2025-09','2026-08',freq='M').astype(str).tolist()
FEATURES=['yoy_m','yoy_3m','yoy_change1','growth_acceleration','mom_m','log_revenue',
 'season_sin','season_cos','revenue_vol3','market_code','revenue_sum6m',
 'revenue_mean12m','revenue_growth_6m','base_log_twd','base_to_recent_log']
NEW_NAMES=['xgb_yoy_mae','lgb_yoy_mae','cat_yoy_mae','lgb_level_log','cat_level_log','lgb_regime_gate','cat_regime_gate']
BASELINES=['combo_baseline','prior_xgb_l1','seasonal_zero','last_revenue_carry']

def checksum(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def add_features(df):
 df=df.copy()
 b=df.prior_target_revenue.to_numpy(float)
 mean=df.revenue_mean12m.to_numpy(float)
 df['base_log_twd']=np.log1p(np.maximum(b,0))
 # Feature only uses prior year's target month and current trailing revenue mean.
 df['base_to_recent_log']=np.clip(np.log(np.maximum(mean,1)/np.maximum(b,1)),-16.,16.)
 return df

def load():
 panel=pd.read_csv(PANEL,dtype={'symbol':str},low_memory=False)
 old=pd.read_csv(OLD,dtype={'symbol':str},low_memory=False)
 keys=['market','symbol','month']
 assert not panel.duplicated(keys).any() and not old.duplicated(keys).any()
 assert set(old.month)==set(MONTHS)
 assert not panel.published_at.notna().any() and not panel.pit_eligible.astype(bool).any()
 shared=old.merge(panel,on=keys,suffixes=('_orig',''),validate='one_to_one')
 shared=shared.loc[shared.eligible13.astype(bool)].copy()
 assert np.allclose(shared.y_orig,shared.y,atol=1e-4,rtol=1e-7)
 assert np.allclose(shared.yoy_m_orig,shared.yoy_m,atol=1e-3,rtol=1e-6)
 assert (shared.prior_target_revenue>0).all()
 assert (shared.groupby('month').size().reindex(MONTHS).fillna(0)>=100).all()
 return add_features(panel),add_features(shared),len(old)

def train_one(train,test):
 X=train[FEATURES].replace([np.inf,-np.inf],np.nan).astype('float32')
 Z=test[FEATURES].replace([np.inf,-np.inf],np.nan).astype('float32')
 y=train.y.to_numpy(float)
 prev=train.prior_target_revenue.to_numpy(float)
 assert np.min(y)>=-100.-1e-6 and (prev>0).all() and np.isfinite(y).all()
 nxt=prev*(1.+y/100.)
 assert np.isfinite(nxt).all() and np.min(nxt)>-1e-3
 logn=np.log1p(np.maximum(nxt,0))
 models={
  'xgb_yoy_mae':XGBRegressor(objective='reg:absoluteerror',n_estimators=100,max_depth=3,
         learning_rate=.05,min_child_weight=50,subsample=.8,colsample_bytree=.8,
         reg_lambda=20,tree_method='hist',n_jobs=2,random_state=S),
  'lgb_yoy_mae':LGBMRegressor(objective='regression_l1',n_estimators=100,learning_rate=.05,
        num_leaves=7,max_depth=3,min_child_samples=80,reg_lambda=20,colsample_bytree=.8,
        subsample=.8,subsample_freq=1,random_state=S,n_jobs=2,verbosity=-1),
  'cat_yoy_mae':CatBoostRegressor(loss_function='MAE',iterations=120,depth=3,
        learning_rate=.05,l2_leaf_reg=20,random_seed=S,thread_count=2,verbose=False,allow_writing_files=False),
  'lgb_level_log':LGBMRegressor(objective='regression_l2',n_estimators=100,learning_rate=.05,
        num_leaves=7,max_depth=3,min_child_samples=80,reg_lambda=20,colsample_bytree=.8,
        subsample=.8,subsample_freq=1,random_state=S,n_jobs=2,verbosity=-1),
  'cat_level_log':CatBoostRegressor(loss_function='RMSE',iterations=120,depth=3,
        learning_rate=.05,l2_leaf_reg=20,random_seed=S,thread_count=2,verbose=False,allow_writing_files=False)}
 preds={}
 for name,m in models.items():
  m.fit(X,logn if name.endswith('level_log') else y)
  pred=np.asarray(m.predict(Z),float)
  if name.endswith('level_log'):
   pred=100*(np.expm1(np.clip(pred,0.,60.))/test.prior_target_revenue.to_numpy(float)-1.)
   pred=np.maximum(-100.,pred)
  if not np.isfinite(pred).all():raise ValueError('NONFINITE '+name)
  preds[name]=pred
 # Fixed 10x relative-base heuristic OR 10th percentile, learned ONLY on training X.
 abs_q10=float(np.quantile(train.prior_target_revenue,0.1))
 lowbase=(test.prior_target_revenue.to_numpy(float)<abs_q10)|(
   test.revenue_mean12m.to_numpy(float)/test.prior_target_revenue.to_numpy(float)>10.)
 preds['lgb_regime_gate']=np.where(lowbase,preds['lgb_level_log'],preds['lgb_yoy_mae'])
 preds['cat_regime_gate']=np.where(lowbase,preds['cat_level_log'],preds['cat_yoy_mae'])
 preds['low_base_gate']=lowbase
 return preds,abs_q10

def run(months):
 panel,cohort,original_n=load()
 for month in months:
  assert month in MONTHS
  test=cohort.loc[cohort.month.eq(month)].sort_values(['market','symbol'])
  cutoff=pd.Timestamp(month+'-01')
  eligible=panel.eligible13.astype(bool)&panel.y.notna()&(panel.month<month)&(
      pd.to_datetime(panel.proxy_label_eligible_start)<=cutoff)
  train=panel.loc[eligible]
  assert train.month.nunique()>=12
  assert (pd.to_datetime(train.proxy_label_eligible_start)<=cutoff).all()
  assert train.month.max()<month
  p,th=train_one(train,test)
  out=test[['market','symbol','month','y','prior_target_revenue','revenue_twd',
            'market_code','yoy_m','combo_baseline','xgb_l1']].rename(columns={'xgb_l1':'prior_xgb_l1'}).copy()
  for c,v in p.items():out[c]=v
  out['seasonal_zero']=0.
  out['last_revenue_carry']=100*(out.revenue_twd/out.prior_target_revenue-1)
  out['publication_allowed']=False;out['pit_verified']=False
  out.to_csv(HERE/f'fold_{month}.csv',index=False,float_format='%.12g')
  meta={'month':month,'train_rows':len(train),'train_months':train.month.nunique(),
    'train_max_month':str(train.month.max()),
    'train_max_proxy_maturity':str(pd.to_datetime(train.proxy_label_eligible_start).max().date()),
    'test_rows':len(test),'low_base_cutoff_twd':th,'gate_n':int(p['low_base_gate'].sum()),
    'label_available':'CALENDAR_PROXY_ONLY','publication_allowed':False}
  (HERE/f'fold_{month}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
  print('PASS',month,'train',len(train),'test',len(test),'gate',meta['gate_n'],flush=True)

def score(df,col):
 z=df.loc[np.isfinite(df[col]),['month','y',col]]
 ae=(z.y-z[col]).abs()
 return {'model':col,'n':len(z),'month_equal_mae':float(ae.groupby(z.month).mean().mean()),
  'pooled_mae':float(ae.mean()),'median_ae':float(ae.median()),
  'p90_ae':float(ae.quantile(.9)),'top1pct_share':float(ae.nlargest(max(1,int(np.ceil(len(ae)*.01)))).sum()/ae.sum()),
  'publication_allowed':False}

def compare(df,a,b,boots=5000):
 x=df.loc[np.isfinite(df[a])&np.isfinite(df[b]),['month','y',a,b]]
 gain=((x.y-x[a]).abs()-(x.y-x[b]).abs()).groupby(x.month).mean().reindex(MONTHS)
 assert not gain.isna().any()
 vals=gain.to_numpy();rng=np.random.default_rng(S)
 out=np.empty(boots)
 for i in range(boots):
  ix=rng.integers(0,10,size=4)
  out[i]=np.concatenate([vals[j:j+3] for j in ix])[:12].mean()
 lo,hi=np.quantile(out,[.025,.975])
 return {'reference':a,'candidate':b,'n':len(x),'gain_pp':float(vals.mean()),
  'ci95_low':float(lo),'ci95_high':float(hi),'positive_months':int((vals>0).sum()),
  'block_months':3,'bootstrap_n':boots,'already_exposed_test':True,'publication_allowed':False}

def finalize():
 panel,cohort,original_n=load()
 files=[HERE/f'fold_{month}.csv' for month in MONTHS]
 if any(not f.is_file() for f in files):raise ValueError('INCOMPLETE_FOLDS')
 p=pd.concat([pd.read_csv(f,dtype={'symbol':str}) for f in files],ignore_index=True)
 assert len(p)==len(cohort)
 assert not p.duplicated(['market','symbol','month']).any()
 assert all((p.groupby('month').size()==cohort.groupby('month').size()))
 for x in NEW_NAMES+["prior_xgb_l1","seasonal_zero","last_revenue_carry"]:
  assert np.isfinite(p[x]).all(),x
 # A few prior combo predictions are genuinely missing: preserve NaN; paired CI uses intersection.
 assert not np.isinf(p["combo_baseline"]).any()
 summary=pd.DataFrame([score(p,c) for c in BASELINES+NEW_NAMES]).sort_values('month_equal_mae')
 month=pd.DataFrame([{'month':m,'model':c,'n':len(z),'mae':float((z.y-z[c]).abs().mean())}
   for m,z in p.groupby('month') for c in BASELINES+NEW_NAMES])
 pairs=[('combo_baseline',c) for c in NEW_NAMES]+[('xgb_yoy_mae','lgb_yoy_mae'),
   ('xgb_yoy_mae','cat_yoy_mae'),('lgb_yoy_mae','lgb_level_log'),
   ('cat_yoy_mae','cat_level_log'),('lgb_yoy_mae','lgb_regime_gate'),
   ('cat_yoy_mae','cat_regime_gate')]
 paired=pd.DataFrame([compare(p,*pr) for pr in pairs])
 slices=[]
 for m,z in p.groupby('month'):
  groups={'all':np.ones(len(z),bool),'low_base':z.low_base_gate.astype(bool).values,
    'non_low_base':~z.low_base_gate.astype(bool).values,
    'true_extreme_abs_y_ge1000':(z.y.abs()>=1000).values,
    'regular_abs_y_lt1000':(z.y.abs()<1000).values}
  for gn,g in groups.items():
   if not g.any():continue
   d=z.loc[g]
   for c in BASELINES+NEW_NAMES:
    err=np.abs(d.y-d[c]);slices.append({'month':m,'slice':gn,'model':c,
        'n':len(d),'mae':float(err.mean()),'ae_sum':float(err.sum())})
 # Original top 100 from combo not from challenger to avoid cherry-pick.
 top=p.assign(ae=np.abs(p.y-p.combo_baseline)).nlargest(100,'ae')
 top=top[['market','symbol','month','y','prior_target_revenue','revenue_twd','low_base_gate',
       'combo_baseline','xgb_yoy_mae','lgb_yoy_mae','cat_yoy_mae','lgb_level_log',
       'cat_level_log','lgb_regime_gate','cat_regime_gate']]
 for fn,frame in [('predictions.csv',p),('summary.csv',summary),('monthly.csv',month),
  ('paired.csv',paired),('slices.csv',pd.DataFrame(slices)),('top100.csv',top)]:
  frame.to_csv(HERE/fn,index=False,float_format='%.10g')
 meta={'status':'HISTORICAL_RETROSPECTIVE','publication_allowed':False,
  'data_original_old_n':original_n,'data_common_n':len(p),'coverage':len(p)/original_n,
  'months':MONTHS,'train_includes_financial':True,
  'pre_declared_label_handling':'DO_NOT_DROP_OR_WINSORIZE_TRUE_Y; model log-level alternative then reconvert original Y',
  'low_base_gate':'training-only q10 OR 10x trailing revenue / prior-year target month',
  'feature_order':FEATURES,'source_sha256':{str(i.name):checksum(i) for i in [PANEL,OLD]},
  'artifacts_sha256':{f.name:checksum(f) for f in HERE.glob('*.csv')},
  'pit':'historical published_at is missing; month-based proxy only',
  'test_is_previously_exposed':True,
  'versions':{'python':platform.python_version(),'pandas':pd.__version__,
    'numpy':np.__version__,'sklearn':sklearn.__version__,'lightgbm':lightgbm.__version__,
    'catboost':catboost.__version__,'xgboost':xgboost.__version__}}
 (HERE/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 print('COMPLETE',len(p),'COVERAGE',meta['coverage']);print(summary.to_string(index=False));print(paired.to_string(index=False))

if __name__=='__main__':
 if sys.argv[1]=='run':run(sys.argv[2:]);
 elif sys.argv[1]=='finalize':finalize();
 else:raise SystemExit('run month... | finalize')
