from __future__ import annotations

from contextlib import nullcontext

import pytest

from ingestion_core import serving_schema_migration as migration


class FakeCursor:
    def __init__(self, identity: str) -> None:
        self.identity = identity
        self.statements: list[str] = []
        self._last = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        assert params is None
        self._last = str(sql)
        self.statements.append(self._last)

    def fetchone(self):
        if self._last.strip() == "SELECT current_user":
            return (self.identity,)
        # Acceptance queries only contain boolean expressions in these tests.
        return tuple(True for _ in range(12))


class FakeConnection:
    def __init__(self, identity: str) -> None:
        self.identity = identity
        self.cursors: list[FakeCursor] = []
        self.closed = False

    def transaction(self):
        return nullcontext()

    def cursor(self):
        cursor = FakeCursor(self.identity)
        self.cursors.append(cursor)
        return cursor

    def close(self):
        self.closed = True


class FakeControl:
    def __init__(self) -> None:
        self.connection = FakeConnection("janus_control")


class FakeOperationalError(RuntimeError):
    sqlstate = "08001"


def statements(connection: FakeConnection) -> str:
    return "\n".join(statement for cursor in connection.cursors for statement in cursor.statements)


def test_position_projection_splits_control_and_private_api_owners(monkeypatch):
    control = FakeControl()
    private = FakeConnection("janus_private_api")
    monkeypatch.setattr(migration, "_private_api_connection", lambda: private)

    migration.run(control, migration.MIGRATION_POSITION)

    control_sql = statements(control.connection)
    private_sql = statements(private)
    assert "CREATE TABLE IF NOT EXISTS private.current_positions" in control_sql
    assert "GRANT CREATE ON SCHEMA private TO janus_private_api" in control_sql
    assert "REVOKE CREATE ON SCHEMA private FROM janus_private_api" in control_sql
    assert "CREATE OR REPLACE FUNCTION private.refresh_current_positions" in private_sql
    assert "SECURITY DEFINER" not in private_sql
    assert "041_operational_position_projection" in control_sql
    assert private.closed is True


def test_position_projection_revokes_temporary_create_when_private_phase_fails(monkeypatch):
    control = FakeControl()

    class BrokenCursor(FakeCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "CREATE OR REPLACE FUNCTION private.refresh_current_positions" in str(sql):
                raise RuntimeError("private replay failed")

    class BrokenConnection(FakeConnection):
        def cursor(self):
            cursor = BrokenCursor(self.identity)
            self.cursors.append(cursor)
            return cursor

    private = BrokenConnection("janus_private_api")
    monkeypatch.setattr(migration, "_private_api_connection", lambda: private)

    try:
        migration.run(control, migration.MIGRATION_POSITION)
    except RuntimeError as error:
        assert str(error) == "private replay failed"
    else:
        raise AssertionError("private migration failure was swallowed")

    control_sql = statements(control.connection)
    assert "REVOKE CREATE ON SCHEMA private FROM janus_private_api" in control_sql
    assert "041_operational_position_projection" not in control_sql


def test_stock_serving_splits_control_and_publication_owners(monkeypatch):
    control = FakeControl()
    publication = FakeConnection("janus_publication")
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


def test_stock_serving_reports_safe_publication_connection_failure(monkeypatch):
    control = FakeControl()

    def fail_publication_connection():
        raise FakeOperationalError("sensitive connection detail")

    monkeypatch.setattr(migration, "_publication_connection", fail_publication_connection)

    with pytest.raises(migration.ServingSchemaMigrationError) as raised:
        migration.run(control, migration.MIGRATION_STOCK_SERVING)

    error = raised.value
    assert error.stage == "publication_connect"
    assert error.error_code == "FAKEOPERATIONALERROR"
    assert error.sqlstate == "08001"
    assert "sensitive connection detail" not in str(error)
    assert "042_stock_serving_projection" not in statements(control.connection)


def test_psql_cleaner_removes_meta_transaction_lines():
    cleaned = migration._clean_psql_sql("\\set ON_ERROR_STOP on\nBEGIN;\nSELECT 1;\nCOMMIT;\n")
    assert cleaned == "SELECT 1;"


def test_role_cleaner_removes_set_and_reset_role_lines():
    cleaned = migration._without_role_lines("SET ROLE janus_control;\nSELECT 1;\nRESET ROLE;")
    assert cleaned == "SELECT 1;"
