#!/usr/bin/env python3
"""Janus Quant historical 'prospective-style' replay, research-only.

All models are frozen BEFORE 2026-07-01, using only labels whose actual
mature_at is strictly earlier than that cutoff. Predictions are reconstructed
now, NOT previously issued in 2026. No mutation of canonical, Risk or registry.

Usage with normal pyarrow:
  python quant_forward_jul2026.py --x X.parquet --y Y_NOT_X.parquet --out DIR
Local fallback ONLY after verifying original Parquet SHA:
  python quant_forward_jul2026.py --x X.parquet.bin --y Y_NOT_X.parquet.bin \
    --trusted-x-pkl X.pkl --trusted-y-pkl Y_NOT_X.pkl --out DIR
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, log_loss

SEED = 20261023
CUT = pd.Timestamp('2026-07-01')
LAST = pd.Timestamp('2026-09-30')
EXPECT = {
 'X': '1b5c2cdd6f7b48427f81351ece2a855f4b97d44d89606ecd0f3fe29f5f8403ae',
 'Y': 'e00b92ee1eb0d651b4baa5c28c2fa81dc9de6679b7e3e1b37a9a6ce1d1f44d5e',
}
F12=['ret5','ret20','ma20_distance','ma60_distance','vol20','vol60','drawdown60',
     'volume_ratio20','log_turnover20','market_code','ret10','bollinger_z20']
F15=['ret5','ret20','ret60','ma20_distance','ma60_distance','vol20','vol60',
     'drawdown60','volume_ratio20','log_turnover20','market_code','ret10',
     'ret120','bollinger_z20','ret20_market_rank']
KEY=['market','symbol','signal_group']

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()

def tojson(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True,
                         allow_nan=False,default=str)+'\n',encoding='utf-8')

def read_source(path,raw_sha,decoded):
    assert sha(path)==EXPECT[raw_sha],f'{raw_sha} SHA_MISMATCH'
    if decoded:
        # Local compatibility only. Pickle is untrusted: use ONLY from the
        # locally generated and already verified Decoded Stage05.1 material.
        obj=pd.read_pickle(decoded)
        print(f'[local fallback] {raw_sha} decoded pickle used after raw hash check; not canonical')
    else:
        obj=pd.read_parquet(path)
    return obj

def fit(d, mask, features, label):
    z=d.loc[mask]
    if len(z)==0 or z.y.nunique()!=2: raise RuntimeError(label+': bad training labels')
    model=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,random_state=SEED,
                solver='lbfgs',max_iter=1000))
    model.fit(z[features].astype('float32'),z.y.astype('int8'))
    predmean=float(z.y.mean())
    return model,{'model':label,'features':features,'train_rows':int(len(z)),
                  'train_dates':int(z.signal_group.nunique()),
                  'train_start':str(z.signal_group.min().date()),
                  'train_end':str(z.signal_group.max().date()),
                  'latest_training_label_mature_at':str(z.mature_at.max().date()),
                  'train_prevalence':predmean,
                  'train_symbols':int(z.symbol.nunique()),
                  'cutoff_exclusive':str(CUT.date()),
                  'fit_y_maturity_guard':bool((z.mature_at<CUT).all()),
                  'solver':'LogisticRegression lbfgs C=1.0; StandardScaler fit only on training'}

def brier(a, col):
    return float(np.mean((a.y.to_numpy()-a[col].to_numpy())**2)) if len(a) else None

def date_brier(a,col):
    if not len(a):return None
    return float(a.assign(loss=(a.y-a[col])**2).groupby('signal_group',observed=True).loss.mean().mean())

def auc(a, col):
    if len(a)==0 or a.y.nunique()!=2:return None
    return float(roc_auc_score(a.y,a[col]))

def score(a,col):
    a=a.loc[a[col].notna()].copy()
    if not len(a):return {'rows':0,'signal_dates':0,'brier_date_equal':None}
    day=a.assign(loss=(a.y-a[col])**2).groupby('signal_group',observed=True).loss.mean()
    a_daily=[]
    for dt,g in a.groupby('signal_group',observed=True):
        if g.y.nunique()==2:a_daily.append(roc_auc_score(g.y,g[col]))
    return {'rows':int(len(a)),'signal_dates':int(len(day)),
            'brier_date_equal':float(day.mean()),'brier_pooled_row_weighted':brier(a,col),
            'logloss_pooled':float(log_loss(a.y,np.clip(a[col].to_numpy(),1e-7,1-1e-7),labels=[0,1])),
            'auc_pooled':auc(a,col),
            'auc_daily_mean':float(np.mean(a_daily)) if a_daily else None,
            'mean_prediction':float(a[col].mean()),'positive_rate':float(a.y.mean())}

def paired_ci(a,first,second,block,b=2000):
    t=a[['signal_group','y',first,second]].dropna()
    t=t.assign(delta=(t.y-t[first])**2-(t.y-t[second])**2)
    daily=t.groupby('signal_group',observed=True).delta.mean().sort_index().to_numpy()
    n=len(daily)
    if n<2*block:return {'block':block,'dates':n,'status':'INSUFFICIENT_BLOCKS',
                         'mean_gain_second_vs_first':float(daily.mean()) if n else None,'ci95':None}
    rng=np.random.default_rng(SEED+block)
    means=[]
    for _ in range(b):
        starts=rng.integers(0,n-block+1,size=int(np.ceil(n/block)))
        ix=np.concatenate([np.arange(s,s+block) for s in starts])[:n]
        means.append(float(daily[ix].mean()))
    lo,hi=np.quantile(means,[.025,.975])
    return {'block':block,'dates':n,'status':'EXPLORATORY_ONLY_DEVELOPMENT_PERIOD',
      'resamples':b,'mean_gain_second_vs_first':float(daily.mean()),
      'ci95':[float(lo),float(hi)],'ci_includes_zero':bool(lo<=0<=hi)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--x',required=True);p.add_argument('--y',required=True)
    p.add_argument('--trusted-x-pkl');p.add_argument('--trusted-y-pkl')
    p.add_argument('--out',required=True)
    args=p.parse_args()
    if bool(args.trusted_x_pkl)!=bool(args.trusted_y_pkl):raise ValueError('PICKLE_PAIR_REQUIRED')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    xx=read_source(args.x,'X',args.trusted_x_pkl)
    yy=read_source(args.y,'Y',args.trusted_y_pkl)
    if len(xx)!=len(yy):raise ValueError('KEY_LENGTH_MISMATCH')
    if not xx[KEY].reset_index(drop=True).astype(str).equals(yy[KEY].reset_index(drop=True).astype(str)):
        raise ValueError('KEY_ALIGNMENT_FAILED')
    if xx.duplicated(KEY).any() or yy.duplicated(KEY).any():raise ValueError('DUPLICATE_KEYS')
    d=xx.copy()
    for c in ['signal_at','mature_at','reason','y']:d[c]=yy[c]
    for c in ['signal_group','signal_at','mature_at']:d[c]=pd.to_datetime(d[c],errors='raise')
    reason_ok=d.reason.astype(str).eq('OK')
    finite12=np.isfinite(d[F12].to_numpy(dtype='float64')).all(axis=1)
    finite15=np.isfinite(d[F15].to_numpy(dtype='float64')).all(axis=1)
    eligible_train=(d.signal_group<CUT)&(d.mature_at<CUT)&d.y.notna()&reason_ok
    tr12=eligible_train&finite12
    tr15=eligible_train&finite15
    recent_dates=pd.DatetimeIndex(sorted(d.loc[tr12,'signal_group'].unique()))[-120:]
    if len(recent_dates)<120:raise ValueError('NOT_ENOUGH_MATURE_120_DATES')
    tr120=tr12&d.signal_group.isin(recent_dates)
    print('train counts:',int(tr12.sum()),int(tr120.sum()),int(tr15.sum()),flush=True)
    roll,manifest_roll=fit(d,tr120,F12,'F14_12_rolling120')
    exp,manifest_exp=fit(d,tr12,F12,'F14_12_expanding')
    old,manifest_old=fit(d,tr15,F15,'original15_expanding_REFERENCE')
    valid=(d.signal_group>=CUT)&(d.signal_group<=LAST)&reason_ok&finite12
    z=d.loc[valid,KEY+['signal_at','mature_at','reason','y']+F15].copy().reset_index(drop=True)
    print('simulation eligible:',len(z),flush=True)
    z['p_rolling12']=roll.predict_proba(z[F12].astype('float32'))[:,1]
    z['p_expanding12']=exp.predict_proba(z[F12].astype('float32'))[:,1]
    z['p_train_prevalence']=manifest_exp['train_prevalence']
    valid15=np.isfinite(z[F15].to_numpy(dtype='float64')).all(axis=1)
    z['p_original15']=np.nan
    z.loc[valid15,'p_original15']=old.predict_proba(z.loc[valid15,F15].astype('float32'))[:,1]
    z['maturity_state']='PENDING_OR_ENDPOINT_UNKNOWN'
    mature=z.mature_at.notna()&(z.mature_at<=LAST)&z.y.notna()
    missing=z.mature_at.notna()&(z.mature_at<=LAST)&z.y.isna()
    z.loc[mature,'maturity_state']='MATURED'
    z.loc[missing,'maturity_state']='CENSORED_MISSING_Y'
    z['model_freeze_before']='2026-07-01'
    z['signal_clock_assumption']='AFTER_EOD_UNVERIFIED'
    z['prediction_origin']='RECONSTRUCTED_2026_10_23_NOT_HISTORICALLY_RECORDED'
    z['dataset_role']='DEVELOPMENT_RETROSPECTIVE_SIMULATION'
    z['label_end_date']=z.mature_at
    z['publication_allowed']=False
    z.drop(columns=F15,inplace=True)
    z.sort_values(['signal_group','market','symbol'],inplace=True)
    z.to_csv(out/'simulated_prediction_ledger.csv.gz',index=False,compression='gzip')
    # Separate inferred issuance from labels: an as-of forecast must not carry
    # future outcomes, even in a retrospective replay.
    issue_cols=KEY+['signal_at','p_train_prevalence','p_rolling12','p_expanding12',
                    'p_original15','model_freeze_before','signal_clock_assumption',
                    'prediction_origin','dataset_role','publication_allowed']
    z[issue_cols].to_csv(out/'simulated_issued_only.csv.gz',index=False,compression='gzip')
    z[KEY+['label_end_date','y','maturity_state']].to_csv(
       out/'maturity_recovery_ledger.csv.gz',index=False,compression='gzip')
    # Portable research-only model parameters, no pickle/unsafe loader.
    def export_linear(model,name,feats):
        sc=model.named_steps['standardscaler'];lr=model.named_steps['logisticregression']
        v={'model':name,'features':feats,'scaler_mean':sc.mean_.tolist(),
           'scaler_scale':sc.scale_.tolist(),'coefficients':lr.coef_.tolist(),
           'intercepts':lr.intercept_.tolist(),'classes':lr.classes_.tolist(),
           'research_only':True,'publication_allowed':False}
        target=out/('model_'+name+'.json');tojson(target,v)
        return sha(target)
    model_fingerprints={
        'rolling12':export_linear(roll,'rolling12',F12),
        'expanding12':export_linear(exp,'expanding12',F12),
        'original15_REFERENCE':export_linear(old,'original15_reference',F15)}
    matured=z.loc[z.maturity_state=='MATURED'].copy()
    common=matured.loc[matured.p_original15.notna()].copy()
    totals={'raw_after_july_rows':int(((d.signal_group>=CUT)&(d.signal_group<=LAST)).sum()),
      'eligible_12_rows':len(z),'eligible_15_rows':int(valid15.sum()),
      'matured_12_rows':len(matured),'matured_15_rows':len(common),
      'censored_missing_y':int((z.maturity_state=='CENSORED_MISSING_Y').sum()),
      'pending_rows':int((z.maturity_state=='PENDING_OR_ENDPOINT_UNKNOWN').sum()),
      'signal_dates':int(z.signal_group.nunique()),
      'matured_signal_dates':int(matured.signal_group.nunique()),
      'last_observed_session':str(LAST.date())}
    metrics={'native12':{col:score(matured,col) for col in ['p_train_prevalence','p_rolling12','p_expanding12']},
             'common15':{col:score(common,col) for col in ['p_train_prevalence','p_rolling12','p_expanding12','p_original15']},
             'monthly':{},'market':{}}
    for k,g in matured.groupby(matured.signal_group.dt.to_period('M').astype(str)):
        metrics['monthly'][k]={col:score(g,col) for col in ['p_train_prevalence','p_rolling12','p_expanding12']}
    for k,g in matured.groupby('market',observed=True):
        metrics['market'][str(k)]={col:score(g,col) for col in ['p_train_prevalence','p_rolling12','p_expanding12']}
    records=[]
    for dt,g in matured.groupby('signal_group',observed=True):
        row={'signal_date':str(dt.date()),'rows':int(len(g))}
        for col in ['p_train_prevalence','p_rolling12','p_expanding12']:
            row[col+'_brier']=brier(g,col)
            row[col+'_auc']=auc(g,col)
        records.append(row)
    pd.DataFrame(records).to_csv(out/'metrics_by_signal_date.csv',index=False)
    # Cumulative as-of snapshot replays collection and recovery, not re-fitting.
    snapshots=[]
    dates=sorted(z.signal_group.unique())
    for dt in dates:
        issued=z.loc[z.signal_group<=dt]
        recovered=issued.loc[(issued.maturity_state=='MATURED')&(issued.mature_at<=dt)]
        baseline=date_brier(recovered,'p_train_prevalence')
        rr=date_brier(recovered,'p_rolling12');ex=date_brier(recovered,'p_expanding12')
        snapshots.append({'asof_session_eod':str(dt.date()),
         'issued_today':int((z.signal_group==dt).sum()),'cumulative_issued':int(len(issued)),
         'matured_new_today':int(((z.maturity_state=='MATURED')&(z.mature_at==dt)).sum()),
         'cumulative_matured':int(len(recovered)),
         'cumulative_pending_or_censored':int(len(issued)-len(recovered)),
         'matured_signal_dates':int(recovered.signal_group.nunique()),
         'cumulative_brier_date_equal_prevalence':baseline,
         'cumulative_brier_date_equal_rolling12':rr,
         'cumulative_brier_date_equal_expanding12':ex})
    pd.DataFrame(snapshots).to_csv(out/'cumulative_asof_eod.csv',index=False)
    cis={str(block):paired_ci(matured,'p_expanding12','p_rolling12',block) for block in (10,20,30)}
    tojson(out/'paired_block_ci.json',cis)
    tojson(out/'metrics.json',{'scope':'ONLY_MATURED_BY_DATASET_END','totals':totals,'metrics':metrics})
    tojson(out/'training_models.json',{'rolling12':manifest_roll,'expanding12':manifest_exp,
                                    'original15_REFERENCE':manifest_old})
    config={'status':'RESEARCH_CANDIDATE','publication_allowed':False,
      'model_decision':'TWO_PRESET_12FACTOR_CANDIDATES_NO_NEW_SELECTION',
      'lock_timestamp_cutoff_exclusive':str(CUT.date()),
      'simulation_start':str(CUT.date()),'dataset_end':str(LAST.date()),
      'not_real_forward':'predictions were reconstructed retrospectively on 2026-10-23',
      'development_only':'2026/07 and 2026/08 were previously examined in Stage06',
      'selected_pre_replay':'12F Logistic C=1; rolling120 vs expanding; 15F expanding original reference',
      'train_constraint':'only labels with mature_at<2026-07-01 used in fit; all models frozen for 63 sessions',
      'eval_constraint':'outcomes recovered by label_end_date<=each asof EOD, no future Y injection',
      'time_basis':'observed market-session union, NOT official validated TWSE/TPEx calendar',
      'label':'forward_up20 on unadjusted price, historical PIT/adjustments not verified',
      'prediction_asof':'signal_at date proxied as after market close; no actual 2026 daily issuance receipts',
      'data_file_sha256':EXPECT,'features_12':F12,'features_15':F15,
      'source_git_main_at_initial_audit':'351d28e16b45ec345c191e18283af867980c5be6',
      'source_training_code_git_sha':'28fd738d509ab9936bf997b7024430372ac9ceac',
      'stage05_1_candidate':'candidate-21588985ff46345d',
      'research_model_artifact_shas':model_fingerprints,
      'seed':SEED,'packages':{'python':platform.python_version(),
        'numpy':np.__version__,'pandas':pd.__version__,
        'sklearn':__import__('sklearn').__version__},
      'feature_and_label_canonical_source':'Drive Stage05.1 frozen X.parquet/Y_NOT_X.parquet; local fallback only after SHA',
      'unknown':['true historical published_at','price adjusted corporate actions','PIT universe','provenance ML license per row',
                 'actual future live predictions','2026-09 future matured Y beyond dataset end']}
    tojson(out/'simulation_manifest.json',config)
    sd=metrics['native12']
    fmt=lambda q:'NA' if q is None else f'{q:.6f}'
    rows=[f'# Janus Quant｜2026/07–09 模擬前瞻回收報告',
      '', '**RESEARCH_CANDIDATE；publication_allowed=false；非真實前瞻紀錄。**',
      '', '本研究於 2026-10-23 以已存在的 2026/07–09 歷史 X/Y **事後重建**逐交易日預測，',
      '僅用 2026-07-01 以前**已成熟**的標籤訓練三個凍結的 Logistic 版本，',
      '而不是 2026/07 當時真的發過且永久保存的預測。7–8 月早已被研究者檢視，所以此結果全屬 **development／retrospective simulation**。',
      '', '## 固定契約與資料',
      '', f'- 原始 X/Y SHA256：`{EXPECT["X"]}` / `{EXPECT["Y"]}`。',
      f'- 研究起點：2026-07-01；資料截止：2026-09-30；{totals["signal_dates"]} 訊號日期；模型自始至終不重訓。',
      f'- 原始 7–9 月 {totals["raw_after_july_rows"]:,} 列；12 因子可出具模擬預測 {totals["eligible_12_rows"]:,} 列；可成熟回收 {totals["matured_12_rows"]:,} 列；PENDING {totals["pending_rows"]:,}；CENSORED {totals["censored_missing_y"]:,}。',
      '- 凍結兩候選：同一個 F14 **12 因子**、相同 C=1 Logistic/Scaler；僅比較最近120成熟訊號日訓練 vs 全歷史成熟訓練。另有 15 因子歷史參照，分 common15 相同樣本比較。',
      '- 截止日之前已成熟標籤才進 fit（成熟日期嚴格小於 2026-07-01）；未來資料只在實際日期成熟後回收。',
      '', '## 7–8 月成熟樣本日期等權 Brier', '',
      '| 模型 | 成熟筆數 | 訊號日期數 | 日期等權 Brier | pooled AUC |',
      '|---|---:|---:|---:|---:|']
    for col,label in [('p_train_prevalence','固定訓練正例率'),('p_rolling12','12F 最近120日'),('p_expanding12','12F 全歷史')]:
        q=sd[col]
        rows.append(f'| {label} | {q["rows"]:,} | {q["signal_dates"]} | {fmt(q["brier_date_equal"])} | {fmt(q.get("auc_pooled"))} |')
    rows += ['', '## 訓練樣本比較', '', '| 版本 | 訓練筆數 | 訓練日期數 | 最晚已成熟標籤日 |', '|---|---:|---:|---|']
    for q in [manifest_roll,manifest_exp,manifest_old]:
        rows.append(f'| {q["model"]} | {q["train_rows"]:,} | {q["train_dates"]} | {q["latest_training_label_mature_at"]} |')
    rows += ['', '## 連續日期 paired block CI（全日截面保留）', '', '| Block | improvement: expanding − rolling | 95% CI | 狀態 |', '|---|---:|---|---|']
    for block,c in cis.items():
        v=c['ci95'];ci='INSUFFICIENT' if v is None else f'[{v[0]:.6f}, {v[1]:.6f}]'
        rows.append(f'| {block} | {fmt(c["mean_gain_second_vs_first"])} | {ci} | {c["status"]} |')
    rows += ['', '## 重要限制與後續', '',
      '- **不得宣稱 untouched OOS 或真實前瞻**：模型雖嚴格只看 7/1 前標籤，因這些資料、候選因子與研究方法早已被檢視，仍屬研究回放。',
      '- 研究資料是未調整股價與已觀測市場日期聯集，不具正式分市場日曆、PIT/公司行動完整證據。',
      '- 未取得截至 2026-09-30 之後的成熟行情，不得替 2026/09 模擬發出的預測創造 Y；所有 PENDING 留待真實資料逐日回收。',
      '- 不以該短期CI、單月或單一Brier最佳值做 production promotion。真正前瞻應在發出當時將 as_of、X/模型 SHA、模型機率 append-only 保存，再在20交易日後獨立收標籤。',
      '- `simulated_issued_only.csv.gz` 為不含 Y/label_end_date 的模擬發出紀錄；`maturity_recovery_ledger.csv.gz` 為獨立回收紀錄；`simulated_prediction_ledger.csv.gz` 僅為事後配對分析便利。',
      '- `model_*.json` 保留固定Scaler和Logistic係數、模型SHA；`cumulative_asof_eod.csv` 為每天預測新增與到期回收進度。',
      '', '未改動原始 Parquet、canonical、Risk ACTIVE、Registry 或任何部署。']
    (out/'研究報告.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    files=sorted(p for p in out.iterdir() if p.is_file())
    tojson(out/'artifact_checksums.json', {p.name:sha(p) for p in files})
    print('totals',totals,flush=True)
    print('native metrics',metrics['native12'],flush=True)
    print('report',out/'研究報告.md')

if __name__=='__main__':main()
