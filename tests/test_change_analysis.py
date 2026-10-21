from copy import deepcopy
from contextlib import contextmanager

import pytest

from packages.change_analysis import observations, session_view, fact_snapshot
from packages.analysis_product import content_hash


def fact(value=10, **changes):
    return {'symbol': '2330', 'kind': 'operation', 'metric': 'eps_yoy', 'value': value,
            'series_key': 'same-filing', 'unit': '%', 'basis': 'same-filing', 'period': '2026-06-30',
            'source_event': None, 'source_version': '1', 'source_available_at': '2026-08-01T00:00:00Z',
            'evidence_refs': [{'source_id': 'mops', 'provenance_id': 'p', 'location': 'iceberg://core.financials_v1'}],
            'valid_until': '2027-08-01T00:00:00Z', 'headline': '獲利同比增加',
            'meaning': '同份財報比較', 'condition': 'positive', **changes}


def observe(facts, previous=(), cutoff='2026-08-02T00:00:00Z'):
    return observations(facts, previous, symbol='2330', cutoff_at=cutoff)


def test_rule_transitions_missing_recovery_revision_and_no_model_required():
    first = observe([fact()])
    assert first[0]['state'] == 'new'
    ongoing = observe([fact()], first)
    assert ongoing[0]['state'] == 'ongoing'
    assert ongoing[0]['observation_id'] == first[0]['observation_id']
    assert observe([fact(20)], first)[0]['state'] == 'strengthened'
    assert observe([fact(5)], first)[0]['state'] == 'weakened'
    assert observe([fact(0)], first)[0]['state'] == 'resolved'
    assert observe([fact(-1)], first)[0]['state'] == 'invalidated'
    revised = observe([fact(11, source_version='2')], first)[0]
    assert revised['revision'] and revised['previous_observation_id'] == first[0]['observation_id']
    pending = observe([], first)
    assert pending[0]['state'] == 'pending' and pending[0]['value'] == 10
    assert observe([fact()], pending)[0]['state'] == 'ongoing'
    assert observe([], first, cutoff='2027-09-02T00:00:00Z')[0]['state'] == 'expired'
    assert observe([], first, cutoff='2028-09-02T00:00:00Z') == []
    changed_unit = observe([fact(100, unit='元')], first)[0]
    assert changed_unit['comparison_value'] is None and changed_unit['state'] == 'ongoing'
    assert 'probability' not in str(first)


@pytest.mark.parametrize('changed', [dict(symbol='2454'), dict(value=float('nan')),
    dict(value=True), dict(evidence_refs=[]), dict(unit=''),
    dict(source_available_at='2026-08-03T00:00:00Z')])
def test_rejects_cross_symbol_future_unproven_or_nonfinite_facts(changed):
    with pytest.raises(ValueError):
        observe([fact(**changed)])


def test_snapshot_cutoff_holiday_late_data_and_corporate_action_no_fake_return():
    def price(day, close, available):
        return dict(symbol='2330', source_id='twse', provenance_id='p'+day,
                    trade_date=day, close=close, observed_at=available)
    datasets = {'ohlcv': [price('2026-10-16', 100, '2026-10-16T07:00:00Z'),
                          price('2026-10-19', 50, '2026-10-19T07:00:00Z')], 'events': []}
    pre = fact_snapshot(datasets, '2330', '2026-10-19', 'core-1',
                        '2026-10-19T09:00:00+08:00', session='premarket')
    post = fact_snapshot(datasets, '2330', '2026-10-19', 'core-1', '2026-10-19T16:00:00+08:00')
    assert pre[0]['value'] == 100 and pre[0]['period'] == '2026-10-16'
    assert post[0]['value'] == 50 and post[0]['period'] == '2026-10-19'
    assert all('return' not in f['metric'] for f in post)  # Unadjusted split is not a return signal.
    holiday = fact_snapshot(datasets, '2330', '2026-10-18', 'core-1', '2026-10-18T16:00:00+08:00')
    assert holiday[0]['period'] == '2026-10-16'
    product = {'symbol': '2330', 'change_analysis': {'premarket': {
        'cutoff_at': '2026-10-19T09:00:00+08:00',
        'observations': observations(pre, [], symbol='2330', cutoff_at='2026-10-19T09:00:00+08:00')}}}
    view = session_view(product, 'premarket', cutoff_at='2026-10-19T09:00:00+08:00')
    assert view['price_date'] == '2026-10-16' and view['observations'][0]['state_label'] == '新增'
    early = session_view(product, 'premarket', cutoff_at='2026-10-18T09:00:00+08:00')
    assert early['observations'] == []

