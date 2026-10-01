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
import eventize_run_v2
import matched_feature_run as legacy
import outcome_run
import validation_run

FEATURES = validation_run.FEATURES
HIGHER_SIGNAL = validation_run.HIGHER_SIGNAL
MIN_FEATURES = validation_run.MIN_FEATURES
PRIMARY_HORIZON = 60
SEED_FRACTION = 0.10
PRIMARY_GAP = 7
CONTAMINATION_GAP_TD = 10
VALIDATION_START = 2021


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _read_independent_cohort(client: Any, bucket: str, prefix: str, cohort_run_id: str) -> pd.DataFrame:
    obj = f'{prefix}/revisions/{cohort_run_id}/cohort/cohort_manifest.csv'
    raw = client.bucket(bucket).blob(obj).download_as_bytes()
    q = pd.read_csv(io.BytesIO(raw), dtype=str).fillna('')
    need = {'stock_id','effective_start','effective_end_exclusive','coverage','qualified','selected'}
    miss = sorted(need - set(q.columns))
    if miss:
        raise RuntimeError(f'cohort manifest schema missing: {miss}')
    qualified = q[q['qualified'].map(outcome_run.truthy)].copy()
    selected = qualified[qualified['selected'].map(outcome_run.truthy)].copy()
    holdout = qualified[~qualified['selected'].map(outcome_run.truthy)].copy()
    if len(selected) != 500:
        raise RuntimeError(f'expected original selected cohort 500, got {len(selected)}')
    if len(holdout) < 400:
        raise RuntimeError(f'independent qualified holdout too small: {len(holdout)}')
    if set(selected['stock_id']) & set(holdout['stock_id']):
        raise RuntimeError('selected and independent holdout overlap')
    if (pd.to_numeric(holdout['coverage'], errors='coerce') < 0.90).any():
        raise RuntimeError('independent holdout contains coverage below 0.90')
    return holdout.sort_values('stock_id').reset_index(drop=True)


def _compact_feature_row(vw: dict[str, Any], t: date) -> list[float | None]:
    f = validation_run._feature8(vw, t)
    return [f.get(name) for name in FEATURES]


def _score_frame(frame: pd.DataFrame) -> pd.DataFrame:
    orient = []
    for f in FEATURES:
        r = frame.groupby('t', sort=False)[f].rank(pct=True, method='average')
        orient.append(r if f in HIGHER_SIGNAL else (1.0 - r))
    score_mat = pd.concat(orient, axis=1)
    score_mat.columns = [f's__{f}' for f in FEATURES]
    frame = frame.copy()
    frame['available_features'] = score_mat.notna().sum(axis=1)
    frame['score'] = score_mat.mean(axis=1, skipna=True)
    frame.loc[frame['available_features'] < MIN_FEATURES, 'score'] = np.nan
    return frame


def _event_keys_and_seed_positions(valid: pd.DataFrame, calendar: list[date]) -> tuple[set[tuple[str,date]], dict[str,np.ndarray], dict[str,Any]]:
    seed_input = valid[['stock_id','t','mfe']].copy()
    seed_input['horizon'] = PRIMARY_HORIZON
    seed_input['status'] = 'valid'
    ranked = eventize_run_v2.rank_seed_frame(seed_input, PRIMARY_HORIZON, SEED_FRACTION)
    calendar_pos = {d:i for i,d in enumerate(calendar)}
    events: list[dict[str,Any]] = []
    seed_pos: dict[str,np.ndarray] = {}
    for sid, g in ranked[ranked['is_seed']].groupby('stock_id', sort=True):
        g = g.sort_values('t', kind='mergesort')
        comps = eventize_run_v2.eventize_symbol_seeds(g, calendar_pos, PRIMARY_GAP)
        pos_all = []
        for comp in comps:
            x = g.loc[comp].sort_values('t', kind='mergesort')
            events.append({'stock_id':str(sid),'anchor_t':x.iloc[0]['t'],'seed_count':len(x)})
            pos_all.extend(calendar_pos[t] for t in x['t'].tolist())
        seed_pos[str(sid)] = np.asarray(sorted(set(pos_all)), dtype=np.int32)
    event_keys = {(e['stock_id'], e['anchor_t']) for e in events}
    audit = {
        'valid_h60_observation_count': int(len(valid)),
        'seed_count': int(ranked['is_seed'].sum()),
        'event_count': int(len(events)),
        'symbols_with_events': int(len({e['stock_id'] for e in events})),
        'seed_fraction': SEED_FRACTION,
        'gap_trading_days': PRIMARY_GAP,
    }
    return event_keys, seed_pos, audit


def _contaminated(sid: str, t: date, seed_pos: dict[str,np.ndarray], cal_pos: dict[date,int]) -> bool:
    p = cal_pos.get(t)
    if p is None:
        return True
    sp = seed_pos.get(sid)
    if sp is None or len(sp) == 0:
        return False
    j = int(np.searchsorted(sp, p))
    dist = []
    if j > 0:
        dist.append(abs(p - int(sp[j-1])))
    if j < len(sp):
        dist.append(abs(p - int(sp[j])))
    return bool(dist and min(dist) <= CONTAMINATION_GAP_TD)


def run(request: dict[str,Any], bucket: str, prefix: str, run_id: str) -> dict[str,Any]:
    source_obj = str(request.get('source_gcs_object','')).strip()
    expected_sha = str(request.get('source_sha256','')).strip().lower()
    expected_size = int(request.get('source_size_bytes',0))
    materialized_revision = str(request.get('materialized_revision','20260917T025906Z'))
    cohort_run_id = str(request.get('cohort_run_id','')).strip()
    research_start = cohort_build.d(request.get('research_start')) or date(2015,1,1)
    research_end = cohort_build.d(request.get('research_end')) or date(2026,9,16)
    if not cohort_run_id or not source_obj or len(expected_sha) != 64 or expected_size <= 0:
        raise RuntimeError('independent validation immutable input identity missing')

    from google.cloud import storage
    client = storage.Client()
    buck = client.bucket(bucket)
    holdout = _read_independent_cohort(client, bucket, prefix, cohort_run_id)
    root = f'{prefix}/revisions/{run_id}/independent_validation'
    base = f'janus_step2a_materialized/{materialized_revision}/'

    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        source_path = td/'source.zip'
        buck.blob(source_obj).download_to_filename(source_path)
        if source_path.stat().st_size != expected_size or _sha256(source_path) != expected_sha:
            raise RuntimeError('staged source identity mismatch')

        rows: list[dict[str,Any]] = []
        with zipfile.ZipFile(source_path) as z:
            calendar, calendar_meta = cohort_build.calendar(z, base, research_start, research_end)
            weekly = outcome_run.weekly_first_trading_days(calendar)
            marketwide_par_value = outcome_run.load_marketwide_par_value_dates(z, base)
            for idx, r in holdout.iterrows():
                sid = str(r['stock_id'])
                s = cohort_build.d(r['effective_start'])
                e = cohort_build.d(r['effective_end_exclusive'])
                if s is None:
                    raise RuntimeError(f'independent symbol missing effective_start: {sid}')
                q = outcome_run.load_price(z, base, sid)
                actions = outcome_run.load_action_dates(z, base, sid, marketwide_par_value)
                obs, _, _ = outcome_run._obs_for_symbol(sid, s, e, q, actions, weekly, calendar, research_end)
                vw = legacy._view(q)
                for rec in obs:
                    if int(rec['horizon']) != PRIMARY_HORIZON or rec['status'] != 'valid':
                        continue
                    t = cohort_build.d(rec['t'])
                    if t is None:
                        continue
                    fvals = _compact_feature_row(vw, t)
                    row = {'stock_id':sid,'t':t,'year':t.year,'mfe':float(rec['mfe'])}
                    row.update({name:value for name,value in zip(FEATURES,fvals)})
                    rows.append(row)
                if (idx + 1) % 25 == 0:
                    print(f'[independent {idx+1}/{len(holdout)}] {sid} rows={len(rows)}', flush=True)

        frame = pd.DataFrame(rows)
        if frame.empty:
            raise RuntimeError('no valid H60 independent observations')
        event_keys, seed_pos, event_audit = _event_keys_and_seed_positions(frame[['stock_id','t','mfe']], calendar)
        cal_pos = {d:i for i,d in enumerate(calendar)}
        frame['is_event'] = [(str(s),t) in event_keys for s,t in zip(frame['stock_id'],frame['t'])]
        frame['contaminated'] = [
            _contaminated(str(s), t, seed_pos, cal_pos)
            for s,t in zip(frame['stock_id'], frame['t'])
        ]
        frame = _score_frame(frame)
        eligible = frame[frame['score'].notna() & (frame['is_event'] | ~frame['contaminated'])].copy()
        if int(eligible['is_event'].sum()) == 0:
            raise RuntimeError('no independent event anchors survived score gate')

        all_metrics = validation_run._metrics(eligible)
        primary = eligible[eligible['year'] >= VALIDATION_START].copy()
        if primary.empty or int(primary['is_event'].sum()) == 0:
            raise RuntimeError('no 2021-2026 independent validation events')
        primary_metrics = validation_run._metrics(primary)
        year_rows = []
        for yr, q in primary.groupby('year'):
            year_rows.append({'year':int(yr), **validation_run._metrics(q)})
        years_lift = sum(1 for r in year_rows if r.get('top10_lift') is not None and r['top10_lift'] > 1.0)
        validation_years = len(year_rows)

        dec = primary.copy()
        dec['score_decile'] = np.minimum(9, np.floor(dec['score']*10).astype(int)) + 1
        dec_rows = dec.groupby('score_decile',as_index=False).agg(n=('is_event','size'),events=('is_event','sum'))
        dec_rows['event_rate'] = dec_rows['events']/dec_rows['n']

        acceptance = {
            'independent_universe_size_ge_400': bool(len(holdout) >= 400),
            'primary_top10_lift_gt_1': bool(primary_metrics.get('top10_lift') is not None and primary_metrics['top10_lift'] > 1.0),
            'primary_majority_years_top10_lift_gt_1': bool(validation_years > 0 and years_lift >= math.ceil(validation_years/2)),
            'primary_decile_monotonic_positive': bool(primary_metrics.get('decile_event_rate_spearman') is not None and primary_metrics['decile_event_rate_spearman'] > 0),
        }
        acceptance['pass'] = all(acceptance.values())

        summary = {
            'schema_version':'janus.research.big-move.independent-universe-validation.v1',
            'status':'ok','action':'validate_independent_universe','run_id':run_id,'generated_at':now(),
            'design':{
                'holdout_rule':'cohort_manifest qualified=true and selected=false; zero stock overlap with original selected 500',
                'holdout_selection_caveat':'not random; original cohort selected qualified symbols by ascending numeric stock_id',
                'frozen_features':FEATURES,
                'feature_orientation':{'higher_signal':sorted(HIGHER_SIGNAL),'lower_signal':sorted(set(FEATURES)-set(HIGHER_SIGNAL))},
                'score':'same-T cross-sectional percentile ranks within independent universe; equal-weight mean; require >=6/8 available',
                'positive_label':'independent-universe H60 exact top-decile seeds, G7 wave anchor',
                'negative_guard':f'exclude same-stock observations within +/-{CONTAMINATION_GAP_TD} trading days of any independent seed',
                'primary_period':'2021-2026',
                'information_cutoff':'T close or earlier only',
                'interpretation':'independent-stock temporal replication; still not prospective because methodology was defined after inspecting original 500-stock history',
            },
            'independent_universe':{
                'qualified_nonselected_symbols':int(len(holdout)),
                'coverage_min':float(pd.to_numeric(holdout['coverage'],errors='coerce').min()),
                'selected_overlap_count':0,
            },
            'eventization':event_audit,
            'all_period_metrics':all_metrics,
            'primary_2021_2026':primary_metrics,
            'primary_year_count':int(validation_years),
            'primary_years_top10_lift_gt_1':int(years_lift),
            'acceptance':acceptance,
            'calendar':calendar_meta,
            'isolation':{'postgresql_used':False,'database_used':False,'existing_janus_iceberg_catalog_used':False,'janus_core_written':False,'janus_mart_written':False,'janus_private_mart_written':False,'runtime_secret_used':False},
            'next_gate':'if pass, freeze research signal contract and begin prospective shadow validation; do not promote to canonical production signal yet',
        }
        outputs = {
            f'{root}/summary.json':(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode(),
            f'{root}/score_deciles_2021_2026.csv':dec_rows.to_csv(index=False).encode('utf-8-sig'),
            f'{root}/validation_by_year.csv':pd.DataFrame(year_rows).to_csv(index=False).encode('utf-8-sig'),
            f'{root}/holdout_symbols.csv':holdout[['stock_id','coverage','effective_start','effective_end_exclusive']].to_csv(index=False).encode('utf-8-sig'),
        }
        for obj, body in outputs.items():
            buck.blob(obj).upload_from_string(body,content_type='application/json' if obj.endswith('.json') else 'text/csv')
        return summary


def self_test() -> None:
    q = pd.DataFrame({
        't':[date(2026,1,2)]*10,
        'score':[0.05,0.15,0.25,0.35,0.45,0.55,0.65,0.75,0.85,0.95],
        'is_event':[False]*9+[True],
    })
    m = validation_run._metrics(q)
    assert m['top10_lift'] is not None and m['top10_lift'] > 1.0
