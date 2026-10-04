"""Allow-listed serving-schema migrations through the existing dev PostgreSQL path.

This avoids coupling database migrations to Compute Engine SSH/IAP.  The
canonical SQL files remain the source of truth; this module only splits the
multi-owner 042 migration across the existing janus_control and
janus_publication database identities.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


MIGRATION_POSITION = "041_operational_position_projection"
MIGRATION_STOCK_SERVING = "042_stock_serving_projection"
SUPPORTED = frozenset({MIGRATION_POSITION, MIGRATION_STOCK_SERVING})


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


def _verify_position_projection(cursor: Any) -> None:
    cursor.execute(
        """SELECT
          EXISTS (SELECT 1 FROM control.schema_migrations
                  WHERE version='041_operational_position_projection'),
          to_regclass('private.current_positions') IS NOT NULL,
          has_table_privilege('janus_private_api','private.current_positions','SELECT'),
          has_table_privilege('janus_private_pipeline','private.current_positions','SELECT'),
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
        raise RuntimeError("operational position projection acceptance failed")


def _publication_connection() -> Any:
    from packages.postgres_bundle import load_postgres_bundle
    import psycopg

    load_postgres_bundle(
        "JANUS_INGESTION_POSTGRES_BUNDLE",
        {"SERVING_PUBLICATION_PASSWORD": ("mart_publication_password", "publication_password")},
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


def _apply_position(control: Any) -> None:
    sql = _clean_psql_sql(_migration_path(MIGRATION_POSITION).read_text(encoding="utf-8"))
    with control.connection.transaction(), control.connection.cursor() as cursor:
        cursor.execute(sql)
        _verify_position_projection(cursor)


def _apply_stock_serving(control: Any) -> None:
    text = _migration_path(MIGRATION_STOCK_SERVING).read_text(encoding="utf-8")
    try:
        control_part, remainder = text.split("SET ROLE janus_publication;", 1)
        publication_part, control_tail = remainder.split("RESET ROLE;", 1)
    except ValueError as error:
        raise RuntimeError("042 migration owner phases are not recognizable") from error

    # Phase 1: janus_control owns the serving table and grants bounded read access
    # to janus_publication.  Commit before the publication owner creates views.
    with control.connection.transaction(), control.connection.cursor() as cursor:
        cursor.execute(_clean_psql_sql(control_part))

    publication = _publication_connection()
    try:
        with publication.transaction(), publication.cursor() as cursor:
            cursor.execute(_clean_psql_sql(publication_part))
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
    finally:
        publication.close()

    # Record the migration only after both owner phases are committed.
    with control.connection.transaction(), control.connection.cursor() as cursor:
        cursor.execute(_clean_psql_sql(control_tail))
        cursor.execute(
            """SELECT
              EXISTS (SELECT 1 FROM control.schema_migrations
                      WHERE version='042_stock_serving_projection'),
              to_regclass('control.stock_serving_recent') IS NOT NULL,
              has_table_privilege('janus_publication','control.stock_serving_recent','SELECT'),
              has_table_privilege('janus_public_api','publication.stock_serving_recent','SELECT')"""
        )
        row = cursor.fetchone()
        if row is None or not all(bool(value) for value in row):
            raise RuntimeError("stock serving projection acceptance failed")


def run(control: Any, name: str) -> None:
    """Apply one allow-listed serving migration using existing DB identities."""
    if name == MIGRATION_POSITION:
        _apply_position(control)
    elif name == MIGRATION_STOCK_SERVING:
        _apply_stock_serving(control)
    else:
        raise ValueError("unsupported serving schema migration")
