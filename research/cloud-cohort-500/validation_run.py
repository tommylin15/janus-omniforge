from __future__ import annotations

import hashlib
import io
import json
import math
import tempfile
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import cohort_build
import matched_feature_run as legacy

FEATURES = [
    'range_mean_20','vol_60','vol_20','close_to_high_20',
    'ret_5','max_drawdown_20','close_to_high_60','max_drawdown_60'
]
HIGHER_SIGNAL = {'range_mean_20','vol_60','vol_20'}
LOWER_SIGNAL = set(FEATURES) - HIGHER_SIGNAL
MIN_FEATURES = 6
CONTAMINATION_GAP_TD = 10
DISCOVERY_END = 2020
VALIDATION_START = 2021


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _feature8(vw: dict[str, Any], t: date) -> dict[str, float | None]:
    p=vw['pos'].get(t)
    if p is None:
        return {f:None for f in FEATURES}
    h,c=vw['high'],vw['close']
    out: dict[str,float|None] = {}
    out['ret_5'] = float(c[p]/c[p-5]-1.0) if p>=5 and np.isfinite(c[p]) and np.isfinite(c[p-5]) and c[p]>0 and c[p-5]>0 else None
    for n in (20,60):
        if p>=n:
            cr=c[p-n:p+1]
            if np.all(np.isfinite(cr)) and np.all(cr>0):
                rr=cr[1:]/cr[:-1]-1.0
                out[f'vol_{n}']=float(np.std(rr,ddof=1)) if len(rr)>=2 else None
            else:
                out[f'vol_{n}']=None
        else:
            out[f'vol_{n}']=None
        if p+1>=n:
            sl=slice(p-n+1,p+1)
            cw,hw=c[sl],h[sl]
            out[f'close_to_high_{n}']=float(c[p]/np.max(hw)-1.0) if np.all(np.isfinite(hw)) and np.all(hw>0) and np.isfinite(c[p]) and c[p]>0 else None
            out[f'max_drawdown_{n}']=legacy._max_drawdown(cw)
            if n==20:
                low=vw['low'][sl]
                out['range_mean_20']=float(np.mean((hw-low)/cw)) if np.all(np.isfinite(hw)) and np.all(np.isfinite(low)) and np.all(np.isfinite(cw)) and np.all(cw>0) else None
        else:
            out[f'close_to_high_{n}']=None
            out[f'max_drawdown_{n}']=None
            if n==20:
                out['range_mean_20']=None
    return {f:out.get(f) for f in FEATURES}


def _metrics(q: pd.DataFrame) -> dict[str, Any]:
    n=len(q); events=int(q['is_event'].sum())
    baseline=events/n if n else None
    out={'eligible_count':int(n),'event_count':events,'baseline_event_rate':baseline}
    for name,thr in [('top10',0.90),('top20',0.80),('top30',0.70)]:
        g=q[q['score']>=thr]
        ge=int(g['is_event'].sum())
        rate=ge/len(g) if len(g) else None
        lift=(rate/baseline) if baseline and rate is not None else None
        capture=(ge/events) if events else None
        out[f'{name}_count']=int(len(g)); out[f'{name}_events']=ge; out[f'{name}_event_rate']=rate; out[f'{name}_lift']=lift; out[f'{name}_capture']=capture
    d=q.copy(); d['score_decile']=np.minimum(9,np.floor(d['score']*10).astype(int))+1
    tab=d.groupby('score_decile',as_index=False).agg(n=('is_event','size'),events=('is_event','sum'))
    tab['event_rate']=tab['events']/tab['n']
    if len(tab)>=3 and tab['event_rate'].nunique()>1:
        out['decile_event_rate_spearman']=float(tab['score_decile'].corr(tab['event_rate'],method='spearman'))
    else:
        out['decile_event_rate_spearman']=None
    return out


def run(request: dict[str,Any], bucket: str, prefix: str, run_id: str) -> dict[str,Any]:
    outcome_run_id=str(request.get('outcome_run_id','')).strip()
    event_run_id=str(request.get('event_run_id','')).strip()
    source_obj=str(request.get('source_gcs_object','')).strip()
    expected_sha=str(request.get('source_sha256','')).strip().lower()
    expected_size=int(request.get('source_size_bytes',0))
    materialized_revision=str(request.get('materialized_revision','20260917T025906Z'))
    if not outcome_run_id or not event_run_id or not source_obj or len(expected_sha)!=64 or expected_size<=0:
        raise RuntimeError('validation immutable input identity missing')

    from google.cloud import storage
    client=storage.Client(); buck=client.bucket(bucket)
    root=f'{prefix}/revisions/{run_id}/validation'
    outcome_obj=f'{prefix}/revisions/{outcome_run_id}/outcomes/observations.parquet'
    event_obj=f'{prefix}/revisions/{event_run_id}/events/event_manifest.csv'

    with tempfile.TemporaryDirectory() as td:
        td=Path(td); obs_path=td/'observations.parquet'; source_path=td/'source.zip'
        buck.blob(outcome_obj).download_to_filename(obs_path)
        buck.blob(source_obj).download_to_filename(source_path)
        if source_path.stat().st_size!=expected_size or _sha256(source_path)!=expected_sha:
            raise RuntimeError('staged source identity mismatch')
        obs=pd.read_parquet(obs_path,columns=['stock_id','t','horizon','status'])
        obs['horizon']=pd.to_numeric(obs['horizon'],errors='raise').astype(int)
        obs=obs[(obs['horizon']==60)&(obs['status']=='valid')][['stock_id','t']].copy()
        obs['stock_id']=obs['stock_id'].astype(str); obs['t']=pd.to_datetime(obs['t'],errors='raise').dt.date
        events=pd.read_csv(io.BytesIO(buck.blob(event_obj).download_as_bytes()),dtype={'stock_id':str})
        events['stock_id']=events['stock_id'].astype(str); events['anchor_t']=pd.to_datetime(events['anchor_t'],errors='raise').dt.date
        event_keys={(r.stock_id,r.anchor_t) for r in events.itertuples(index=False)}
        base=f'janus_step2a_materialized/{materialized_revision}/'
        with zipfile.ZipFile(source_path) as z:
            calendar,calendar_meta=cohort_build.calendar(z,base,obs['t'].min(),obs['t'].max())
            cal_pos={d:i for i,d in enumerate(calendar)}
            seed_pos: dict[str,list[int]]=defaultdict(list)
            for r in events.itertuples(index=False):
                for ts in str(r.seed_ts).split('|'):
                    d=cohort_build.d(ts)
                    if d in cal_pos: seed_pos[str(r.stock_id)].append(cal_pos[d])
            seed_pos={k:sorted(set(v)) for k,v in seed_pos.items()}

            cols={'stock_id':[],'t':[],'is_event':[],'contaminated':[]}
            for f in FEATURES: cols[f]=[]
            for sid,g in obs.groupby('stock_id',sort=True):
                sid=str(sid); vw=legacy._view(legacy._load_prices(z,base,sid)); sp=seed_pos.get(sid,[])
                sp_arr=np.asarray(sp,dtype=int) if sp else None
                for t in g['t'].tolist():
                    p=cal_pos.get(t); contaminated=False
                    if p is None: contaminated=True
                    elif sp_arr is not None and len(sp_arr):
                        j=np.searchsorted(sp_arr,p)
                        ds=[]
                        if j>0: ds.append(abs(p-int(sp_arr[j-1])))
                        if j<len(sp_arr): ds.append(abs(p-int(sp_arr[j])))
                        contaminated=bool(ds and min(ds)<=CONTAMINATION_GAP_TD)
                    ft=_feature8(vw,t)
                    cols['stock_id'].append(sid); cols['t'].append(t); cols['is_event'].append((sid,t) in event_keys); cols['contaminated'].append(contaminated)
                    for f in FEATURES: cols[f].append(ft[f])
        frame=pd.DataFrame(cols)
        orient=[]
        for f in FEATURES:
            r=frame.groupby('t')[f].rank(pct=True,method='average')
            orient.append(r if f in HIGHER_SIGNAL else (1.0-r))
        score_mat=pd.concat(orient,axis=1); score_mat.columns=[f's__{f}' for f in FEATURES]
        frame['available_features']=score_mat.notna().sum(axis=1)
        frame['score']=score_mat.mean(axis=1,skipna=True)
        frame.loc[frame['available_features']<MIN_FEATURES,'score']=np.nan
        frame['year']=pd.to_datetime(frame['t']).dt.year
        eligible=frame[frame['score'].notna() & (frame['is_event'] | ~frame['contaminated'])].copy()
        if eligible['is_event'].sum()==0: raise RuntimeError('no event anchors survived validation feature gate')
        discovery=eligible[eligible['year']<=DISCOVERY_END].copy()
        validation=eligible[eligible['year']>=VALIDATION_START].copy()
        disc_m=_metrics(discovery); val_m=_metrics(validation)
        dec_rows=[]
        for period,q in [('discovery_2015_2020',discovery),('validation_2021_2026',validation)]:
            q=q.copy(); q['score_decile']=np.minimum(9,np.floor(q['score']*10).astype(int))+1
            t=q.groupby('score_decile',as_index=False).agg(n=('is_event','size'),events=('is_event','sum'))
            t['event_rate']=t['events']/t['n']; t['period']=period; dec_rows.extend(t.to_dict('records'))
        year_rows=[]
        for yr,q in validation.groupby('year'):
            m=_metrics(q); year_rows.append({'year':int(yr),**m})
        years_lift=sum(1 for r in year_rows if r.get('top10_lift') is not None and r['top10_lift']>1.0)
        validation_years=len(year_rows)
        acceptance={
            'validation_top10_lift_gt_1': bool(val_m.get('top10_lift') is not None and val_m['top10_lift']>1.0),
            'validation_majority_years_top10_lift_gt_1': bool(validation_years>0 and years_lift>=math.ceil(validation_years/2)),
            'validation_decile_monotonic_positive': bool(val_m.get('decile_event_rate_spearman') is not None and val_m['decile_event_rate_spearman']>0),
        }
        acceptance['pass']=all(acceptance.values())
        summary={
            'schema_version':'janus.research.big-move.predictive-validation.v1',
            'status':'ok','action':'validate_antecedent_score','run_id':run_id,'generated_at':now(),
            'design':{
                'features':FEATURES,'feature_orientation':{'higher_signal':sorted(HIGHER_SIGNAL),'lower_signal':sorted(LOWER_SIGNAL)},
                'score':'same-T cross-sectional percentile ranks; equal-weight mean; require >=6/8 available',
                'positive_label':'primary G7 H60 top-decile wave anchor',
                'negative_guard':f'exclude same-stock observations within +/-{CONTAMINATION_GAP_TD} trading days of any primary seed',
                'discovery_period':'2015-2020','validation_period':'2021-2026',
                'information_cutoff':'T close or earlier only','interpretation':'post-hoc temporal replication, not pristine blind OOS because full-period exploratory results were previously inspected'
            },
            'discovery':disc_m,'validation':val_m,
            'validation_years_top10_lift_gt_1':int(years_lift),'validation_year_count':int(validation_years),
            'acceptance':acceptance,'calendar':calendar_meta,
            'isolation':{'postgresql_used':False,'database_used':False,'existing_janus_iceberg_catalog_used':False,'janus_core_written':False,'janus_mart_written':False,'janus_private_mart_written':False,'runtime_secret_used':False},
            'next_gate':'if pass, define prospective/independent-universe validation before any canonical signal threshold'
        }
        outputs={
            f'{root}/summary.json':(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode(),
            f'{root}/score_deciles.csv':pd.DataFrame(dec_rows).to_csv(index=False).encode('utf-8-sig'),
            f'{root}/validation_by_year.csv':pd.DataFrame(year_rows).to_csv(index=False).encode('utf-8-sig'),
        }
        for obj,body in outputs.items(): buck.blob(obj).upload_from_string(body,content_type='application/json' if obj.endswith('.json') else 'text/csv')
        return summary


def self_test() -> None:
    q=pd.DataFrame({'score':[.05,.15,.25,.35,.45,.55,.65,.75,.85,.95]*20,'is_event':[False]*180+[True]*20})
    m=_metrics(q)
    assert m['eligible_count']==200 and m['event_count']==20
    assert m['top10_lift'] is not None
