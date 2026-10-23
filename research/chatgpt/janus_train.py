"""Bounded four-role chronological research benchmark. Never promotes models."""
from __future__ import annotations
import hashlib, json, platform
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LogisticRegression, ElasticNet
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss,log_loss,roc_auc_score,average_precision_score
from xgboost import XGBRegressor,XGBClassifier,Booster,DMatrix
import janus_precision as p

SEED=20261023

def split(frame,role):
    """Unique time groups, purge actual/dependency maturity; no row-wise time split."""
    dates=pd.DatetimeIndex(sorted(frame.signal_group.unique()))
    daily=role in ('quant','risk');n=len(dates)
    mins=(120,20,20) if daily else (12,3,3)
    if n<sum(mins):return None,{'reason':'INSUFFICIENT_PERIODS','periods':n,'minimum':mins}
    nv=max(mins[1],int(n*.15));nt=max(mins[2],int(n*.15))
    vb=dates[-nv-nt];tb=dates[-nt]
    a=frame.signal_group<vb;b=(frame.signal_group>=vb)&(frame.signal_group<tb);c=frame.signal_group>=tb
    # For real publication-time panels, the earliest actual validation/test cutoff controls maturity.
    vc=frame.loc[b,'signal_at'].min();tc=frame.loc[c,'signal_at'].min()
    if pd.isna(vc) or pd.isna(tc):return None,{'reason':'MISSING_SIGNAL_CUTOFF'}
    a &= frame.mature_at.notna() & (frame.mature_at<vc)
    b &= frame.mature_at.notna() & (frame.mature_at<tc)
    masks=[a,b,c]
    counts=[int(frame.loc[z,'signal_group'].nunique()) for z in masks]
    # Minima apply AFTER maturity purge.
    meta={'validation_first_group':str(vb),'test_first_group':str(tb),
          'periods_after_purge':counts,'rows':[int(z.sum()) for z in masks],
          'symbols':[int(frame.loc[z,'symbol'].nunique()) for z in masks],
          'independence':'calendar groups; rows within dates are correlated'}
    if any(n<m for n,m in zip(counts,mins)):return None,{**meta,'reason':'INSUFFICIENT_AFTER_PURGE'}
    return masks,meta

def score(y,q,classification=False):
    y=np.asarray(y,float);q=np.asarray(q,float)
    if not np.isfinite(y).all() or not np.isfinite(q).all():raise ValueError('NONFINITE_SCORE')
    if classification:
        q=np.clip(q,1e-7,1-1e-7)
        return {'brier':float(brier_score_loss(y,q)),'logloss':float(log_loss(y,q,labels=[0,1])),
                'roc_auc':float(roc_auc_score(y,q)) if len(np.unique(y))==2 else None,
                'pr_auc':float(average_precision_score(y,q)) if len(np.unique(y))==2 else None}
    return {'mae':float(np.mean(abs(y-q))),'rmse':float(np.sqrt(np.mean((y-q)**2))),
            'median_absolute_error':float(np.median(abs(y-q)))}

def block_gain(frame,y,base,candidate,role):
    """Paired loss difference, equal-date mean, moving time blocks."""
    loss=lambda z:(y-z)**2 if role=='quant' else abs(y-z)
    s=pd.DataFrame({'date':frame.signal_group,'gain':loss(base)-loss(candidate)}).groupby('date').gain.mean().to_numpy()
    block=20 if role in ('quant','risk') else 3
    if len(s)<max(2*block,12):return {'state':'INSUFFICIENT_TIME_BLOCKS','dates':len(s),'block':block}
    rng=np.random.default_rng(SEED);means=[]
    for _ in range(500):
        starts=rng.integers(0,len(s)-block+1,size=int(np.ceil(len(s)/block)))
        sample=np.concatenate([s[i:i+block] for i in starts])[:len(s)]
        means.append(float(sample.mean()))
    lo,hi=np.quantile(means,[.025,.975])
    return {'state':'POSITIVE_GAIN' if lo>0 else 'INCONCLUSIVE','mean_gain':float(s.mean()),
            'ci95':[float(lo),float(hi)],'block':block,'dates':len(s),'resamples':500}

def _serialize_linear(model,path,features):
    scale,fit=model.steps[0][1],model.steps[1][1]
    p.write_json(path,{'features':features,'scaler_mean':scale.mean_.tolist(),
        'scaler_scale':scale.scale_.tolist(),'coef':np.asarray(fit.coef_).tolist(),
        'intercept':np.asarray(fit.intercept_).tolist(),'type':type(fit).__name__,
        'classes':fit.classes_.tolist() if hasattr(fit,'classes_') else None})

def fit_one(frame,features,role,out,target='y',max_trees=400):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if role=='valuation' and set(features)!=set(p.VAL):raise ValueError('VALUATION_ALLOWLIST')
    if any(c.startswith(('target','forward','future','label')) for c in features):raise ValueError('Y_IN_X')
    ok=frame.reason.eq('OK')&np.isfinite(frame[features]).all(axis=1)&np.isfinite(frame[target])
    d=frame.loc[ok].copy().reset_index(drop=True)
    masks,info=split(d,role)
    p.write_json(out/'split_manifest.json',info)
    result={'state':'NOT_TRAINED','target':target,'role':role,'eligible_rows':len(d),
            'split':info,'publication_allowed':False,'calibration':'NOT_FITTED_RAW_RESEARCH_SCORE'}
    if masks is None:return {**result,'state':info['reason']}
    tr,va,te=masks;X=d[features].astype('float32');y=d[target].astype(float)
    xt,xv,xh=X.loc[tr],X.loc[va],X.loc[te];yt,yv,yh=y.loc[tr],y.loc[va],y.loc[te]
    classification=role=='quant'
    if classification and yt.nunique()<2:return {**result,'state':'TRAIN_SINGLE_CLASS'}
    baseline_val={};baseline_test={}
    if role=='quant':
        baseline_val['prevalence']=np.full(len(yv),yt.mean());baseline_test['prevalence']=np.full(len(yh),yt.mean())
        linear_names=['logistic']
    elif role=='risk':
        baseline_val['rolling20']=d.loc[va,'vol20'].to_numpy();baseline_test['rolling20']=d.loc[te,'vol20'].to_numpy()
        linear_names=['ridge5','ridge8']
    elif role=='fundamental':
        baseline_val={'growth_persistence':d.loc[va,'yoy_m'].to_numpy(),'seasonal_zero':np.zeros(len(yv))}
        baseline_test={'growth_persistence':d.loc[te,'yoy_m'].to_numpy(),'seasonal_zero':np.zeros(len(yh))}
        linear_names=['elastic_net']
    else:
        # Caller separates financial cohorts; train-only market median within cohort.
        med=d.loc[tr].groupby('market')[target].median();fallback=float(yt.median())
        baseline_val['train_cohort_median']=d.loc[va,'market'].map(med).fillna(fallback).to_numpy()
        baseline_test['train_cohort_median']=d.loc[te,'market'].map(med).fillna(fallback).to_numpy()
        linear_names=['ridge']
    for name in linear_names:
        feats=p.RISK[:5] if name=='ridge5' else features
        base=(LogisticRegression(max_iter=1000,random_state=SEED) if classification else
              ElasticNet(alpha=.1,l1_ratio=.1,max_iter=3000) if name=='elastic_net' else Ridge(alpha=10))
        linear=make_pipeline(StandardScaler(),base);linear.fit(xt[feats],yt)
        fn=lambda z:linear.predict_proba(z)[:,1] if classification else linear.predict(z)
        a,b=fn(xv[feats]),fn(xh[feats])
        if role=='risk':a=np.maximum(a,0);b=np.maximum(b,0)
        baseline_val[name]=a;baseline_test[name]=b
        _serialize_linear(linear,out/(name+'.json'),feats)
    metric='brier' if classification else 'mae'
    # Select comparator on validation; never choose baseline by final-test score.
    val_metrics={k:score(yv,v,classification) for k,v in baseline_val.items()}
    best_base=min(val_metrics,key=lambda k:val_metrics[k][metric])
    params=dict(max_depth=3 if role in ('quant','risk') else 2,learning_rate=.05,
        n_estimators=max_trees,min_child_weight=25 if role in ('quant','risk') else 50,
        subsample=.8,colsample_bytree=1. if role=='risk' else .8,
        reg_lambda=10 if role in ('quant','risk') else 20,random_state=SEED,n_jobs=4,
        tree_method='hist',device='cpu',early_stopping_rounds=30,
        eval_metric='logloss' if classification else 'mae')
    cls=XGBClassifier if classification else XGBRegressor
    model=cls(objective='binary:logistic' if classification else 'reg:squarederror',**params)
    model.fit(xt,yt,eval_set=[(xv,yv)],verbose=False)
    # Save only effective trees; Booster inference cannot accidentally use post-best trees.
    booster=model.get_booster()[:model.best_iteration+1]
    dest=out/'model.ubj';booster.save_model(dest)
    loaded=Booster();loaded.load_model(dest)
    raw=booster.predict(DMatrix(xh));reload=loaded.predict(DMatrix(xh))
    if not np.allclose(raw,reload,atol=1e-6,rtol=1e-6):raise ValueError('UBJ_PARITY')
    pred=np.maximum(raw,0) if role=='risk' else raw
    preds={**baseline_test,'xgboost':pred}
    metrics={k:score(yh,v,classification) for k,v in preds.items()}
    table=d.loc[te,p.KEY+['signal_group','signal_at','mature_at']].copy();table['actual']=yh
    for k,v in preds.items():table[k]=v
    table.to_parquet(out/'test_predictions.parquet',index=False)
    groups={}
    slice_tags={'market':table.market,'month':table.signal_group.dt.to_period('M').astype(str)}
    if role in ('quant','risk'):
        for field,axis in [('log_turnover20','liquidity'),('vol20','volatility')]:
            q=d.loc[tr,field].quantile([.25,.75]).to_numpy()
            slice_tags[axis]=pd.Series(np.where(d.loc[te,field]<q[0],'LOW',
                np.where(d.loc[te,field]>q[1],'HIGH','MID')),index=table.index)
    for axis,tags in slice_tags.items():
        groups[axis]={}
        for tag,index in tags.groupby(tags).groups.items():
            block=table.loc[index]
            groups[axis][str(tag)]={'rows':len(block),'dates':int(block.signal_group.nunique()),
                'metrics':{k:score(block.actual,block[k],classification) for k in preds}}
    if classification:
        table['bin']=pd.cut(table.xgboost,bins=np.linspace(0,1,11),include_lowest=True)
        cal=table.groupby('bin',observed=True).agg(n=('actual','size'),mean_score=('xgboost','mean'),actual_rate=('actual','mean'))
        cal.to_csv(out/'calibration_bins.csv',encoding='utf-8-sig')
    interval=block_gain(d.loc[te],yh.to_numpy(),baseline_test[best_base],pred,role)
    review=[]
    for m,g in groups['market'].items():
        base=g['metrics'][best_base][metric];cand=g['metrics']['xgboost'][metric]
        if cand>base*1.05:review.append(m)
    result.update(state='RESEARCH_EVALUATED',metrics=metrics,validation_baselines=val_metrics,
        selected_baseline=best_base,by_slice=groups,paired_time_gain=interval,
        market_review_required=review,best_iteration=int(model.best_iteration),
        model_sha256=p.sha(dest),retrospective=True)
    p.write_json(out/'model_schema.json',{'features':features,'dtype':'float32','target':target,
       'role':role,'best_iteration':int(model.best_iteration),'saved_tree_count':int(model.best_iteration+1),
       'output_transform':'max(0, raw)' if role=='risk' else 'exp(raw) reference multiple' if role=='valuation' else 'identity',
       'publication_allowed':False,'model_sha256':p.sha(dest)})
    p.write_json(out/'test_vectors.json',{'X':xh.iloc[:8].values.tolist(),
        'raw_predictions':raw[:8].tolist(),'output_predictions':pred[:8].tolist(),'atol':1e-6})
    latest=frame.loc[frame.reason.eq('OK')&np.isfinite(frame[features]).all(axis=1)].sort_values('signal_at').groupby(p.KEY).tail(1)
    if not latest.empty:
        lp=loaded.predict(DMatrix(latest[features].astype('float32')))
        z=latest[p.KEY+['signal_group','signal_at','mature_at']].copy()
        z['raw_score']=lp;z['prediction']=np.maximum(lp,0) if role=='risk' else lp
        z['status']='RESEARCH_ONLY';z['publication_allowed']=False
        if role=='quant':z['calibrated_probability']=np.nan
        if role=='valuation':z['reference_multiple']=np.exp(lp)
        if role=='risk':
            z['baseline_vol20']=latest.vol20
            z['ratio']=z.prediction/z.baseline_vol20.where(z.baseline_vol20>0)
        z.to_parquet(out/'latest_research_predictions.parquet',index=False)
    return result

def run(root,output_root,role,mode='retrospective',horizon=20,financial_mapping=None,max_trees=400):
    if not 1<=max_trees<=500:raise ValueError('TREE_BUDGET')
    kinds={'quant':['ohlcv'],'risk':['ohlcv'],'fundamental':['revenue'],
           'valuation':['valuation','financials','ohlcv']}[role]
    data,receipt=p.load_release(root,kinds)
    deps={x:__import__(x).__version__ for x in ['numpy','pandas','sklearn','xgboost','pyarrow']}
    config={'version':p.VERSION,'role':role,'mode':mode,'horizon':horizon,'max_trees':max_trees,
        'financial_mapping':financial_mapping,'seed':SEED,'dependencies':deps,
        'core_sha':p.sha(__file__),'precision_sha':p.sha(p.__file__),
        'factory_sha':p.sha(p.legacy.__file__),'publication_allowed':False}
    fingerprint=hashlib.sha256(json.dumps([receipt,config],sort_keys=True).encode()).hexdigest()[:16]
    out=Path(output_root)/role/('v3.8.1-'+fingerprint)
    marker=out/'artifact_manifest.json'
    if marker.exists():
        m=json.loads(marker.read_text())
        for rel,h in m['files'].items():
            if p.sha(p.safe_path(out,rel))!=h:raise ValueError('CACHE_HASH '+rel)
        return json.loads((out/'reports/result.json').read_text()),out
    out.mkdir(parents=True,exist_ok=True)
    for d in ['control','data','reports','models']:(out/d).mkdir(exist_ok=True)
    p.write_json(out/'control/config.json',config);p.write_json(out/'control/input_manifest.json',receipt)
    p.write_json(out/'control/evaluation_plan.json',{'model_search':'one predeclared XGB config, validation early stopping',
        'test_use':'once per fingerprint; historical test is RETROSPECTIVE, not pristine',
        'main_metric':'brier' if role=='quant' else 'MAE',
        'minimum_independent_periods_after_purge':[120,20,20] if role in ('quant','risk') else [12,3,3],
        'block_length':20 if role in ('quant','risk') else 3,
        'market_degradation_review':.05,'publication_allowed':False})
    report={'role':role,'state':'NOT_TRAINED','publication_allowed':False,'input':receipt,
            'mode':mode,'pit_status':'NOT_VERIFIED','retrospective':True}
    try:
        if any(d.empty for d in data.values()):
            report['state']='MISSING_REQUIRED_TABLE'
        else:
            frame,features=p.training_panel(data,role,mode,horizon,financial_mapping)
            # Physically separate allowlisted X from all Y, context and outcome columns.
            keys=p.KEY+['signal_group']
            frame[keys+features].to_parquet(out/'data/X.parquet',index=False)
            ycols=[c for c in ['y','y_pe','y_pb'] if c in frame]
            frame[keys+['signal_at','mature_at','reason']+ycols].to_parquet(out/'data/Y_NOT_X.parquet',index=False)
            report['raw_rows']=len(frame);report['reason_counts']=frame.reason.value_counts().to_dict()
            report['missing_features']={c:int(frame[c].isna().sum()) for c in features}
            results={}
            tasks=[('main',frame,'y')]
            if role=='valuation':
                tasks=[]
                for cohort,g in frame.loc[frame.cohort.ne('UNKNOWN')].groupby('cohort'):
                    if not re_safe(cohort):raise ValueError('UNSAFE_COHORT_NAME')
                    if g.symbol.nunique()<10 or g.signal_group.nunique()<12:
                        results[cohort]={'state':'INSUFFICIENT_COHORT'};continue
                    tasks.extend([(cohort+'_'+t,g,'y_'+t) for t in ['pe','pb']])
            for name,block,target in tasks:
                results[name]=fit_one(block,features,role,out/'models'/name,target,max_trees)
            report['models']=results
            report['state']='RESEARCH_EVALUATED' if any(r['state']=='RESEARCH_EVALUATED' for r in results.values()) else 'BLOCKED_OR_INSUFFICIENT'
            if role=='valuation':report['limitation']='Month-end must match market calendar; older months without session evidence remain excluded. No scenario price without independently sourced EPS/BVPS.'
    except Exception as exc:
        report.update(state='FAILED',error_type=type(exc).__name__,reason=str(exc))
        p.write_json(out/'reports/result.json',report)
        raise
    p.write_json(out/'reports/result.json',report)
    files={str(x.relative_to(out)):p.sha(x) for x in out.rglob('*') if x.is_file() and x!=marker}
    p.write_json(marker,{'files':files,'publication_allowed':False,'fingerprint':fingerprint})
    return report,out

def re_safe(name):
    import re
    return bool(re.fullmatch('[A-Za-z0-9_-]{1,60}',str(name)))
