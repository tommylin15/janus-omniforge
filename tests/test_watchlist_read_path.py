from contextlib import contextmanager
from uuid import uuid4

from services.api.repository import PostgresWorkspaceRepository


def test_watchlist_read_preserves_offlist_owner_rows_without_writing():
    owner = uuid4()
    queries = []
    row = {"user_id": owner, "symbol": "2330", "active": True, "in_market": False}

    class Connection:
        def execute(self, sql, params):
            queries.append((sql, params))
            return self

        def fetchall(self):
            return [row]

    class Repository(PostgresWorkspaceRepository):
        @contextmanager
        def _connection(self):
            yield Connection()

    assert Repository('test').watchlist(owner) == [row]
    assert len(queries) == 1
    sql, params = queries[0]
    assert params == (owner,)
    assert "WHERE w.user_id=%s AND w.active\n" in sql
    assert "UPDATE" not in sql
    assert "AS in_market" in sql
    assert "control.market_universe_members" in sql
    assert "LEFT JOIN LATERAL" in sql and "publication.stock_serving_recent" in sql
    assert "r.sort_at<price.sort_at" in sql


def test_blank_watchlist_search_does_not_read_the_universe():
    assert PostgresWorkspaceRepository("test").search_watchlist_stocks("   ") == []


def test_trade_search_includes_registered_etf_and_uses_bound_parameters():
    queries = []
    row = {"symbol": "00719B", "stock_name": "元大美債1-3", "market": "TWSE", "enabled": True}

    class Connection:
        def execute(self, sql, params):
            queries.append((sql, params))
            return self

        def fetchall(self):
            return [row]

    class Repository(PostgresWorkspaceRepository):
        @contextmanager
        def _connection(self):
            yield Connection()

    repository = Repository('test')
    assert repository.search_trade_instruments(' 元 ') == [row]
    sql, params = queries[0]
    assert params == ('元',) * 4
    assert 'market_universe_members' not in sql
    assert 'LIMIT 20' in sql
    assert repository.search_trade_instruments(' ') == []
    assert len(queries) == 1
