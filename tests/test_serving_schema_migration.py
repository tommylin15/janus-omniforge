from __future__ import annotations

from contextlib import nullcontext

from ingestion_core import serving_schema_migration as migration


class FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self._row = (True, True, True, True, True, True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        assert params is None
        self.statements.append(str(sql))

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self) -> None:
        self.cursors: list[FakeCursor] = []
        self.closed = False

    def transaction(self):
        return nullcontext()

    def cursor(self):
        cursor = FakeCursor()
        self.cursors.append(cursor)
        return cursor

    def close(self):
        self.closed = True


class FakeControl:
    def __init__(self) -> None:
        self.connection = FakeConnection()


def statements(connection: FakeConnection) -> str:
    return "\n".join(statement for cursor in connection.cursors for statement in cursor.statements)


def test_position_projection_uses_canonical_migration_and_acceptance():
    control = FakeControl()
    migration.run(control, migration.MIGRATION_POSITION)
    sql = statements(control.connection)
    assert "CREATE TABLE IF NOT EXISTS private.current_positions" in sql
    assert "CREATE CONSTRAINT TRIGGER ledger_refresh_current_positions" in sql
    assert "041_operational_position_projection" in sql
    assert "operational position" not in sql.lower() or "current_positions" in sql


def test_stock_serving_splits_control_and_publication_owners(monkeypatch):
    control = FakeControl()
    publication = FakeConnection()
    monkeypatch.setattr(migration, "_publication_connection", lambda: publication)

    migration.run(control, migration.MIGRATION_STOCK_SERVING)

    control_sql = statements(control.connection)
    publication_sql = statements(publication)
    assert "CREATE TABLE IF NOT EXISTS control.stock_serving_recent" in control_sql
    assert "GRANT SELECT ON control.stock_serving_recent TO janus_publication" in control_sql
    assert "CREATE OR REPLACE VIEW publication.stock_serving_recent" in publication_sql
    assert "GRANT SELECT ON publication.stock_serving_recent, publication.stock_latest TO janus_public_api" in publication_sql
    assert "042_stock_serving_projection" in control_sql
    assert publication.closed is True


def test_psql_cleaner_removes_meta_transaction_lines():
    cleaned = migration._clean_psql_sql("\\set ON_ERROR_STOP on\nBEGIN;\nSELECT 1;\nCOMMIT;\n")
    assert cleaned == "SELECT 1;"
