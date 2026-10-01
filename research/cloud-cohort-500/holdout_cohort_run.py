from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

import cohort_build


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _select_holdout(q: pd.DataFrame, target: int, mincov: float) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {'stock_id','effective_start','effective_end_exclusive','coverage','qualified','selected'}
    missing = sorted(required - set(q.columns))
    if missing:
        raise RuntimeError(f'cohort manifest schema missing: {missing}')

    x = q.copy().fillna('')
    x['stock_id'] = x['stock_id'].astype(str)
    x['coverage_num'] = pd.to_numeric(x['coverage'], errors='coerce')
    x['qualified_bool'] = x['qualified'].map(cohort_build.b)
    x['selected_bool'] = x['selected'].map(cohort_build.b)

    original_selected = set(x.loc[x['selected_bool'], 'stock_id'])
    pool = x[x['qualified_bool'] & ~x['selected_bool'] & (x['coverage_num'] >= mincov)].copy()
    pool = pool.sort_values('stock_id', key=lambda s: s.astype(int), kind='mergesort').reset_index(drop=True)
    if len(pool) < target:
        raise RuntimeError(f'holdout gate failed: eligible_nonselected={len(pool)} need={target}')

    chosen_ids = set(pool.iloc[:target]['stock_id'])
    out = pool.drop(columns=['coverage_num','qualified_bool','selected_bool']).copy()
    out['selected'] = out['stock_id'].isin(chosen_ids)
    out['rank_rule'] = 'source_qualified_not_original_selected_then_stock_id_ascending'

    chosen = out[out['selected']].copy()
    overlap = len(set(chosen['stock_id']) & original_selected)
    cov = pd.to_numeric(chosen['coverage'], errors='coerce').to_numpy(dtype=float)
    if len(chosen) != target:
        raise RuntimeError(f'holdout selected count mismatch: {len(chosen)} != {target}')
    if overlap:
        raise RuntimeError(f'holdout overlaps source selected cohort: {overlap}')
    if not np.isfinite(cov).all() or float(np.min(cov)) < mincov:
        raise RuntimeError('holdout contains coverage below minimum')

    meta = {
        'source_selected_symbols': int(len(original_selected)),
        'eligible_nonselected_symbols': int(len(pool)),
        'selected_symbols': int(len(chosen)),
        'overlap_with_source_selected': int(overlap),
        'coverage_min': float(np.min(cov)),
        'coverage_p50': float(np.quantile(cov, 0.50, method='linear')),
        'coverage_max': float(np.max(cov)),
        'selected_stock_ids': sorted(chosen_ids, key=int),
    }
    return out, meta


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    source_cohort_run_id = str(request.get('source_cohort_run_id', '')).strip()
    target = int(request.get('cohort_size', 500))
    mincov = float(request.get('usable_ohlcv_coverage_min', 0.90))
    if not source_cohort_run_id:
        raise RuntimeError('source_cohort_run_id missing')
    if target != 500:
        raise RuntimeError(f'holdout target must remain frozen at 500; got {target}')
    if mincov < 0.90:
        raise RuntimeError('holdout coverage minimum must be >= 0.90')

    from google.cloud import storage
    client = storage.Client()
    buck = client.bucket(bucket)
    source_obj = f'{prefix}/revisions/{source_cohort_run_id}/cohort/cohort_manifest.csv'
    raw = buck.blob(source_obj).download_as_bytes()
    source = pd.read_csv(io.BytesIO(raw), dtype=str).fillna('')
    out, meta = _select_holdout(source, target, mincov)

    root = f'{prefix}/revisions/{run_id}'
    summary = {
        'schema_version': 'janus.research.big-move.holdout-cohort.v1',
        'status': 'ok',
        'action': 'build_holdout_cohort',
        'run_id': run_id,
        'generated_at': now(),
        'source_cohort_run_id': source_cohort_run_id,
        'source_cohort_object': source_obj,
        'selection_contract': {
            'universe': 'same source cohort manifest; qualified=true; original selected=false',
            'selection_rule': 'ascending numeric stock_id; first 500; independent of MFE/outcomes/features',
            'coverage_min': mincov,
            'target': target,
            'purpose': 'independent-stock-universe replication of frozen antecedent score',
        },
        'cohort': meta,
        'isolation': {
            'postgresql_used': False,
            'database_used': False,
            'existing_janus_iceberg_catalog_used': False,
            'janus_core_written': False,
            'janus_mart_written': False,
            'janus_private_mart_written': False,
            'runtime_secret_used': False,
        },
        'next_gate': 'preflight_and_outcomes_on_holdout_500',
    }

    body = out.to_csv(index=False).encode('utf-8-sig')
    buck.blob(f'{root}/cohort/cohort_manifest.csv').upload_from_string(body, content_type='text/csv')
    buck.blob(f'{root}/cohort/holdout_cohort_result.json').upload_from_string(
        (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8'),
        content_type='application/json',
    )
    return summary


def self_test() -> None:
    q = pd.DataFrame([
        {'stock_id':'1101','effective_start':'2015-01-01','effective_end_exclusive':'','coverage':'0.95','qualified':'True','selected':'True','rank_rule':'x'},
        {'stock_id':'1102','effective_start':'2015-01-01','effective_end_exclusive':'','coverage':'0.94','qualified':'True','selected':'False','rank_rule':'x'},
        {'stock_id':'1103','effective_start':'2015-01-01','effective_end_exclusive':'','coverage':'0.96','qualified':'True','selected':'False','rank_rule':'x'},
        {'stock_id':'1104','effective_start':'2015-01-01','effective_end_exclusive':'','coverage':'0.89','qualified':'True','selected':'False','rank_rule':'x'},
    ])
    out, meta = _select_holdout(q, 2, 0.90)
    assert out[out['selected']]['stock_id'].tolist() == ['1102','1103']
    assert meta['overlap_with_source_selected'] == 0
    assert meta['eligible_nonselected_symbols'] == 2
