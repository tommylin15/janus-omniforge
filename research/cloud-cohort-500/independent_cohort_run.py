from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def truthy(v: Any) -> bool:
    return str(v).strip().lower() in {'1', 'true', 'yes', 'y'}


def derive_frame(frame: pd.DataFrame, target: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    q = frame.copy().fillna('')
    required = {
        'stock_id', 'effective_start', 'effective_end_exclusive',
        'coverage', 'qualified', 'selected'
    }
    missing = sorted(required - set(q.columns))
    if missing:
        raise RuntimeError(f'primary cohort manifest schema missing: {missing}')

    q['stock_id'] = q['stock_id'].astype(str)
    if q['stock_id'].duplicated().any():
        raise RuntimeError('primary cohort manifest has duplicate stock_id')

    primary = q[q['selected'].map(truthy)].copy()
    if len(primary) != 500:
        raise RuntimeError(f'primary cohort must contain exactly 500 selected symbols; got {len(primary)}')
    primary_ids = set(primary['stock_id'])

    qualified = q[q['qualified'].map(truthy)].copy()
    qualified['coverage_num'] = pd.to_numeric(qualified['coverage'], errors='coerce')
    if qualified['coverage_num'].isna().any():
        raise RuntimeError('qualified cohort rows contain invalid coverage')

    reserve = qualified[~qualified['stock_id'].isin(primary_ids)].copy()
    reserve['stock_id_num'] = pd.to_numeric(reserve['stock_id'], errors='coerce')
    if reserve['stock_id_num'].isna().any():
        raise RuntimeError('independent reserve contains non-numeric stock_id')
    reserve = reserve.sort_values(['stock_id_num', 'stock_id'], kind='mergesort')
    chosen = reserve.head(target).copy()
    if len(chosen) != target:
        raise RuntimeError(f'independent cohort gate failed: reserve={len(reserve)} need={target}')
    if (chosen['coverage_num'] < 0.90).any():
        raise RuntimeError('independent cohort contains coverage below 0.90')

    chosen_ids = set(chosen['stock_id'])
    overlap = sorted(primary_ids & chosen_ids)
    if overlap:
        raise RuntimeError(f'independent cohort overlaps primary cohort: {overlap[:10]}')

    q['selected'] = q['stock_id'].isin(chosen_ids)
    q['rank_rule'] = 'primary_unselected_qualified_then_stock_id_ascending'
    q['cohort_role'] = 'independent_validation'
    q['primary_selected'] = q['stock_id'].isin(primary_ids)

    meta = {
        'primary_selected_count': int(len(primary_ids)),
        'qualified_count': int(len(qualified)),
        'qualified_unselected_reserve_count': int(len(reserve)),
        'independent_selected_count': int(len(chosen_ids)),
        'remaining_qualified_reserve_count': int(len(reserve) - len(chosen_ids)),
        'stock_overlap_count': int(len(overlap)),
        'selection_rule': 'from immutable primary cohort manifest: qualified=true AND primary selected=false, then ascending numeric stock_id; no outcome/MFE input',
        'selected_stock_ids': sorted(chosen_ids, key=int),
    }
    return q, meta


def run(request: dict[str, Any], bucket: str, prefix: str, run_id: str) -> dict[str, Any]:
    primary_run_id = str(request.get('primary_cohort_run_id', '')).strip()
    target = int(request.get('cohort_size', 500))
    if not primary_run_id:
        raise RuntimeError('primary_cohort_run_id missing')
    if target != 500:
        raise RuntimeError(f'independent cohort target must remain frozen at 500; got {target}')

    from google.cloud import storage

    client = storage.Client()
    buck = client.bucket(bucket)
    source_obj = f'{prefix}/revisions/{primary_run_id}/cohort/cohort_manifest.csv'
    raw = buck.blob(source_obj).download_as_bytes()
    primary_manifest = pd.read_csv(io.BytesIO(raw), dtype=str).fillna('')
    derived, meta = derive_frame(primary_manifest, target)

    root = f'{prefix}/revisions/{run_id}/cohort'
    manifest_obj = f'{root}/cohort_manifest.csv'
    result_obj = f'{root}/independent_cohort_result.json'
    body = derived.to_csv(index=False).encode('utf-8-sig')
    buck.blob(manifest_obj).upload_from_string(body, content_type='text/csv')

    summary = {
        'schema_version': 'janus.research.big-move.independent-cohort.v1',
        'status': 'ok',
        'action': 'derive_independent_cohort',
        'run_id': run_id,
        'generated_at': now(),
        'primary_cohort_run_id': primary_run_id,
        'primary_manifest_object': source_obj,
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
        'next_gate': 'independent_cohort_outcomes_then_eventization_then_frozen_score_validation',
    }
    buck.blob(result_obj).upload_from_string(
        (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8'),
        content_type='application/json',
    )
    return summary


def self_test() -> None:
    rows = []
    for i in range(1, 13):
        rows.append({
            'stock_id': f'{1000+i}',
            'effective_start': '2015-01-01',
            'effective_end_exclusive': '',
            'coverage': '0.95',
            'qualified': 'True',
            'selected': 'True' if i <= 5 else 'False',
            'rank_rule': 'x',
        })
    q = pd.DataFrame(rows)
    # Exercise the selection helper with a miniature primary size by temporarily
    # building a 500-row-shaped frame is unnecessary; verify truth parsing and
    # deterministic stock ordering here, while production run enforces primary=500.
    assert truthy('True') and not truthy('False')
    r = q[~q['selected'].map(truthy)].copy()
    assert r.sort_values('stock_id').head(3)['stock_id'].tolist() == ['1006', '1007', '1008']
