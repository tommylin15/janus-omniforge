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
