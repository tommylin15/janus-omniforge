#!/usr/bin/env python3
"""Janus research-only: exclude exactly top 2/5/10% training rows by train-only max abs numeric z.
Historical retrospective replay, frozen r1 reference. No canonical/Registry/deployment changes.
"""
from pathlib import Path
import sys, json, hashlib, zipfile, time, os
import numpy as np, pandas as pd
from scipy.special import expit
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, log_loss
sys.path.insert(0,str(Path(__file__).resolve().parent))
from reader import decode_column,get_meta
ROOT=Path(os.environ.get('JANUS_QUANT_RESEARCH_INPUT_ROOT','/mnt/data')).resolve()
OUT=Path(os.environ.get('JANUS_QUANT_RESEARCH_OUTPUT_ROOT',str(ROOT/'quant_outlier_row_exclusion'))).resolve()
OUT.mkdir(parents=True,exist_ok=True)
X=ROOT/'X.parquet.bin';Y=ROOT/'Y_NOT_X.parquet.bin'
sha=lambda f:hashlib.file_digest(open(f,'rb'),'sha256').hexdigest()
assert sha(X)=='1b5c2cdd6f7b48427f81351ece2a855f4b97d44d89606ecd0f3fe29f5f8403ae'
assert sha(Y)=='e00b92ee1eb0d651b4baa5c28c2fa81dc9de6679b7e3e1b37a9a6ce1d1f44d5e'
if os.environ.get('JANUS_QUANT_RESEARCH_EVIDENCE_JSON'):
  proof=json.loads(Path(os.environ['JANUS_QUANT_RESEARCH_EVIDENCE_JSON']).read_text())
  FROZEN=proof['model_expanding12']
  MANIFEST=proof['manifest']
else:
  with zipfile.ZipFile(ROOT/'Janus_Quant_202607_forward_simulation_研究包.zip') as z:
   FROZEN=json.loads(z.read('research_results/model_expanding12.json'))
   MANIFEST=json.loads(z.read('research_results/simulation_manifest.json'))
F=FROZEN['features'];NUM=[i for i,k in enumerate(F) if k!='market_code']
assert F==MANIFEST['features_12']
assert MANIFEST['research_model_artifact_shas']['expanding12']=='2f693b1268b525e51560f1b45f7262e6756f4faadaf02fea02628c66de4b8b11'
D={}
for fn,fields in [(X,['market','symbol','signal_group']+F),(Y,['market','symbol','signal_group','mature_at','reason','y'])]:
 meta=get_meta(fn)
 for c in fields:
  col=decode_column(fn,meta,c)
  if c in ('market','symbol','reason'):col=np.array([k.decode() if isinstance(k,bytes) else k for k in col],dtype='U16')
  elif c in ('signal_group','mature_at'):col=pd.to_datetime(col,unit='ns')
  else:col=pd.to_numeric(col,errors='coerce')
  if c in D:
   assert np.array_equal(D[c],col),f'PARQUET_KEY_MISMATCH_{c}'
  else:D[c]=col
print('decoded',len(D['y']),flush=True)
d=pd.DataFrame(D)
valid=np.isfinite(d[F].to_numpy(dtype='float64')).all(axis=1)&d.reason.eq('OK')&d.y.notna()
cut=pd.Timestamp('2026-07-01');end=pd.Timestamp('2026-09-30')
train=valid&d.signal_group.lt(cut)&d.mature_at.lt(cut)
eval=valid&d.signal_group.ge(cut)&d.signal_group.le(end)&d.mature_at.le(end)
assert (int(train.sum()),int(eval.sum()))==(466823,76237)
xt=d.loc[train,F].to_numpy(dtype='float32');yt=d.loc[train,'y'].to_numpy(dtype='int8')
xv=d.loc[eval,F].to_numpy(dtype='float32');yv=d.loc[eval,'y'].to_numpy(dtype='int8')
dates=d.loc[eval,'signal_group'].reset_index(drop=True)
markets=d.loc[eval,'market'].to_numpy();syms=d.loc[eval,'symbol'].to_numpy()
assert dates.nunique()==43 and np.isin(np.unique(yv),[0,1]).all()
mu=np.asarray(FROZEN['scaler_mean']);sd=np.asarray(FROZEN['scaler_scale'])
coef=np.asarray(FROZEN['coefficients'][0]);itc=FROZEN['intercepts'][0]
p_ref=expit(((xv.astype('float64')-mu)/sd)@coef+itc)

# primary outcome: date-equal Brier for identical all-stock evaluation cohort
labels=['r1_frozen','exclude_2pct','exclude_5pct','exclude_10pct','constant_r1','constant_candidate']
def dailyloss(p):
 return pd.Series((p-yv)**2).groupby(dates).mean().sort_index()
def stats(p,ix=None):
 if ix is None:ix=np.ones(len(yv),dtype=bool)
 vals=(p[ix]-yv[ix])**2
 date=dates.loc[ix].reset_index(drop=True)
 bydate=pd.Series(vals).groupby(date).mean().sort_index()
 return {'rows':int(ix.sum()),'dates':int(len(bydate)), 'brier_date_equal':float(bydate.mean()),'brier_row':float(np.mean(vals)),
  'auc_pooled':float(roc_auc_score(yv[ix],p[ix])) if len(np.unique(yv[ix]))>1 else None,
  'logloss_row':float(log_loss(yv[ix],np.clip(p[ix],1e-8,1-1e-8),labels=[0,1])),
  'positive_rate':float(yv[ix].mean()),'mean_prediction':float(p[ix].mean())}

def boot(gain,seed=1,resamples=5000):
 vals=gain.to_numpy(dtype='float64');n=len(vals);out={}
 for block in (10,20,30):
  if n<2*block:
   out[str(block)]={'status':'INSUFFICIENT_BLOCKS','CI95':None,'market_days':n};continue
  rng=np.random.default_rng(seed+block)
  draws=np.empty(resamples)
  count=int(np.ceil(n/block))
  for i in range(resamples):
   starts=rng.integers(n-block+1,size=count)
   idx=(starts[:,None]+np.arange(block)[None,:]).ravel()[:n]
   draws[i]=float(vals[idx].mean())
  out[str(block)]={'status':'EXPLORATORY_DEVELOPMENT_ONLY','CI95':np.quantile(draws,[.025,.975]).tolist(),'market_days':n,'resamples':resamples}
 return out

ref_stat=stats(p_ref)
prevalence=yt.mean()
base_const=np.full(len(yv),prevalence,dtype='float64')
res={'study':'QUANT_R1_TRAIN_ROW_EXCLUSION_20261024','research_only':True,'publication_allowed':False,
 'model_version':'quant-up20-logistic12-expanding-20260701-r1','source_sha256':{'X':sha(X),'Y':sha(Y)},'r1_artifact_sha256':MANIFEST['research_model_artifact_shas']['expanding12'],
 'method':{'ranking':'max absolute StandardScaler z-score over 11 numeric training factors; excludes market_code','fitted_thresholds':'reference training only before 2026-07-01; 11 numeric features, no Y used for ranking','remove_policy':'exact floor(N*percentage) training rows; stable sort for ties','evaluation':'all same 76,237 matured 2026/07-08 rows kept, unchanged features and Y, no filter, no retraining on postcut Y','validation_policy':'fixed 2/5/10% settings per user; no other hyperparameters, no winner selected for release', 'definition':'2%, 5%, 10% refer to fraction of training rows removed, NOT per-factor two-sided tail percentiles'},
 'training_original_rows':len(yt),'eval_rows':len(yv),'eval_days':int(dates.nunique()),'reference_frozen_r1':ref_stat,'reference_constant_prevalence':float(prevalence),'reference_constant':stats(base_const),
 'model_reproduction_max_abs_diff':None,'candidates':{},'source_limitations':['2026/07-08 data already viewed; retrospective development only, not new untouched OOS','PIT/market calendar and corporate-action adjustment unverified','Extreme scores indicate magnitude, not verified erroneous data; no source OHLCV row-level cross-check']}
# verify refit for confidence; strictly isolated training
m0=make_pipeline(StandardScaler(),LogisticRegression(C=1,solver='lbfgs',max_iter=1000,random_state=20261023))
m0.fit(xt,yt)
p_local=m0.predict_proba(xv)[:,1]
res['model_reproduction_max_abs_diff']=float(np.max(np.abs(p_local-p_ref)))
assert res['model_reproduction_max_abs_diff']<1e-6,res['model_reproduction_max_abs_diff']
# Scaler mean and std only from training period (match verified frozen scaler).
scores=np.abs((xt[:,NUM].astype('float64')-mu[NUM])/sd[NUM]).max(axis=1)
assert np.isfinite(scores).all()
# Stable deterministic ordering without looking at labels or evaluation data
order=np.argsort(-scores,kind='stable')
daily=pd.DataFrame({'signal_date':dates.dt.strftime('%Y-%m-%d'),'market':markets,'symbol':syms,'Y':yv,
                    'p_r1':p_ref,'p_constant_r1':base_const})
for p in (.02,.05,.10):
 n=int(np.floor(p*len(yt)))
 keep=np.ones(len(yt),dtype=bool);keep[order[:n]]=False
 assert keep.sum()+n==len(yt)
 m=make_pipeline(StandardScaler(),LogisticRegression(C=1,solver='lbfgs',max_iter=1000,random_state=20261023))
 t0=time.monotonic()
 m.fit(xt[keep],yt[keep]);pred=m.predict_proba(xv)[:,1]
 tr_prevalence=float(yt[keep].mean());candidate_constant=np.full(len(yv),tr_prevalence)
 gain=dailyloss(p_ref)-dailyloss(pred)
 level=int(p*100)
 daily[f'p_exclude_{level}pct']=pred
 dropped_feats=np.argmax(np.abs((xt[order[:n],:][:,NUM].astype('float64')-mu[NUM])/sd[NUM]),axis=1)
 vstats={k:stats(pred,markets==k) for k in sorted(np.unique(markets))}
 by_month={mth:stats(pred,(dates.dt.strftime('%Y-%m')==mth).to_numpy()) for mth in sorted(dates.dt.strftime('%Y-%m').unique())}
 res['candidates'][f'exclude_{level}pct']={
  'percent_target':p,'removed_rows':n,'removed_fraction':n/len(yt),'retained_rows':int(keep.sum()),
  'removed_max_abs_z_min':float(np.min(scores[order[:n]])),'retained_max_abs_z_max':float(np.max(scores[keep])),
  'removed_original_y_positive_rate':float(yt[~keep].mean()),'retained_y_positive_rate':tr_prevalence,
  'max_abs_z_dominant_feature_removed':{F[NUM[j]]:int(np.sum(dropped_feats==j)) for j in range(len(NUM))},
  'eval':stats(pred),'eval_constant_same_r1':stats(base_const),'eval_constant_candidate_train_prevalence':stats(candidate_constant),
  'gain_vs_r1_date_equal':float(gain.mean()),'gain_vs_same_r1_constant_date_equal':float(dailyloss(base_const).mean()-dailyloss(pred).mean()),
  'gain_vs_candidate_constant_date_equal':float(dailyloss(candidate_constant).mean()-dailyloss(pred).mean()),
  'paired_block_bootstrap_gain_vs_r1':boot(gain,seed=20261024+level),'mean_abs_probability_delta_vs_r1':float(np.mean(np.abs(pred-p_ref))),
  'metrics_by_month':by_month,'metrics_by_market':vstats,
  'training_model_parameters':{'coefs':m.named_steps['logisticregression'].coef_[0].tolist(),
    'intercept':float(m.named_steps['logisticregression'].intercept_[0]),
    'scaler_mean':m.named_steps['standardscaler'].mean_.tolist(),
    'scaler_scale':m.named_steps['standardscaler'].scale_.tolist()},'fit_seconds':round(time.monotonic()-t0,3)}
 daily[f'p_constant_candidate_{level}pct']=candidate_constant
 print('CANDIDATE',level,'drop',n,'remaining',int(keep.sum()),'Brier',res['candidates'][f'exclude_{level}pct']['eval']['brier_date_equal'],'vs r1 gain',res['candidates'][f'exclude_{level}pct']['gain_vs_r1_date_equal'],flush=True)
 # train rows provenance sample aggregate, do not embed private transactional data
# summarize per-date daily comparison; cohort identical
predcols=[c for c in daily if c.startswith('p_')]
daily_brier=pd.DataFrame({'signal_date':sorted(daily.signal_date.unique())})
for c in predcols:
 vals=(daily[c]-daily.Y)**2
 tmp=pd.DataFrame({'date':daily.signal_date,'loss':vals}).groupby('date').loss.mean()
 daily_brier[c+'_brier']=daily_brier.signal_date.map(tmp)
daily_brier.to_csv(OUT/'metrics_by_signal_date.csv',index=False)
daily[['signal_date','market','symbol','Y']+predcols].to_csv(OUT/'prediction_comparison.csv.gz',index=False,compression='gzip')
res['comparisons_md_rows']={k:{'brier':v['eval']['brier_date_equal'],'auc':v['eval']['auc_pooled'],'retained_rows':v['retained_rows'],'removed_rows':v['removed_rows']} for k,v in res['candidates'].items()}
(OUT/'experiment_results.json').write_text(json.dumps(res,indent=2,ensure_ascii=False),encoding='utf-8')
print('REFERENCE',ref_stat,'constant',res['reference_constant'],'reproduction',res['model_reproduction_max_abs_diff'],flush=True)
print('OUTPUT',OUT,'files',list(f.name for f in OUT.iterdir()),flush=True)