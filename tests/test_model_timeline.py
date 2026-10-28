from datetime import date, timedelta
import math

import pytest

from packages.market_sessions import verified_stock_market_day
from packages.model_timeline import build_timeline


def inputs():
    days = [str(date(2026, 7, 1) + timedelta(days=i)) for i in range(80)
            if verified_stock_market_day(str(date(2026, 7, 1) + timedelta(days=i)))]
    price = {'bars': [{'date': day, 'close': 100 * math.exp(.01 * i)}
                      for i, day in enumerate(days)], 'source_ids': ['twse']}
    model = lambda target, prediction: {'status': 'ACTIVE_PREDICTED', 'output_name': target,
        'model_version': 'v1', 'input_as_of': days[10], 'prediction': prediction}
    product = {'analysis_as_of': days[10], 'created_at': days[10], 'four_model_serving': {
        'risk': model(['future_rms_vol20'], .2), 'quant': model(['p_up_20d'], .75),
        'fundamental': {**model(['next_month_revenue_yoy_pct'], 12), 'input_as_of': '2026-06'},
        'valuation': model(['log_pe', 'log_pb'], {'log_pe': math.log(20), 'log_pb': math.log(2)})}}
    revenue = {'points': [{'date': '2025-07-31', 'value': 100}, {'date': '2026-07-31', 'value': 110}]}
    pe = {'points': [{'date': days[10], 'value': 22}]}
    pb = {'points': [{'date': days[10], 'value': 2.5}]}
    return days, product, price, revenue, pe, pb


def test_all_four_tasks_compare_correct_targets_units_and_calendar_windows():
    days, product, price, revenue, pe, pb = inputs()
    result = build_timeline([product], price, revenue, pe, pb, today=days[-1])['roles']
    risk = result['risk']['forecasts'][0]
    assert risk['date'] == days[30] and risk['value'] == 20
    assert risk['actual'] == pytest.approx(math.sqrt(252) * .01 * 100)
    quant = result['quant']['forecasts'][0]
    assert quant['value'] == 75 and quant['actual'] == 100
    fund = result['fundamental']['forecasts'][0]
    assert fund['date'] == '2026-07' and fund['actual'] == pytest.approx(10)
    assert result['valuation_pe']['forecasts'][0]['value'] == pytest.approx(20)
    assert result['valuation_pe']['forecasts'][0]['actual'] == 22
    assert result['valuation_pb']['forecasts'][0]['value'] == pytest.approx(2)
    assert risk['evaluation_kind'] == 'published'


def test_missing_session_does_not_compress_twenty_day_window_or_fabricate_result():
    days, product, price, *series = inputs()
    price['bars'] = [p for p in price['bars'] if p['date'] != days[15]]
    result = build_timeline([product], price, *series, today=days[-1])['roles']
    assert result['risk']['forecasts'][0]['date'] == days[30]
    assert result['risk']['forecasts'][0]['actual'] is None
    assert result['quant']['forecasts'][0]['actual'] is None


def test_immature_forecasts_and_late_recomputations_are_explicit():
    days, product, price, *series = inputs()
    product['created_at'] = days[12]
    result = build_timeline([product], price, *series, today=days[15])['roles']
    risk = result['risk']['forecasts'][0]
    assert risk['actual'] is None and risk['date'] == days[30]
    assert risk['evaluation_kind'] == 'retrospective'
    assert all(p['date'] <= days[15] for p in result['risk']['observed'])


def test_missing_models_keep_observed_history_without_fake_forecasts():
    days, product, price, *series = inputs()
    product['four_model_serving'] = {}
    result = build_timeline([product], price, *series, today=days[-1])['roles']
    assert result['risk']['observed']
    assert result['fundamental']['observed']
    assert all(not r['forecasts'] and r['missing'] == 1 for r in result.values())


def test_nonfinite_wrong_targets_and_unsupported_calendar_stay_missing():
    days, product, price, *series = inputs()
    product['four_model_serving']['risk']['prediction'] = float('inf')
    product['four_model_serving']['quant']['output_name'] = 'p_outperform_20d'
    product['four_model_serving']['valuation']['prediction'] = {'log_pe': 999, 'log_pb': True}
    result = build_timeline([product], price, *series, today=days[-1])['roles']
    assert not result['risk']['forecasts'] and not result['quant']['forecasts']
    assert not result['valuation_pe']['forecasts'] and not result['valuation_pb']['forecasts']
    product['four_model_serving']['risk']['input_as_of'] = '2027-01-04'
    product['four_model_serving']['risk']['prediction'] = .2
    assert not build_timeline([product], price, *series, today=days[-1])['roles']['risk']['forecasts']


def test_model_history_membership_and_hash_fences():
    from contextlib import contextmanager
    from fastapi import HTTPException
    from packages.analysis_product import content_hash
    from services.api.analysis import AnalysisService
    from services.api.repository import NotFoundError

    class DB:
        def __init__(self, value, allowed=True):
            self.value, self.allowed, self.queries = value, allowed, []
        @contextmanager
        def _connection(self): yield self
        def execute(self, sql, args):
            self.queries.append((sql, args))
            return self
        def fetchone(self): return {'allowed': self.allowed}
        def fetchall(self): return [{'payload_json': self.value, 'created_at': '2026-07-01'}]
    value = {'symbol': '2330', 'analysis_as_of': '2026-07-01', 'four_model_serving': {}}
    value['content_hash'] = content_hash(value)
    db = DB(value)
    assert AnalysisService(db).model_history('owner-A', '2330')[0]['created_at'] == '2026-07-01'
    assert db.queries[0][1] == ('owner-A', '2330', 'owner-A', '2330')
    assert 'LIMIT 80' in db.queries[1][0] and db.queries[1][1] == ('2330',)
    with pytest.raises(NotFoundError):
        AnalysisService(DB(value, allowed=False)).model_history('owner-B', '2330')
    value['symbol'] = '2882'
    with pytest.raises(HTTPException):
        AnalysisService(DB(value)).model_history('owner-A', '2330')
