"""Allow-listed serving-schema migrations through the existing dev PostgreSQL path.

Migration 048 is carried by this runtime so the controller deploy must precede applying it.

This avoids coupling database migrations to Compute Engine SSH/IAP. Canonical
SQL remains the source of truth, while this module executes explicit owner
phases with the already-approved janus_control, janus_private_api, and
janus_publication identities.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


MIGRATION_POSITION = "041_operational_position_projection"
MIGRATION_STOCK_SERVING = "042_stock_serving_projection"
MIGRATION_OPERATIONS = "043_admin_batch_read"
MIGRATION_QUOTES_BROKER = "044_quotes_broker_profile"
MIGRATION_PRIVATE_OPERATIONS = "045_private_pipeline_operations"
MIGRATION_TWSE_LATEST_PRICE = "046_twse_only_latest_price"
MIGRATION_LATEST_PRICE_ROUTE_V2 = "047_latest_price_route_v2"
MIGRATION_PRIVATE_RECALC = "048_private_recalculation_queue"
MIGRATION_BATCH_OCCURRENCE_SKIPPED = "049_batch_occurrence_skipped_status"
MIGRATION_HOLDINGS_PREVIOUS_CLOSE = "050_holdings_previous_close_read"
SUPPORTED = frozenset({
    MIGRATION_POSITION,
    MIGRATION_STOCK_SERVING,
    MIGRATION_OPERATIONS,
    MIGRATION_QUOTES_BROKER,
    MIGRATION_PRIVATE_OPERATIONS,
    MIGRATION_TWSE_LATEST_PRICE,
    MIGRATION_LATEST_PRICE_ROUTE_V2,
    MIGRATION_PRIVATE_RECALC,
    MIGRATION_BATCH_OCCURRENCE_SKIPPED,
    MIGRATION_HOLDINGS_PREVIOUS_CLOSE,
})


class ServingSchemaMigrationError(RuntimeError):
    """Safe stage metadata for migration failures without exception details."""

    def __init__(self, stage: str, error: Exception) -> None:
        self.stage = stage
        self.error_code = type(error).__name__.upper()[:64]
        sqlstate = getattr(error, "sqlstate", None)
        self.sqlstate = str(sqlstate)[:16] if sqlstate else None
        super().__init__(f"serving schema migration failed at {stage}")


def _migration_path(name: str) -> Path:
    if name not in SUPPORTED:
        raise ValueError("unsupported serving schema migration")
    return Path(__file__).resolve().parents[3] / "infra/postgres/migrations" / f"{name}.sql"


def _clean_psql_sql(text: str) -> str:
    """Remove psql-only/meta transaction lines; callers own the transaction."""
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("\\") and line.strip() not in {"BEGIN;", "COMMIT;"}
    ).strip()


def _without_role_lines(text: str) -> str:
    """Connections already use the bounded owner identity for each phase."""
    cleaned = _clean_psql_sql(text)
    return "\n".join(
        line for line in cleaned.splitlines()
        if not line.strip().startswith("SET ROLE ") and line.strip() != "RESET ROLE;"
    ).strip()


def _private_api_connection() -> Any:
    from packages.postgres_bundle import load_postgres_bundle
    import psycopg

    load_postgres_bundle(
        "JANUS_INGESTION_POSTGRES_BUNDLE",
        {"SERVING_PRIVATE_DATABASE_URL": "database_url"},
    )
    dsn = os.environ.get("SERVING_PRIVATE_DATABASE_URL", "").strip()
    if not dsn:
        raise ValueError("missing serving private API database URL")
    return psycopg.connect(
        dsn,
        connect_timeout=5,
        options="-c statement_timeout=60000 -c idle_in_transaction_session_timeout=15000",
    )


def _publication_connection() -> Any:
    from packages.postgres_bundle import load_postgres_bundle
    import psycopg

    load_postgres_bundle(
        "JANUS_INGESTION_POSTGRES_BUNDLE",
        {"SERVING_PUBLICATION_PASSWORD": "publication_password"},
    )
    required = ("CONTROL_DB_HOST", "CONTROL_DB_NAME", "SERVING_PUBLICATION_PASSWORD")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise ValueError(f"missing serving publication database settings: {','.join(missing)}")
    return psycopg.connect(
        host=os.environ["CONTROL_DB_HOST"],
        dbname=os.environ["CONTROL_DB_NAME"],
        user="janus_publication",
        password=os.environ["SERVING_PUBLICATION_PASSWORD"],
        sslmode=os.environ.get("CONTROL_DB_SSLMODE", "require"),
        connect_timeout=5,
        options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=15000",
    )


def _require_current_user(cursor: Any, expected: str) -> None:
    cursor.execute("SELECT current_user")
    row = cursor.fetchone()
    if row is None or str(row[0]) != expected:
        actual = "unknown" if row is None else str(row[0])
        raise RuntimeError(f"serving migration expected database identity {expected}, got {actual}")


def _verify_position_schema(cursor: Any) -> None:
    cursor.execute(
        """SELECT
          EXISTS (SELECT 1 FROM control.schema_migrations
                  WHERE version='041_operational_position_projection'),
          to_regclass('private.current_positions') IS NOT NULL,
          to_regprocedure('private.refresh_current_positions(uuid)') IS NOT NULL,
          has_table_privilege('janus_private_api','private.current_positions','SELECT'),
          has_table_privilege('janus_private_api','private.current_positions','INSERT'),
          has_table_privilege('janus_private_api','private.current_positions','UPDATE'),
          has_table_privilege('janus_private_api','private.current_positions','DELETE'),
          has_table_privilege('janus_private_pipeline','private.current_positions','SELECT'),
          has_table_privilege('janus_private_pipeline','private.current_positions','DELETE'),
          NOT has_schema_privilege('janus_private_api','private','CREATE'),
          COALESCE((
            SELECT pg_get_userbyid(p.proowner)='janus_private_api'
              FROM pg_proc p
             WHERE p.oid=to_regprocedure('private.refresh_current_positions(uuid)')
          ), false)"""
    )
    row = cursor.fetchone()
    if row is None or not all(bool(value) for value in row):
        raise RuntimeError("operational position projection schema acceptance failed")


def _verify_position_data(cursor: Any) -> None:
    cursor.execute(
        """SELECT
          current_user='janus_private_api',
          NOT EXISTS (
            SELECT 1
              FROM private.current_positions p
              LEFT JOIN private.users u USING(user_id)
             WHERE u.user_id IS NULL
          ),
          NOT EXISTS (
            SELECT 1
              FROM private.current_positions p
              JOIN private.users u USING(user_id)
             WHERE p.ledger_version <> u.ledger_version
          ),
          NOT EXISTS (
            SELECT 1 FROM private.current_positions
             WHERE shares <= 0 OR cost_basis < 0 OR average_cost < 0
          )"""
    )
    row = cursor.fetchone()
    if row is None or not all(bool(value) for value in row):
        raise RuntimeError("operational position projection data acceptance failed")


def _apply_position(control: Any) -> None:
    text = _migration_path(MIGRATION_POSITION).read_text(encoding="utf-8")
    try:
        _, remainder = text.split("-- PHASE: control-prepare", 1)
        control_prepare, remainder = remainder.split("-- PHASE: private-api", 1)
        private_part, control_finalize = remainder.split("-- PHASE: control-finalize", 1)
    except ValueError as error:
        raise RuntimeError("041 migration owner phases are not recognizable") from error

    # Phase 1 commits the rebuildable table/ACL and a temporary CREATE grant so
    # janus_private_api can own the ledger replay function without superuser.
    with control.connection.transaction(), control.connection.cursor() as cursor:
        _require_current_user(cursor, "janus_control")
        cursor.execute(_without_role_lines(control_prepare))

    private = _private_api_connection()
    private_ok = False
    try:
        with private.transaction(), private.cursor() as cursor:
            _require_current_user(cursor, "janus_private_api")
            cursor.execute(_without_role_lines(private_part))
            _verify_position_data(cursor)
        private_ok = True
    finally:
        private.close()
        # Never leave runtime CREATE permission behind, even if replay/backfill
        # fails. The table is rebuildable and no migration version is recorded
        # until all owner phases have passed.
        with control.connection.transaction(), control.connection.cursor() as cursor:
            _require_current_user(cursor, "janus_control")
            cursor.execute("REVOKE CREATE ON SCHEMA private FROM janus_private_api")

    if not private_ok:
        raise RuntimeError("operational position private phase failed")

    # Phase 3 records the migration only after the private replay committed.
    finalize_sql = _without_role_lines(control_finalize)
    finalize_sql = finalize_sql.replace(
        "REVOKE CREATE ON SCHEMA private FROM janus_private_api;", ""
    ).strip()
    with control.connection.transaction(), control.connection.cursor() as cursor:
        _require_current_user(cursor, "janus_control")
        cursor.execute(finalize_sql)
        _verify_position_schema(cursor)


def _apply_stock_serving(control: Any) -> None:
    text = _migration_path(MIGRATION_STOCK_SERVING).read_text(encoding="utf-8")
    try:
        control_part, remainder = text.split("SET ROLE janus_publication;", 1)
        view_part, remainder = remainder.split("RESET ROLE;", 1)
        publication_acl_part, migration_record = remainder.split(
            "INSERT INTO control.schema_migrations", 1
        )
    except ValueError as error:
        raise RuntimeError("042 migration owner phases are not recognizable") from error

    # Phase 1: janus_control owns the serving table and grants bounded read access
    # to janus_publication. Commit before the publication owner creates views.
    try:
        with control.connection.transaction(), control.connection.cursor() as cursor:
            _require_current_user(cursor, "janus_control")
            cursor.execute(_without_role_lines(control_part))
    except Exception as error:
        raise ServingSchemaMigrationError("control_prepare", error) from error

    try:
        publication = _publication_connection()
    except Exception as error:
        raise ServingSchemaMigrationError("publication_connect", error) from error

    try:
        try:
            with publication.transaction(), publication.cursor() as cursor:
                _require_current_user(cursor, "janus_publication")
                cursor.execute(_without_role_lines(view_part + "\n" + publication_acl_part))
                cursor.execute(
                    """SELECT
                      to_regclass('publication.stock_serving_recent') IS NOT NULL,
                      to_regclass('publication.stock_latest') IS NOT NULL,
                      has_table_privilege('janus_public_api','publication.stock_serving_recent','SELECT'),
                      has_table_privilege('janus_public_api','publication.stock_latest','SELECT')"""
                )
                row = cursor.fetchone()
                if row is None or not all(bool(value) for value in row):
                    raise RuntimeError("stock serving publication view acceptance failed")
        except Exception as error:
            raise ServingSchemaMigrationError("publication_apply", error) from error
    finally:
        publication.close()

    # Record the migration only after both owner phases are committed. Publication
    # ACL acceptance is already verified under janus_publication above, so this
    # final janus_control phase stays within the control schema boundary.
    try:
        with control.connection.transaction(), control.connection.cursor() as cursor:
            _require_current_user(cursor, "janus_control")
            cursor.execute(_clean_psql_sql(
                "INSERT INTO control.schema_migrations" + migration_record
            ))
            cursor.execute(
                """SELECT
                  EXISTS (SELECT 1 FROM control.schema_migrations
                          WHERE version='042_stock_serving_projection'),
                  to_regclass('control.stock_serving_recent') IS NOT NULL,
                  has_table_privilege('janus_publication','control.stock_serving_recent','SELECT')"""
            )
            row = cursor.fetchone()
            if row is None or not all(bool(value) for value in row):
                raise RuntimeError("stock serving projection acceptance failed")
    except Exception as error:
        raise ServingSchemaMigrationError("control_finalize", error) from error


def _apply_operations(control: Any) -> None:
    try:
        text = _clean_psql_sql(_migration_path(MIGRATION_OPERATIONS).read_text(encoding='utf-8'))
        prepare, rest = text.split('-- PHASE: publication-apply', 1)
        publication_sql, finalize = rest.split('-- PHASE: control-finalize', 1)
        with control.connection.transaction(), control.connection.cursor() as cursor:
            _require_current_user(cursor, 'janus_control')
            cursor.execute(prepare)
        publication = _publication_connection()
        try:
            with publication.transaction(), publication.cursor() as cursor:
                _require_current_user(cursor, 'janus_publication')
                cursor.execute(publication_sql)
                cursor.execute("SELECT has_table_privilege('janus_private_api','publication.stock_latest','SELECT')")
                if not cursor.fetchone()[0]:
                    raise RuntimeError('watchlist projection read permission is unavailable')
        finally:
            publication.close()
        with control.connection.transaction(), control.connection.cursor() as cursor:
            _require_current_user(cursor, 'janus_control')
            cursor.execute("SELECT has_table_privilege('janus_web_control','control.batch_occurrences','SELECT')")
            if not cursor.fetchone()[0]:
                raise RuntimeError('Admin batch read permission is unavailable')
            cursor.execute(finalize)
    except Exception as error:
        raise ServingSchemaMigrationError("operations_apply", error) from error

def _apply_holdings_previous_close(control: Any) -> None:
    """Grant market-reference SELECT via publication owner; no owner position exposure."""
    text = _migration_path(MIGRATION_HOLDINGS_PREVIOUS_CLOSE).read_text(encoding="utf-8")
    try:
        prepare, rest = text.split("-- PHASE: publication-apply", 1)
        publication_sql, finalize = rest.split("-- PHASE: control-finalize", 1)
        checks, record = finalize.split("INSERT INTO control.schema_migrations", 1)
        with control.connection.transaction(), control.connection.cursor() as cursor:
            _require_current_user(cursor, "janus_control")
            cursor.execute(_without_role_lines(prepare))

        publication = _publication_connection()
        try:
            with publication.transaction(), publication.cursor() as cursor:
                _require_current_user(cursor, "janus_publication")
                cursor.execute(_without_role_lines(publication_sql))
                cursor.execute(
                    "SELECT has_table_privilege('janus_private_api',"
                    "'publication.stock_serving_recent','SELECT')"
                )
                if not cursor.fetchone()[0]:
                    raise RuntimeError("holdings reference view read access unavailable")
        finally:
            publication.close()

        with control.connection.transaction(), control.connection.cursor() as cursor:
            _require_current_user(cursor, "janus_control")
            cursor.execute(_without_role_lines(checks))
            row = cursor.fetchone()
            if row is None or not all(bool(value) for value in row):
                raise RuntimeError("holdings reference permission acceptance failed")
            cursor.execute("INSERT INTO control.schema_migrations" + _without_role_lines(record))
    except Exception as error:
        raise ServingSchemaMigrationError("holdings_reference_apply", error) from error


def run(control: Any, name: str) -> None:
    """Apply one allow-listed serving migration using existing DB identities."""
    if name == MIGRATION_QUOTES_BROKER:
        try:
            text = _without_role_lines(_migration_path(name).read_text(encoding='utf-8'))
            prepare, acceptance = text.split('-- PHASE: acceptance', 1)
            checks, record = acceptance.split('INSERT INTO control.schema_migrations', 1)
            with control.connection.transaction(), control.connection.cursor() as cursor:
                _require_current_user(cursor, 'janus_control')
                cursor.execute(prepare)
                cursor.execute(checks)
                row = cursor.fetchone()
                if row is None or not all(bool(value) for value in row):
                    raise RuntimeError('quotes/profile schema acceptance failed')
                cursor.execute('INSERT INTO control.schema_migrations' + record)
        except Exception as error:
            raise ServingSchemaMigrationError('quotes_broker_apply', error) from error
    elif name == MIGRATION_HOLDINGS_PREVIOUS_CLOSE:
        _apply_holdings_previous_close(control)
    elif name == MIGRATION_POSITION:
        _apply_position(control)
    elif name == MIGRATION_STOCK_SERVING:
        _apply_stock_serving(control)
    elif name == MIGRATION_OPERATIONS:
        _apply_operations(control)
    elif name == MIGRATION_PRIVATE_OPERATIONS:
        try:
            text = _without_role_lines(_migration_path(name).read_text(encoding="utf-8"))
            prepare, acceptance = text.split("-- PHASE: acceptance", 1)
            checks, record = acceptance.split("INSERT INTO control.schema_migrations", 1)
            with control.connection.transaction(), control.connection.cursor() as cursor:
                _require_current_user(cursor, "janus_control")
                cursor.execute(prepare)
                cursor.execute(checks)
                row = cursor.fetchone()
                if row is None or not all(bool(value) for value in row):
                    raise RuntimeError("private operations aggregate schema acceptance failed")
                cursor.execute("INSERT INTO control.schema_migrations" + record)
        except Exception as error:
            raise ServingSchemaMigrationError("private_operations_apply", error) from error
    elif name == MIGRATION_TWSE_LATEST_PRICE:
        try:
            text = _without_role_lines(_migration_path(name).read_text(encoding="utf-8"))
            prepare, acceptance = text.split("-- PHASE: acceptance", 1)
            checks, record = acceptance.split("INSERT INTO control.schema_migrations", 1)
            with control.connection.transaction(), control.connection.cursor() as cursor:
                _require_current_user(cursor, "janus_control")
                cursor.execute(prepare)
                cursor.execute(checks)
                row = cursor.fetchone()
                if row is None or not all(bool(value) for value in row):
                    raise RuntimeError("TWSE-only latest-price scope acceptance failed")
                cursor.execute("INSERT INTO control.schema_migrations" + record)
        except Exception as error:
            raise ServingSchemaMigrationError("twse_latest_price_apply", error) from error
    elif name == MIGRATION_PRIVATE_RECALC:
        try:
            text = _without_role_lines(_migration_path(name).read_text(encoding="utf-8"))
            prepare, acceptance = text.split("-- PHASE: acceptance", 1)
            checks, record = acceptance.split("INSERT INTO control.schema_migrations", 1)
            with control.connection.transaction(), control.connection.cursor() as cursor:
                _require_current_user(cursor, "janus_control")
                cursor.execute(prepare)
                cursor.execute(checks)
                row = cursor.fetchone()
                if row is None or not all(bool(value) for value in row):
                    raise RuntimeError("private recalculation queue schema acceptance failed")
                cursor.execute("INSERT INTO control.schema_migrations" + record)
        except Exception as error:
            raise ServingSchemaMigrationError("private_recalculation_queue_apply", error) from error
    elif name == MIGRATION_LATEST_PRICE_ROUTE_V2:
        try:
            text = _without_role_lines(_migration_path(name).read_text(encoding="utf-8"))
            prepare, acceptance = text.split("-- PHASE: acceptance", 1)
            checks, record = acceptance.split("INSERT INTO control.schema_migrations", 1)
            with control.connection.transaction(), control.connection.cursor() as cursor:
                _require_current_user(cursor, "janus_control")
                cursor.execute(prepare)
                cursor.execute(checks)
                row = cursor.fetchone()
                if row is None or not all(bool(value) for value in row):
                    raise RuntimeError("latest-price route-v2 schema acceptance failed")
                cursor.execute("INSERT INTO control.schema_migrations" + record)
        except Exception as error:
            raise ServingSchemaMigrationError("latest_price_route_v2_apply", error) from error
    elif name == MIGRATION_BATCH_OCCURRENCE_SKIPPED:
        try:
            text = _without_role_lines(_migration_path(name).read_text(encoding="utf-8"))
            prepare, acceptance = text.split("-- PHASE: acceptance", 1)
            checks, record = acceptance.split("INSERT INTO control.schema_migrations", 1)
            with control.connection.transaction(), control.connection.cursor() as cursor:
                _require_current_user(cursor, "janus_control")
                cursor.execute(prepare)
                cursor.execute(checks)
                row = cursor.fetchone()
                if row is None or not all(bool(value) for value in row):
                    raise RuntimeError("batch occurrence skipped-status schema acceptance failed")
                cursor.execute("INSERT INTO control.schema_migrations" + record)
        except Exception as error:
            raise ServingSchemaMigrationError("batch_occurrence_status_apply", error) from error
    else:
        raise ValueError("unsupported serving schema migration")
