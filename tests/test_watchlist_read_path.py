from contextlib import contextmanager
from uuid import uuid4

from services.api.repository import PostgresWorkspaceRepository


def test_watchlist_read_preserves_offlist_owner_rows_without_writing():
    owner = uuid4()
    queries = []
    row = {"user_id": owner, "symbol": "2330", "active": True, "in_market_500": False}

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
    assert "AS in_market_500" in sql


def test_blank_watchlist_search_does_not_read_the_universe():
    assert PostgresWorkspaceRepository("test").search_watchlist_stocks("   ") == []
