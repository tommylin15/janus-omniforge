from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from services.api import private_pipeline_runtime
from services.api.private_pipeline import PrivatePipeline
from services.api.repository import PostgresWorkspaceRepository


USER = UUID("00000000-0000-0000-0000-000000000001")


def test_offlist_retirement_preserves_history_and_records_demand():
    class Rows:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.rows[0]

    class Connection:
        def __init__(self):
            self.calls = []

        def execute(self, sql, values=()):
            self.calls.append((sql, values))
            if "UPDATE private.watchlist w" in sql:
                assert "NOT EXISTS" in sql and "liquid_500_members" in sql
                assert "active=false" in sql and "version=version+1" in sql
                return Rows([{"user_id": USER, "symbol": "5876"}])
            if "UPDATE private.users" in sql:
                return Rows([{"change_version": 9}])
            return Rows([])

    repository = object.__new__(PostgresWorkspaceRepository)
    connection_object = Connection()

    @contextmanager
    def connection():
        yield connection_object

    repository._connection = connection
    assert repository.retire_offlist_watchlist(USER) == 1
    assert any("INSERT INTO private.change_log" in sql for sql, _ in connection_object.calls)
    assert any("record_deep_tracking_demand" in sql and values == ("5876",)
               for sql, values in connection_object.calls)
    assert all("ledger_events" not in sql for sql, _ in connection_object.calls)


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


def test_private_pipeline_runtime_retires_offlist_before_processing(monkeypatch, capsys):
    class MarketStub:
        memberships = object()

        def latest_valuation_date(self, day):
            return day

    class RepositoryStub:
        def retire_offlist_watchlist(self):
            return 1

    class PipelineStub:
        def __init__(self, repository, *_args):
            assert isinstance(repository, RepositoryStub)

        def run(self, *_args):
            return 42

    monkeypatch.setattr(private_pipeline_runtime, "load_postgres_bundle", lambda *_args: None)
    monkeypatch.setattr(private_pipeline_runtime, "repository_from_env", RepositoryStub)
    monkeypatch.setattr(private_pipeline_runtime.CorePriceReader, "from_env", classmethod(lambda _cls: MarketStub()))
    monkeypatch.setattr(private_pipeline_runtime.PrivateIcebergStore, "from_env", classmethod(lambda _cls: object()))
    monkeypatch.setattr(private_pipeline_runtime, "PrivatePipeline", PipelineStub)

    private_pipeline_runtime.main()

    assert "checkpoint=42 offlist_watchlist_retired=1" in capsys.readouterr().out


def test_private_pipeline_job_uses_coverage_runtime_entrypoint():
    cloudbuild = (Path(__file__).parents[1] / "cloudbuild.yaml").read_text(encoding="utf-8")
    private_branch = cloudbuild.split('if [[ "${_RUNTIME_NAME}" == "janus-private-pipeline" ]]', 1)[1]
    private_branch = private_branch.split("        fi", 1)[0]
    assert '--command="python"' in private_branch
    assert '--args="-m,services.api.private_pipeline_runtime"' in private_branch
