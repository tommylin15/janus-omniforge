"""SEQ-07 bounded Owner report history and ML report refresh acceptance."""
from contextlib import contextmanager
import pytest
from fastapi import HTTPException
from packages.analysis_product import content_hash
from packages.stock_report_policy import attach_stock_report
from services.api.analysis import AnalysisService
from services.api.repository import NotFoundError


class Result:
    def __init__(self, row=None, rows=None):
        self.row, self.rows = row, rows or []
    def fetchone(self):
        return self.row
    def fetchall(self):
        return self.rows


class DB:
    def __init__(self, reports, allowed=True):
        self.reports = reports
        self.allowed = allowed
        self.queries = []
    @contextmanager
    def _connection(self):
        yield self
    def execute(self, query, params):
        self.queries.append((query, params))
        if 'AS allowed' in query:
            return Result({'allowed': self.allowed})
        if "payload_json->'stock_report'" in query:
            return Result(rows=self.reports[:params[-1]])
        raise AssertionError("Unexpected SQL")


def saved(symbol='2330', day='2026-10-24'):
    report = {'schema_version': 'stock-report.v1', 'symbol': symbol,
              'report_as_of': day, 'model_signature': 'version-1'}
    report['report_hash'] = content_hash(report)
    return {'analysis_as_of': day, 'stock_report': report,
            'refresh': {'generated': True, 'reason': 'first_report'}}


def test_owner_membership_scope_deduplicates_reuse_and_verifies_hash():
    latest, older = saved(), saved(day='2026-10-23')
    db = DB([latest, latest, older])
    result = AnalysisService(db).stock_report_history('owner-A', '2330', 10)
    assert result['status'] == 'available'
    assert [v['report']['report_as_of'] for v in result['items']] == [
        '2026-10-24', '2026-10-23']
    assert db.queries[0][1] == ('owner-A', '2330', 'owner-A', '2330')
    assert db.queries[1][1] == ('2330', 100)
    with pytest.raises(NotFoundError):
        AnalysisService(DB([latest], allowed=False)).stock_report_history('owner-B', '2330')


def test_corrupt_or_wrong_symbol_report_is_not_returned():
    row = saved()
    row['stock_report']['report_as_of'] = '2030-01-01'
    with pytest.raises(HTTPException) as exc:
        AnalysisService(DB([row])).stock_report_history('owner-A', '2330')
    assert exc.value.status_code == 503
    with pytest.raises(HTTPException):
        AnalysisService(DB([saved('2882')])).stock_report_history('owner-A', '2330')


def _facts(version='m1'):
    specialists = [{'role': role, 'model_version': 'baseline', 'feature_version': 'v0',
                    'model_status': 'deterministic', 'status': 'available',
                    'metrics': {}, 'missing_data': [], 'plain_language': 'facts'}
                   for role in ('quant', 'risk', 'fundamental', 'valuation')]
    return {'symbol': '2330', 'analysis_as_of': '2026-10-25', 'execution_id': version,
            'specialists': specialists,
            'four_model_serving': {'quant': {'status': 'ACTIVE_PREDICTED',
                'model_version': version, 'model_sha256': 'a' * 64,
                'output_name': 'p_up_20d', 'prediction': 0.55, 'input_as_of': '2026-10-25'}}}


def _inputs():
    return {'latest_close': 100.0, 'financial_input_hash': 'unchanged',
            'roles': {r: {'input_as_of': '2026-10-25', 'missing_features': []}
                      for r in ('quant', 'risk', 'fundamental', 'valuation')}}


def test_ml_version_changes_report_without_promoting_missing_roles():
    first = attach_stock_report(_facts('m1'), _inputs())
    assert first['stock_report']['serving_roles'][0]['prediction'] == 0.55
    assert first['stock_report']['serving_roles'][1]['status'] == 'NOT_VERIFIED'
    assert first['stock_report']['report_kind'] == 'deterministic_facts_not_ceo'
    second = attach_stock_report(_facts('m2'), _inputs(), first)
    assert second['stock_report_refresh']['reason'] == 'model_changed'
    assert first['stock_report']['report_hash'] != second['stock_report']['report_hash']
    same = attach_stock_report(_facts('m2'), _inputs(), second)
    assert same['stock_report_refresh']['generated'] is False
    assert same['stock_report']['report_hash'] == second['stock_report']['report_hash']
