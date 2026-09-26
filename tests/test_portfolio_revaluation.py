from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from services.api.private_pipeline import PrivatePipeline
from services.api.repository import PostgresWorkspaceRepository


USER = UUID("00000000-0000-0000-0000-000000000001")


def _buy() -> dict:
    return {
        "event_id": uuid4(),
        "user_id": USER,
        "ledger_version": 5,
        "event_action": "ORIGINAL",
        "event_type": "BUY",
        "trade_date": date(2026, 9, 1),
        "symbol": "2330",
        "shares": Decimal("1"),
        "price": Decimal("10"),
        "cash_amount": None,
        "fee": Decimal("0"),
        "tax": Decimal("0"),
        "currency": "TWD",
        "reverses_event_id": None,
    }


def test_empty_change_queue_still_revalues_existing_portfolio_users_without_advancing_checkpoint():
    class Repository:
        def __init__(self):
            self.advanced = []

        def pipeline_checkpoint(self):
            return 7

        def pipeline_batch(self, checkpoint, limit):
            assert checkpoint == 7
            return []

        def portfolio_user_ids_for_pipeline(self, limit=500):
            assert limit == 500
            return [USER]

        def ledger_for_pipeline(self, user_id):
            assert user_id == USER
            return [_buy()]

        def stock_identities(self, symbols):
            assert symbols == {"2330"}
            return {"2330": {"symbol": "2330", "name": "台積電", "market": "TWSE", "enabled": True}}

        def watchlist_for_pipeline(self, user_id):
            return []

        def investment_profile_for_pipeline(self, user_id):
            return None

        def advance_pipeline_checkpoint(self, value):
            self.advanced.append(value)

        def pending_deletions(self):
            return []

    class Store:
        def __init__(self):
            self.rows = {}

        def upsert(self, table, rows):
            self.rows.setdefault(table, []).extend(rows)

    repository = Repository()
    store = Store()
    valuation_date = date(2026, 9, 25)
    pipeline = PrivatePipeline(
        repository,
        store,
        lambda symbols, when: {"2330": (Decimal("12"), when)},
        valuation_date_resolver=lambda: valuation_date,
    )

    assert pipeline.run() == 7
    assert repository.advanced == []
    position = store.rows["mart_user_positions"][0]
    assert position["valuation_date"] == "2026-09-25"
    assert position["stock_name"] == "台積電"
    assert position["market_value"] == Decimal("12")
    assert position["price_status"] == "available"


def test_repository_enumerates_only_bounded_users_with_ledger_history_for_scheduled_revaluation():
    class Rows:
        def fetchall(self):
            return [{"user_id": USER}]

    class Connection:
        def execute(self, sql, values):
            assert "SELECT DISTINCT user_id" in sql
            assert "FROM private.ledger_events" in sql
            assert values == (123,)
            return Rows()

    repository = object.__new__(PostgresWorkspaceRepository)

    @contextmanager
    def connection():
        yield Connection()

    repository._connection = connection
    assert repository.portfolio_user_ids_for_pipeline(123) == [USER]
