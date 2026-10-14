from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace

from ingestion_core.serving_projection import StockServingProjection
from packages.web_api import CoreQueryService
from services.api.public_runtime import market_serving_query
from services.api.repository import PostgresWorkspaceRepository


def test_market_projection_keeps_full_batch_and_official_index_without_stock_membership():
    class Cursor:
        def __init__(self): self.many=[]
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def executemany(self,sql,rows): self.many.append((sql,list(rows)))
        def execute(self,*_): pass
    cursor=Cursor()
    connection=SimpleNamespace(transaction=nullcontext,cursor=lambda:cursor,cursor_value=cursor)
    class Connection:
        def __enter__(self): return connection
        def __exit__(self,*_): pass
    projection = StockServingProjection(Connection)
    for dataset, rows in (
        ('benchmark', [{'benchmark_id': 'TAIEX', 'trade_date': date(2026, 10, 12), 'close': '25000'}]),
        ('institutional', [{'symbol': '9999', 'market': 'TWSE', 'trade_date': date(2026, 10, 12),
                            'investor_type': 'foreign', 'net_shares': '-1200'}]),
    ):
        assert projection.publish(dataset, rows, execution_id='e', provenance_id='p',
                                  source_id='twse', core_snapshot_id=1) == 1
    assert all('control.market_serving_recent' in sql for sql, _ in connection.cursor_value.many)
    assert connection.cursor_value.many[0][1][0][1] == 'TAIEX'


def test_homepage_queries_are_bounded_postgres_only_and_stock_series_is_parameterized():
    sql, values, _ = market_serving_query('core.benchmark_v1', ('TAIEX', 40))
    assert 'publication.market_serving_recent' in sql and values == ('benchmark', 'TAIEX', 40)
    sql, values, payload = market_serving_query('core.institutional_v1', ('2330', 600, 0))
    assert payload and values == ('institutional', '2330', 600, 0)
    sql, values, payload = market_serving_query('core.institutional_v1', ())
    assert 'max(sort_at)' in sql and not payload
    assert market_serving_query('core.financials_v1', ()) is None


def test_institutional_series_keeps_negative_zero_and_missing_lineage_without_core_scan():
    rows = [
        {'trade_date': '2026-10-10', 'investor_type': 'foreign', 'net_shares': '-100', 'source_id': 'twse', 'provenance_id': 'p'},
        {'trade_date': '2026-10-11', 'investor_type': 'foreign', 'net_shares': '0', 'source_id': 'twse', 'provenance_id': 'p'},
        {'trade_date': '2026-10-12', 'investor_type': 'foreign', 'net_shares': '100'},
        {'trade_date': '2026-10-12', 'investor_type': 'dealer', 'net_shares': '50', 'source_id': 'twse', 'provenance_id': 'p'},
    ]
    service = CoreQueryService(lambda *_: (_ for _ in ()).throw(AssertionError('no Core scan')),
                               serving_series=lambda *_: rows)
    result = service.visual_series('2330', 'foreign')
    assert [p['value'] for p in result['points']] == ['-100', '0', None]
    assert result['unit'] == 'shares' and result['data_status'] == 'partial'


def test_private_write_lock_does_not_use_controller_lock_and_unlocks_on_failure(monkeypatch):
    import psycopg
    statements = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql): statements.append(sql)
    monkeypatch.setattr(psycopg, 'connect', lambda *_args, **_kwargs: Connection())
    repo = PostgresWorkspaceRepository('unused-test-dsn')
    try:
        with repo.private_mart_write_lock():
            raise ValueError('write failed')
    except ValueError:
        pass
    assert statements == ["SET lock_timeout='0'; SET statement_timeout='120s'",
                          'SELECT pg_advisory_lock(1835102836,4)',
                          'SELECT pg_advisory_unlock(1835102836,4)']


def test_financial_serving_reuses_same_period_without_daily_row_growth():
    row = {'symbol': '6488', 'fiscal_year': 2026, 'fiscal_quarter': 3, 'statement_type': 'monthly_revenue',
           'metric': 'monthly_revenue', 'fiscal_period_end': '2026-09-30', 'value': '100',
           'availability_at': '2026-10-13T01:00:00Z'}
    values = dict(execution_id='e', provenance_id='p', source_id='mops', core_snapshot_id=1)
    first = StockServingProjection._row('financials', row, **values)
    newer = StockServingProjection._row('financials', dict(row, availability_at='2026-10-14T01:00:00Z'), **values)
    another = StockServingProjection._row('financials', dict(row, fiscal_period_end='2026-08-31'), **values)
    assert first[2] == newer[2] and first[2] != another[2]
