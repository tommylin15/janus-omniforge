"""Versioned, source-bound facts and observations. No model or owner inputs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite

from packages.analysis_product import content_hash

RULE_VERSION = 'change-facts-v1'
STATE_LABELS = {'new': '新增', 'ongoing': '持續', 'strengthened': '增強',
                'weakened': '減弱', 'resolved': '解除', 'invalidated': '失效',
                'expired': '過期', 'pending': '待更新'}


def instant(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed.astimezone(timezone.utc)


def observations(facts, previous, *, symbol, cutoff_at):
    """Same evidence is idempotent; unavailable evidence never clears a condition."""
    cutoff = instant(cutoff_at)
    old = {item['identity']: item for item in previous}
    if any(item['symbol'] != symbol or instant(item['cutoff_at']) > cutoff for item in previous):
        raise ValueError('previous observation scope or time mismatch')
    result = []
    seen = set()
    for fact in facts:
        if fact['symbol'] != symbol or instant(fact['source_available_at']) > cutoff:
            raise ValueError('fact scope or cutoff mismatch')
        value = fact['value']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError('finite fact value required')
        if not fact['evidence_refs'] or not fact['unit'] or not fact['period']:
            raise ValueError('fact lacks evidence, unit or period')
        identity = content_hash([symbol, fact['kind'], fact['metric'], fact['series_key']])
        if identity in seen:
            raise ValueError('ambiguous fact identity')
        seen.add(identity)
        prior = old.get(identity)
        input_hash = content_hash({k: v for k, v in fact.items() if k not in {'evidence_refs', 'valid_until'}})
        if prior and prior['input_hash'] == input_hash:
            item = dict(prior)
            # A recovered source restores its factual state, not a new event.
            if item['state'] not in {'resolved', 'invalidated', 'expired'}:
                item['state'] = 'ongoing'
                item['last_confirmed_state'] = 'ongoing'
            item['status'] = 'available'
            item['evidence_refs'] = fact['evidence_refs']
            item['cutoff_at'] = cutoff_at
            item['changed'] = False
            result.append(item)
            continue
        state = 'new' if prior is None else 'ongoing'
        comparable = prior and all(prior.get(k) == fact.get(k) for k in ('unit', 'basis'))
        comparison = prior['value'] if comparable else None
        if comparable and fact.get('condition') == 'positive':
            if prior['value'] > 0 and value < 0:
                state = 'invalidated'
            elif prior['value'] > 0 and value == 0:
                state = 'resolved'
            elif value > 0 and prior['value'] > 0 and value != prior['value']:
                state = 'strengthened' if value > prior['value'] else 'weakened'
            elif value > 0 and prior['value'] <= 0:
                state = 'new'
        revision = bool(prior and prior['period'] == fact['period'] and
                        prior.get('source_event') == fact.get('source_event') and
                        (prior['value'] != value or prior.get('source_version') != fact.get('source_version')))
        item = {**fact, 'identity': identity, 'input_hash': input_hash,
                'observation_id': content_hash([identity, input_hash, RULE_VERSION]),
                'previous_observation_id': prior['observation_id'] if prior else None,
                'comparison_value': comparison, 'previous_period': prior['period'] if prior else None,
                'state': state, 'last_confirmed_state': state, 'revision': revision,
                'changed': prior is None or not comparable or comparison != value or prior['period'] != fact['period'],
                'status': 'available', 'rule_version': RULE_VERSION,
                'analysis_as_of': fact['period'], 'cutoff_at': cutoff_at,
                'next_check': '下次同口徑資料更新後確認',
                'invalidation_condition': ('同口徑數值不再大於零' if fact.get('condition') == 'positive'
                                           else '來源更正或口徑改變時重新確認')}
        if comparable and value != comparison:
            item['meaning'] = f'前次 {prior["period"]} 為 {comparison:g} {fact["unit"]}；本次 {fact["period"]} 為 {value:g} {fact["unit"]}。' + (
                '這是同一期來源修訂。' if revision else '僅描述同口徑數值變化，不推論價格因果。')
        result.append(item)
    for identity, prior in old.items():
        if identity in seen:
            continue
        item = dict(prior)
        item['state'] = (prior['state'] if prior['state'] in {'resolved', 'invalidated', 'expired'} else
                         'expired' if instant(item['valid_until']) < cutoff else 'pending')
        item['status'] = 'stale' if item['state'] == 'expired' else 'missing'
        if item['state'] in {'resolved', 'invalidated', 'expired'} and instant(item['valid_until']) < cutoff - timedelta(days=365):
            continue
        result.append(item)
    return sorted(result, key=lambda item: (item['kind'], item['metric'], item['identity']))


def fact_snapshot(datasets, symbol, as_of, snapshot, cutoff_at, *, session='postmarket'):
    """Only accepted Core rows, with actual periods and availability, enter prose."""
    from intelligence_mart.specialists import validated_inputs, number
    from intelligence_mart.facts import _evidence_id, _financial_period_time, _instant
    rows, evidence, rejected = validated_inputs(datasets, symbol, as_of, snapshot,
                                          preserve_financial_basis=True)
    refs = {e['evidence_id']: e for e in evidence}
    cutoff = instant(cutoff_at)
    candidates = {}
    conflicting = {r['evidence_id'] for r in rejected if r['reason'] == 'conflict'}
    blocked = {name for name, values in datasets.items() if any(
        _evidence_id(name, row, snapshot, preserve_financial_basis=True) in conflicting
        for row in values if row.get('symbol') == symbol)}

    def add(dataset, row, metric, raw, label, unit, period, basis, *, condition=None, event=None):
        value = None if isinstance(raw, bool) else number(raw)
        ref = refs.get(_evidence_id(dataset, row, snapshot, preserve_financial_basis=True))
        if dataset in blocked or value is None or not ref or not period or not unit:
            return
        times = [_instant(row.get(k)) for k in ('availability_at', 'published_at', 'observed_at',
                  'record_at', 'trade_date', 'observed_date') if row.get(k) is not None]
        if not times or any(t is None or t > cutoff for t in times):
            return
        available = max(times)
        kind = {'ohlcv': 'price', 'financials': 'operation', 'valuation': 'valuation', 'events': 'event'}[dataset]
        series = [row.get('source_id'), metric, basis, event]
        key = content_hash(series)
        lifetime = 400 if dataset == 'financials' else 180 if dataset == 'events' else 14
        shown_unit = {'TWD': '元', 'TWD_per_share': '元／股', 'percent': '%'}.get(unit, unit)
        fact = {'symbol': symbol, 'kind': kind, 'metric': metric, 'value': value,
                'unit': unit, 'period': period, 'basis': basis, 'series_key': key,
                'source_event': event, 'source_version': row.get('source_version') or row.get('revision'),
                'source_available_at': available.isoformat(),
                'evidence_refs': [ref], 'condition': condition,
                'headline': f'{label} {value:g} {shown_unit}',
                'meaning': ('同份財報披露的同比變化，正值表示較去年同期增加；不代表未來成長。'
                            if condition else '已公布的當期數值；缺比較期時不推算成長或高低估。'),
                'valid_until': (available + timedelta(days=lifetime)).isoformat(),
                'fact_type': 'confirmed_fact'}
        if key not in candidates or (period, available.isoformat()) > (
                candidates[key]['period'], candidates[key]['source_available_at']):
            candidates[key] = fact

    for row in rows.get('ohlcv', []):
        from zoneinfo import ZoneInfo
        if session == 'premarket' and str(row.get('trade_date', '')) >= cutoff.astimezone(ZoneInfo('Asia/Taipei')).date().isoformat():
            continue
        add('ohlcv', row, 'close', row.get('close'), '收盤價', '元／股',
            str(row.get('trade_date') or ''), 'reported_close')
    for row in rows.get('valuation', []):
        for metric, label in (('pe_ratio', '本益比'), ('pb_ratio', '股價淨值比')):
            if number(row.get(metric)) is not None and number(row[metric]) > 0:
                add('valuation', row, metric, row[metric], label, '倍',
                    str(row.get('observed_date') or row.get('observed_at', ''))[:10], 'reported_ratio')
    for row in rows.get('financials', []):
        metric = str(row.get('metric', ''))
        label = ('月營收' if row.get('statement_type') == 'monthly_revenue' else
                 '單季每股盈餘' if metric.startswith('eps_') and row.get('is_single_quarter') else None)
        growth = metric in {'eps_yoy_percent_same_filing', 'net_income_parent_yoy_percent_same_filing'}
        if growth:
            if row.get('financial_feature_version') != 'same-filing-comparatives-v1' or row.get('unit') != 'percent':
                continue
            label = '同份財報每股盈餘年增率' if metric.startswith('eps') else '同份財報獲利年增率'
        if label:
            period = _financial_period_time(row)
            add('financials', row, metric, row.get('value'), label, row.get('unit'),
                period.date().isoformat() if period else '',
                [row.get('statement_type'), row.get('period_basis'), row.get('report_scope'),
                 row.get('share_basis_status')], condition='positive' if growth else None)
    for row in rows.get('events', []):
        event = row.get('event_id') or row.get('source_event_id')
        if event:
            from intelligence_mart.facts import _severity
            add('events', row, 'severity', _severity(row.get('severity')), '公告嚴重程度', '／100',
                str(row.get('published_at', ''))[:10], 'source_event_severity', event=str(event))
    return sorted(candidates.values(), key=lambda fact: (fact['kind'], fact['metric'], fact['series_key']))


def session_view(product, session, *, cutoff_at):
    """Two read-only views of one persisted snapshot; no invented trading day."""
    if session not in {'premarket', 'postmarket'}:
        raise ValueError('unknown session')
    cutoff = instant(cutoff_at)
    changes = (product.get('change_analysis') or {}).get(session, {})
    items = []
    for raw in changes.get('observations', []):
        item = dict(raw)
        if instant(item['source_available_at']) > cutoff or instant(item['cutoff_at']) > cutoff:
            continue
        if instant(item['valid_until']) < cutoff:
            item.update(state='expired', status='stale')
        item['state_label'] = STATE_LABELS[item['state']]
        items.append(item)
    prices = [item['period'] for item in items if item['kind'] == 'price']
    return {'symbol': product['symbol'], 'session': session, 'cutoff_at': changes.get('cutoff_at'),
            'view_cutoff_at': cutoff_at, 'price_date': max(prices) if prices else None,
            'basis_note': '依最近已保存的收盤資料；公告各依來源時間，不視為即時或完整收盤分析。',
            'status': 'available' if items and all(i['status'] == 'available' for i in items) else 'partial',
            'observations': items, 'rule_version': RULE_VERSION}
