from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'jobs/intelligence-mart'))
from intelligence_mart.specialists import analyze_specialists, digest
from packages.analysis_product import baseline_projection, content_hash, freshness, validate_ceo_output


def product_inputs():
    rows = [{'symbol': '2330', 'source_id': 'twse', 'provenance_id': f'p{i}',
             'trade_date': str(date(2026, 4, 1) + timedelta(days=i)),
             'observed_at': str(date(2026, 4, 1) + timedelta(days=i)), 'close': 100+i, 'volume_shares': 100000, 'turnover_twd': 10000000}
            for i in range(30)]
    artifacts = analyze_specialists({'ohlcv': rows, 'events': [],
        'benchmark': [dict(row, symbol=None, benchmark_id='TAIEX', close=10000+i) for i, row in enumerate(rows)]},
        '2330', '2026-05-01', 'core-1')
    manifest = {'execution_id': '00000000-0000-0000-0000-000000000001',
        'analysis_as_of': '2026-05-01', 'core_snapshot_id': 'core-1',
        'specialists': [{'symbol': a['symbol'], 'role': a['role'], 'input_hash': a['input_hash'],
                        'source_core_snapshot_id': a['core_snapshot_id'], 'reused': True} for a in artifacts]}
    manifest['output_hash'] = digest(manifest)
    return manifest, artifacts


def test_product_serves_real_baseline_without_promoting_missing_models():
    manifest, artifacts = product_inputs()
    value = baseline_projection(manifest, artifacts)
    assert value['model_quality'] == 'NOT_VERIFIED' and value['llm_api_tokens'] == 0
    roles = {a['role']: a for a in value['specialists']}
    assert roles['quant']['baseline_status'] == 'available'
    assert roles['fundamental']['baseline_status'] == 'unavailable'
    assert roles['event']['baseline_status'] == 'unavailable'
    assert roles['event']['metrics']['event_count'] is None
    assert 'event_count' in roles['event']['missing_data']
    assert roles['quant']['metrics']['outperform_probability'] is None
    assert roles['quant']['metrics']['relative_strength_20d_percent'] is not None
    assert all(a['reused'] for a in roles.values())
    assert value['content_hash'] == content_hash({k: v for k, v in value.items() if k != 'content_hash'})
    assert freshness(value, date(2026, 5, 10)) == 'stale'


def test_empty_events_invalidate_previously_cached_zero_count():
    from intelligence_mart.specialists import specialist_versions
    assert specialist_versions('event') == ('3', 'event-source-coverage-v3')


@pytest.mark.parametrize('change', ['metrics', 'symbol', 'date', 'source', 'role'])
def test_product_rejects_tampering_and_cross_symbol_or_future_source(change):
    manifest, artifacts = product_inputs()
    if change == 'metrics': artifacts[0]['metrics']['fake'] = 99
    if change == 'symbol': artifacts[0]['symbol'] = '2454'
    if change == 'date': artifacts[0]['analysis_as_of'] = '2026-05-02'
    if change == 'source': artifacts[0]['core_snapshot_id'] = 'different'
    if change == 'role': artifacts[0]['role'] = artifacts[1]['role']
    if change != 'metrics': artifacts[0]['output_hash'] = digest({k: v for k,v in artifacts[0].items() if k != 'output_hash'})
    with pytest.raises(ValueError): baseline_projection(manifest, artifacts)


def ceo_output(product):
    ev = next(i for a in product['specialists'] for i in a['evidence_ids'])
    return {'schema_version': '1.0.0', 'role': 'ceo', 'stance': 'neutral',
        'thesis': {'text': '僅基於既有動能基準，保留資料不足', 'evidence_ids': [ev]},
        'missing_information': ['財報資料不足'], 'confidence': .5, 'evidence_ids': [ev],
        'supporting_roles': ['quant'], 'opposing_roles': [], 'contradictions': [],
        'bull_case': [], 'bear_case': [], 'principal_risks': [], 'watch_items': [],
        'change_since_previous_analysis': [],
        'validated_role_artifact_hashes': [a['output_hash'] for a in product['specialists']]}


def test_ceo_validation_requires_exact_artifacts_known_evidence_and_honest_missingness():
    product = baseline_projection(*product_inputs())
    output = ceo_output(product)
    assert validate_ceo_output(output, product)['stance'] == 'neutral'
    for mutate in [lambda o: o['thesis'].update(text='目標價格 999999'),
                   lambda o: o['thesis'].update(text='目標價格999999'),
                   lambda o: o['thesis'].update(evidence_ids=['ev-' + '0'*24]),
                   lambda o: o.update(missing_information=[]),
                   lambda o: o.update(change_since_previous_analysis=[o['thesis']]),
                   lambda o: o['validated_role_artifact_hashes'].__setitem__(0, 'sha256:'+'0'*64)]:
        changed = deepcopy(output)
        mutate(changed)
        with pytest.raises(ValueError): validate_ceo_output(changed, product)


def test_ceo_numeric_claims_are_bound_to_the_source_metric():
    product = baseline_projection(*product_inputs())
    output = ceo_output(product)
    metric = next(a for a in product['specialists'] if a['role'] == 'quant')['metrics']['return_20d_percent']
    output['thesis']['text'] = f'動能基準 quant.return_20d_percent={metric}，其餘資訊不足'
    assert validate_ceo_output(output, product)
    output['thesis']['text'] += f'，目標價{metric}'
    with pytest.raises(ValueError):
        validate_ceo_output(output, product)


def test_ceo_does_not_return_invalid_raw_provider_output():
    from intelligence_mart.product_runtime import execute_ceo
    from types import SimpleNamespace
    product = baseline_projection(*product_inputs())
    request = {'request_id': 'r', 'symbol': '2330', 'baseline_json': product,
               'baseline_hash': product['content_hash'], 'profile_id': 'default', 'profile_version': 1}
    class Router:
        def invoke(self, role, value):
            assert role == 'ceo' and value['canonical_numbers_are_read_only']
            return SimpleNamespace(status='succeeded', output={'secret': 'must-not-escape'},
                attempts=[{'provider': 'test', 'raw_payload': 'hidden'}],
                routing={'routing_hash': 'h', 'providers': ['test']}, provider='test', model='test')
    state, report, audit, reason = execute_ceo(request, Router())
    assert state == 'BLOCKED' and report is None and reason == 'output_validation_failed'
    assert audit['attempts'] == [{'provider': 'test'}]


def test_analysis_migration_is_allowlisted_and_protects_terminal_reports():
    from ingestion_core.serving_schema_migration import SUPPORTED
    sql = (Path(__file__).parents[1] / 'infra/postgres/migrations/051_analysis_product.sql').read_text()
    assert '051_analysis_product' in SUPPORTED
    assert 'CEO terminal execution is immutable' in sql
    assert 'ceo_one_active_owner_idx' in sql
    assert 'GRANT USAGE ON SCHEMA control TO janus_private_api' not in sql
    assert 'GRANT SELECT ON private.ledger_events' not in sql
