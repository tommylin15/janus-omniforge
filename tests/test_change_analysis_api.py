from contextlib import contextmanager
import pytest
from packages.analysis_product import content_hash
from tests.test_change_analysis import fact, observe

class ReadConnection:
    def __init__(self, membership, products):
        self.membership, self.products, self.statements = membership, products, []
    def execute(self, sql, args):
        assert sql.lstrip().startswith('SELECT')
        self.statements.append((sql, args))
        if 'membership GROUP BY' in sql:
            self.result = self.membership.get(args[0], [])
        else:
            self.result = [{'symbol': p['symbol'], 'payload_json': p} for p in self.products if p['symbol'] in args[0]]
        return self
    def fetchall(self):
        return self.result


def test_owner_filter_uses_one_public_read_and_tampering_fails():
    from services.api.analysis import AnalysisService
    product = {'symbol': '2330', 'change_analysis': {'postmarket': {
        'cutoff_at': '2026-08-02T00:00:00Z',
        'observations': observe([fact(valid_until='2099-08-01T00:00:00Z')])}}}
    product['content_hash'] = content_hash(product)
    connection = ReadConnection({'owner-a': [{'symbol': '2330', 'priority': 0}], 'owner-b': []}, [product])
    class Repository:
        @contextmanager
        def _connection(self):
            yield connection
    service = AnalysisService(Repository())
    # Use a long-lived evidence validity for this wall-clock read-model test.
    assert service.today_changes('owner-b')['items'] == []
    result = service.today_changes('owner-a')
    assert len(result['items']) == 1 and result['items'][0]['symbol'] == '2330'
    assert len(connection.statements) == 3
    product['symbol'] = '2330'
    product['change_analysis']['postmarket']['observations'][0]['value'] = 999
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        service.today_changes('owner-a')


def test_today_changes_prefers_confirmed_change_over_pending_event_in_same_stock():
    from services.api.analysis import AnalysisService
    connection = ReadConnection({'owner-a': [{'symbol': '2330', 'priority': 0}]}, [])
    class Repository:
        @contextmanager
        def _connection(self):
            yield connection
    service = AnalysisService(Repository())
    valid = {'identity': 'current-price', 'symbol': '2330', 'kind': 'price',
             'state': 'new', 'changed': True, 'status': 'available',
             'source_available_at': '2026-10-23T07:00:00Z',
             'headline': '已確認收盤價'}
    missing = {'identity': 'old-event', 'symbol': '2330', 'kind': 'event',
               'state': 'pending', 'changed': False, 'status': 'missing',
               'source_available_at': '2026-10-15T07:00:00Z',
               'headline': '過時事件待更新'}
    service._changes = lambda symbols, session: {
        '2330': {'status': 'partial', 'cutoff_at': '2026-10-23T08:00:00Z',
                 'price_date': '2026-10-23',
                 'observations': [missing, valid]}}
    result = service.today_changes('owner-a')
    assert len(result['items']) == 1
    assert result['items'][0]['identity'] == 'current-price'
    assert result['status'] == 'partial'

    # If there is genuinely no confirmed observation, do not discard the
    # missing evidence or falsely change the view's partial status.
    service._changes = lambda symbols, session: {
        '2330': {'status': 'partial', 'cutoff_at': '2026-10-23T08:00:00Z',
                 'price_date': None, 'observations': [missing]}}
    fallback = service.today_changes('owner-a')
    assert fallback['items'][0]['state'] == 'pending'
    assert fallback['items'][0]['status'] == 'missing'
    assert fallback['status'] == 'partial'
