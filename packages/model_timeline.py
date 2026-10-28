"""Bounded display of saved forecasts and observed outcomes; never infer models."""
from datetime import date, datetime, time, timedelta
import math
from zoneinfo import ZoneInfo

from packages.market_sessions import verified_stock_market_day


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def build_timeline(products, prices, revenue, pe, pb, *, today):
    """Dates are target-window ends. Only actual saved predictions are plotted."""
    close = {p['date']: number(p.get('close')) for p in prices.get('bars', [])
             if p.get('date') and p['date'] <= today}
    first = min(close, default=today)
    # shortcut: the shared verified closure list covers 2026 only; add a verified
    # next-year calendar before evaluating targets outside 2026.
    days = []
    start, end = date.fromisoformat(first), date.fromisoformat(today) + timedelta(days=60)
    while start <= end:
        if start.year == 2026 and verified_stock_market_day(start.isoformat()):
            days.append(start.isoformat())
        start += timedelta(days=1)
    index = {day: i for i, day in enumerate(days)}
    risk_actual, quant_actual, returns = {}, {}, {}
    for i, day in enumerate(days):
        window = [close.get(d) for d in days[max(0, i - 20):i + 1]]
        if day <= today and len(window) == 21 and all(p is not None and p > 0 for p in window):
            risk_actual[day] = math.sqrt(252 / 20 * sum(
                math.log(window[j] / window[j - 1]) ** 2 for j in range(1, 21))) * 100
            returns[day] = (window[-1] / window[0] - 1) * 100
            quant_actual[day] = 100.0 if window[-1] > window[0] else 0.0

    def observations(series):
        return {p['date']: number(p.get('value')) for p in series.get('points', [])
                if p.get('date') and p['date'] <= today}

    rev = {d[:7]: v for d, v in observations(revenue).items()}
    yoy = {}
    for month, value in rev.items():
        previous = rev.get(f'{int(month[:4]) - 1}{month[4:]}')
        if value is not None and previous is not None and previous > 0:
            yoy[month] = (value / previous - 1) * 100

    actuals = {'risk': risk_actual, 'quant': quant_actual, 'fundamental': yoy,
               'valuation_pe': observations(pe), 'valuation_pb': observations(pb)}
    result = {key: {'observed': [{'date': d, 'value': v} for d, v in sorted(values.items())],
                    'forecasts': [], 'missing': 0, 'pending': 0}
              for key, values in actuals.items()}
    seen = set()
    for product in sorted(products, key=lambda p: p['analysis_as_of']):
        if str(product['analysis_as_of']) > today:
            continue
        for role in ('quant', 'risk', 'fundamental', 'valuation'):
            model = (product.get('four_model_serving') or {}).get(role) or {}
            heads = ('valuation_pe', 'valuation_pb') if role == 'valuation' else (role,)
            signal = str(product['analysis_as_of'] if role == 'valuation' else model.get('input_as_of') or '')[:10]
            version = model.get('model_version')
            identity = (role, signal, version)
            if identity in seen:
                continue
            if model.get('status') not in {'ACTIVE_PREDICTED', 'ACTIVE_CACHED'} or not signal or not version:
                for head in heads:
                    result[head]['missing'] += 1
                continue
            expected = {'quant': {'p_up_20d'}, 'risk': {'future_rms_vol20'},
                        'fundamental': {'next_month_revenue_yoy_pct'},
                        'valuation': {'log_pe', 'log_pb'}}[role]
            outputs = model.get('output_name')
            if isinstance(outputs, str):
                outputs = [outputs]
            if not isinstance(outputs, list) or set(outputs) != expected:
                for head in heads:
                    result[head]['missing'] += 1
                continue
            seen.add(identity)
            saved_at = str(product.get('created_at') or '')
            try:
                saved = datetime.fromisoformat(saved_at.replace('Z', '+00:00'))
                # Date-only fixture/legacy values have no intraday proof.
                if saved.tzinfo is None:
                    saved = saved.replace(tzinfo=ZoneInfo('Asia/Taipei'))
                saved = saved.astimezone(ZoneInfo('Asia/Taipei'))
                published = saved.date().isoformat()
            except ValueError:
                saved, published = None, ''
            for head in heads:
                value = number(model.get('prediction')) if role != 'valuation' else number(
                    (model.get('prediction') if isinstance(model.get('prediction'), dict) else {}).get(
                        'log_pe' if head.endswith('pe') else 'log_pb'))
                target = signal
                actual = None
                evaluation_kind = 'retrospective'
                if role in ('risk', 'quant'):
                    i = index.get(signal)
                    if i is None or i + 20 >= len(days):
                        result[head]['missing'] += 1
                        continue
                    target = days[i + 20]
                    first_open = datetime.combine(date.fromisoformat(days[i + 1]), time(9),
                                                  ZoneInfo('Asia/Taipei'))
                    if saved is not None and saved < first_open:
                        evaluation_kind = 'published'
                    if role == 'risk':
                        value = value * 100 if value is not None and value >= 0 else None
                        actual = risk_actual.get(target)
                    else:
                        value = value * 100 if value is not None and 0 <= value <= 1 else None
                        window = [close.get(d) for d in days[i:i + 21]]
                        if target <= today and len(window) == 21 and all(p is not None and p > 0 for p in window):
                            actual = 100.0 if window[-1] > window[0] else 0.0
                            actuals['quant'][target] = actual
                elif role == 'fundamental':
                    try:
                        month = date.fromisoformat(signal[:7] + '-01')
                    except ValueError:
                        result[head]['missing'] += 1
                        continue
                    target = (month.replace(day=28) + timedelta(days=4)).strftime('%Y-%m')
                    actual = yoy.get(target)
                    if published and published[:7] <= target:
                        evaluation_kind = 'published'
                else:
                    if value is not None and -700 < value < 700:
                        value = math.exp(value)
                    else:
                        value = None
                    actual = actuals[head].get(signal)
                    if published == signal:
                        evaluation_kind = 'contemporaneous_estimate'
                if value is None:
                    result[head]['missing'] += 1
                    continue
                if actual is None:
                    result[head]['pending'] += 1
                result[head]['forecasts'].append({'date': target, 'signal_date': signal,
                    'value': value, 'actual': actual, 'model_version': version,
                    'published_date': published or None,
                    'actual_return_percent': returns.get(target) if role == 'quant' else None,
                    'evaluation_kind': evaluation_kind,
                    'status': 'matched' if actual is not None else 'awaiting_actual'})
    result['quant']['observed'] = [{'date': d, 'value': v} for d, v in sorted(actuals['quant'].items())]
    return {'schema_version': 'model-timeline.v1', 'as_of': today, 'roles': result,
            'source_ids': sorted({str(s) for series in (prices, revenue, pe, pb)
                                  for s in series.get('source_ids', [])}),
            'calendar_note': '2026 verified exchange closures; unsupported years stay missing',
            'status': 'available' if products else 'no_saved_forecasts'}
