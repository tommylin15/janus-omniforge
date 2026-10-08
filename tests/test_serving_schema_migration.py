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


def test_quotes_profile_migration_records_version_after_acl_checks():
    control = FakeControl()
    migration.run(control, migration.MIGRATION_QUOTES_BROKER)
    sql = statements(control.connection)
    assert sql.index('has_table_privilege') < sql.index('INSERT INTO control.schema_migrations')
    assert 'GRANT SELECT, INSERT ON private.broker_profile_revisions TO janus_private_api' in sql
    assert 'GRANT SELECT, DELETE ON private.broker_profile_revisions TO janus_private_pipeline' in sql
    assert 'CREATE ON SCHEMA' not in sql


def test_quotes_profile_migration_failed_acceptance_does_not_record_version():
    control = FakeControl()
    class Cursor(FakeCursor):
        def fetchone(self):
            return (False,) if 'has_table_privilege' in self._last else super().fetchone()
    control.connection.cursor = lambda: Cursor('janus_control')
    with pytest.raises(migration.ServingSchemaMigrationError):
        migration.run(control, migration.MIGRATION_QUOTES_BROKER)


def test_operations_read_acl_uses_existing_owners_and_records_only_after_acceptance(monkeypatch):
    control = FakeControl()
    publication = FakeConnection('janus_publication')
    monkeypatch.setattr(migration, '_publication_connection', lambda: publication)
    migration.run(control, migration.MIGRATION_OPERATIONS)
    sql = statements(control.connection)
    assert sql.index('has_table_privilege') < sql.index('INSERT INTO control.schema_migrations')
    assert 'GRANT SELECT ON control.batch_occurrences TO janus_web_control' in sql
    assert 'GRANT SELECT ON publication.stock_latest TO janus_private_api' in statements(publication)
    assert publication.closed


def test_private_operations_migration_exposes_only_aggregate_status():
    control = FakeControl()
    migration.run(control, migration.MIGRATION_PRIVATE_OPERATIONS)
    sql = statements(control.connection)
    assert "CREATE TABLE IF NOT EXISTS control.private_pipeline_status" in sql
    assert "GRANT SELECT ON control.private_pipeline_status TO janus_web_control" in sql
    assert "GRANT SELECT, INSERT, UPDATE ON control.private_pipeline_status TO janus_private_pipeline" in sql
    assert "user_id" not in sql
    assert sql.index("has_table_privilege") < sql.index("INSERT INTO control.schema_migrations")
    assert "045_private_pipeline_operations" in sql


def test_twse_only_latest_price_migration_retires_tpex_without_deleting_history():
    control = FakeControl()
    migration.run(control, migration.MIGRATION_TWSE_LATEST_PRICE)
    sql = statements(control.connection)
    assert "source_ids - 'tpex' - 'tpex-benchmark'" in sql
    assert "SET enabled=false, collection_enabled=false, analysis_enabled=false" in sql
    assert "UPDATE control.stock_master" in sql
    assert "WHERE market='TPEX' AND enabled" in sql
    assert "DELETE FROM" not in sql
    assert sql.index("NOT EXISTS") < sql.index("INSERT INTO control.schema_migrations")
    assert "046_twse_only_latest_price" in sql


def test_private_recalculation_queue_migration_is_bounded_and_owner_scoped():
    control = FakeControl()
    migration.run(control, migration.MIGRATION_PRIVATE_RECALC)
    sql = statements(control.connection)
    assert "CREATE TABLE IF NOT EXISTS private.recalculation_requests" in sql
    assert "recalculation_one_active_owner_idx" in sql
    assert "CANCEL_REQUESTED" in sql
    assert "private_recalc_workers" in sql
    assert "BETWEEN 2 AND 8" in sql
    assert "GRANT SELECT, INSERT, UPDATE ON private.recalculation_requests TO janus_private_api" in sql
    assert "GRANT SELECT, UPDATE ON private.recalculation_requests TO janus_private_pipeline" in sql
    assert sql.index("has_table_privilege") < sql.index("INSERT INTO control.schema_migrations")
    assert "048_private_recalculation_queue" in sql


def test_latest_price_route_v2_migration_extends_operational_quote_constraint():
    control = FakeControl()
    migration.run(control, migration.MIGRATION_LATEST_PRICE_ROUTE_V2)
    sql = statements(control.connection)
    assert "operational_last_quotes_route_version_check" in sql
    assert "'quote-router.v1','latest-price.v2'" in sql
    assert "047_latest_price_route_v2" in sql
    assert sql.index("pg_get_constraintdef") < sql.index("INSERT INTO control.schema_migrations")


def test_batch_occurrence_skipped_status_migration_expands_constraint():
    control = FakeControl()
    migration.run(control, migration.MIGRATION_BATCH_OCCURRENCE_SKIPPED)
    sql = statements(control.connection)
    assert "batch_occurrences_status_check" in sql
    assert "'skipped'" in sql
    assert "049_batch_occurrence_skipped_status" in sql
    assert sql.index("pg_get_constraintdef") < sql.index("INSERT INTO control.schema_migrations")


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


def test_publication_connection_uses_publication_owner_credential(monkeypatch):
    import psycopg
    from packages import postgres_bundle

    captured: dict[str, object] = {}
    marker = object()

    def load_bundle(env_name, fields):
        captured["env_name"] = env_name
        captured["fields"] = fields
        monkeypatch.setenv("SERVING_PUBLICATION_PASSWORD", "owner-password")

    def connect(**kwargs):
        captured["connect"] = kwargs
        return marker

    monkeypatch.setattr(postgres_bundle, "load_postgres_bundle", load_bundle)
    monkeypatch.setattr(psycopg, "connect", connect)
    monkeypatch.setenv("CONTROL_DB_HOST", "10.0.0.2")
    monkeypatch.setenv("CONTROL_DB_NAME", "janus_control")
    monkeypatch.delenv("SERVING_PUBLICATION_PASSWORD", raising=False)

    assert migration._publication_connection() is marker
    assert captured["env_name"] == "JANUS_INGESTION_POSTGRES_BUNDLE"
    assert captured["fields"] == {"SERVING_PUBLICATION_PASSWORD": "publication_password"}
    connect_args = captured["connect"]
    assert isinstance(connect_args, dict)
    assert connect_args["user"] == "janus_publication"
    assert connect_args["password"] == "owner-password"


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
    assert "has_table_privilege('janus_public_api','publication.stock_serving_recent','SELECT')" in publication_sql
    assert "has_table_privilege('janus_public_api','publication.stock_serving_recent','SELECT')" not in control_sql
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



def test_holdings_reference_migration_uses_publication_owner_and_validates_acl(monkeypatch):
    control = FakeControl()
    publication = FakeConnection("janus_publication")
    monkeypatch.setattr(migration, "_publication_connection", lambda: publication)
    migration.run(control, migration.MIGRATION_HOLDINGS_PREVIOUS_CLOSE)
    control_sql = statements(control.connection)
    publication_sql = statements(publication)
    assert "GRANT USAGE ON SCHEMA publication TO janus_private_api" in publication_sql
    assert "GRANT SELECT ON publication.stock_serving_recent TO janus_private_api" in publication_sql
    assert "GRANT USAGE ON SCHEMA publication TO janus_private_api" not in control_sql
    assert "NOT has_table_privilege('janus_public_api','private.current_positions','SELECT')" in control_sql
    assert "has_schema_privilege('janus_private_api','publication','USAGE')" in publication_sql
    assert "has_schema_privilege('janus_private_api','publication','USAGE')" not in control_sql
    assert control_sql.index("has_table_privilege") < control_sql.index("INSERT INTO control.schema_migrations")
    assert publication.closed is True


def test_cicd_readiness_skips_completed_and_applies_only_missing_in_order(monkeypatch):
    monkeypatch.setattr(migration, '_publication_connection', lambda: FakeConnection('janus_publication'))
    markers = set(migration.SUPPORTED) - {migration.MIGRATION_HOLDINGS_PREVIOUS_CLOSE}
    applied = []
    class Cursor(FakeCursor):
        def fetchall(self):
            return [(name,) for name in sorted(markers)]
    control = FakeControl()
    control.connection.cursor = lambda: Cursor('janus_control')
    def apply(control, name):
        applied.append(name)
        markers.add(name)
    monkeypatch.setattr(migration, 'run', apply)
    with pytest.raises(RuntimeError, match='markers missing'):
        migration.cicd_readiness(control)
    assert not applied
    result = migration.cicd_readiness(control, apply_missing=True)
    assert applied == [migration.MIGRATION_HOLDINGS_PREVIOUS_CLOSE]
    assert result['applied'] == applied
    assert migration.MIGRATION_HOLDINGS_PREVIOUS_CLOSE not in result['skipped']
    assert migration.cicd_readiness(control)['applied'] == []


def test_cicd_migration_failure_stops_next_migration(monkeypatch):
    missing = sorted(migration.SUPPORTED)[-2:]
    class Cursor(FakeCursor):
        def fetchall(self):
            return [(name,) for name in migration.SUPPORTED if name not in missing]
    control = FakeControl()
    control.connection.cursor = lambda: Cursor('janus_control')
    attempts = []
    def fail(control, name):
        attempts.append(name)
        raise RuntimeError('migration failed')
    monkeypatch.setattr(migration, 'run', fail)
    with pytest.raises(RuntimeError, match='migration failed'):
        migration.cicd_readiness(control, apply_missing=True)
    assert attempts == missing[:1]


def test_holdings_acl_fetches_select_result_in_separate_statement(monkeypatch):
    class Cursor(FakeCursor):
        def fetchone(self):
            if not self._last.lstrip().startswith('SELECT'):
                raise RuntimeError('first result has no rows')
            return super().fetchone()
    publication = FakeConnection('janus_publication')
    publication.cursor = lambda: Cursor('janus_publication')
    monkeypatch.setattr(migration, '_publication_connection', lambda: publication)
    migration.run(FakeControl(), migration.MIGRATION_HOLDINGS_PREVIOUS_CLOSE)
