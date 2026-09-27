"""Cloud Run entrypoint with bounded, secret-safe failure diagnostics."""

from __future__ import annotations

import json
import os
import sys
from time import monotonic
from typing import Any

from .__main__ import _control_plane, consume_queued_collection, run_scheduled_collection


CONTROL_MIGRATION_PRIVATE_STOCK_MASTER_READ = "030_private_stock_master_read"
CONTROL_MIGRATION_PORTFOLIO_MARKET_COVERAGE = "031_portfolio_market_coverage"
CONTROL_MIGRATION_LIQUID_500 = "032_liquid_500"
CONTROL_MIGRATION_LIQUID_500_TPEX_SOURCE = "033_liquid_500_tpex_source"
CONTROL_MIGRATIONS = {
    CONTROL_MIGRATION_PRIVATE_STOCK_MASTER_READ,
    CONTROL_MIGRATION_PORTFOLIO_MARKET_COVERAGE,
    CONTROL_MIGRATION_LIQUID_500,
    CONTROL_MIGRATION_LIQUID_500_TPEX_SOURCE,
}


def _apply_private_stock_master_read(cursor: Any) -> None:
    cursor.execute(
        "GRANT USAGE ON SCHEMA control TO janus_private_api, janus_private_pipeline"
    )
    cursor.execute(
        "GRANT SELECT ON control.stock_master TO janus_private_api, janus_private_pipeline"
    )
    cursor.execute(
        """SELECT
            has_schema_privilege('janus_private_api', 'control', 'USAGE'),
            has_table_privilege('janus_private_api', 'control.stock_master', 'SELECT'),
            has_schema_privilege('janus_private_pipeline', 'control', 'USAGE'),
            has_table_privilege('janus_private_pipeline', 'control.stock_master', 'SELECT')"""
    )
    privileges = cursor.fetchone()
    if privileges is None or not all(bool(value) for value in privileges):
        raise RuntimeError("private stock-master ACL verification failed")


def _apply_portfolio_market_coverage(cursor: Any) -> None:
    cursor.execute("SET LOCAL ROLE janus_control")
    cursor.execute(
        """CREATE OR REPLACE FUNCTION control.request_portfolio_market_coverage(requested_symbols text[])
        RETURNS TABLE(symbol text)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $function$
          WITH eligible AS (
            SELECT sm.symbol, cc.config_id
            FROM control.stock_master AS sm
            JOIN control.collection_configs AS cc
              ON cc.market = sm.market
            WHERE sm.enabled
              AND cc.enabled
              AND cc.collection_enabled
              AND cc.dataset_id = 'ohlcv'
              AND cc.batch_scope = 'symbol'
              AND cc.coverage_tier <> 'core_focus'
              AND sm.symbol = ANY(requested_symbols)
          ),
          inserted AS (
            INSERT INTO control.collection_symbols(config_id, symbol)
            SELECT config_id, symbol
            FROM eligible
            ON CONFLICT (config_id, symbol) DO NOTHING
            RETURNING symbol
          )
          SELECT DISTINCT eligible.symbol
          FROM eligible
          ORDER BY eligible.symbol
        $function$"""
    )
    cursor.execute(
        "REVOKE ALL ON FUNCTION control.request_portfolio_market_coverage(text[]) FROM PUBLIC"
    )
    cursor.execute(
        "GRANT EXECUTE ON FUNCTION control.request_portfolio_market_coverage(text[]) TO janus_private_pipeline"
    )
    cursor.execute(
        """SELECT
            has_function_privilege(
              'janus_private_pipeline',
              'control.request_portfolio_market_coverage(text[])',
              'EXECUTE'
            ),
            EXISTS (
              SELECT 1
              FROM pg_proc AS p
              JOIN pg_namespace AS n ON n.oid = p.pronamespace
              JOIN pg_roles AS r ON r.oid = p.proowner
              WHERE n.nspname = 'control'
                AND p.proname = 'request_portfolio_market_coverage'
                AND p.prosecdef
                AND r.rolname = 'janus_control'
            )"""
    )
    privileges = cursor.fetchone()
    if privileges is None or not all(bool(value) for value in privileges):
        raise RuntimeError("portfolio market coverage ACL verification failed")


def _apply_liquid_500(cursor: Any) -> None:
    cursor.execute("SET LOCAL ROLE janus_control")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS control.liquid_500_versions (
          version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          week_start date NOT NULL,
          effective_from timestamptz NOT NULL UNIQUE,
          reason text NOT NULL CHECK (btrim(reason) <> ''),
          actor text NOT NULL CHECK (btrim(actor) <> ''),
          source_snapshot jsonb NOT NULL CHECK (jsonb_typeof(source_snapshot) = 'object'),
          created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS control.liquid_500_members (
          version bigint NOT NULL REFERENCES control.liquid_500_versions(version) ON DELETE RESTRICT,
          rank integer NOT NULL CHECK (rank BETWEEN 1 AND 500),
          symbol text NOT NULL REFERENCES control.stock_master(symbol) ON DELETE RESTRICT,
          volume_shares bigint,
          turnover_twd numeric(24,2),
          manual_override boolean NOT NULL DEFAULT false,
          PRIMARY KEY (version, symbol),
          UNIQUE (version, rank),
          CHECK (volume_shares IS NULL OR volume_shares >= 0),
          CHECK (turnover_twd IS NULL OR turnover_twd >= 0)
        )"""
    )
    cursor.execute(
        "GRANT SELECT, INSERT ON control.liquid_500_versions, control.liquid_500_members TO janus_web_control"
    )
    cursor.execute(
        "GRANT USAGE, SELECT ON SEQUENCE control.liquid_500_versions_version_seq TO janus_web_control"
    )
    cursor.execute(
        "GRANT SELECT ON control.liquid_500_versions, control.liquid_500_members TO janus_private_api"
    )
    cursor.execute(
        "INSERT INTO control.schema_migrations(version) VALUES ('032_liquid_500') ON CONFLICT DO NOTHING"
    )
    cursor.execute(
        """SELECT
          has_table_privilege('janus_web_control', 'control.liquid_500_versions', 'INSERT'),
          has_table_privilege('janus_web_control', 'control.liquid_500_members', 'INSERT'),
          has_table_privilege('janus_private_api', 'control.liquid_500_versions', 'SELECT'),
          has_table_privilege('janus_private_api', 'control.liquid_500_members', 'SELECT'),
          EXISTS (SELECT 1 FROM control.schema_migrations WHERE version = '032_liquid_500')"""
    )
    privileges = cursor.fetchone()
    if privileges is None or not all(bool(value) for value in privileges):
        raise RuntimeError("liquid-500 schema and ACL verification failed")


def _apply_liquid_500_tpex_source(cursor: Any) -> None:
    cursor.execute("SET LOCAL ROLE janus_control")
    cursor.execute(
        """UPDATE control.collection_configs AS config
        SET source_ids = (
          SELECT jsonb_agg(DISTINCT source_id ORDER BY source_id)
          FROM jsonb_array_elements_text(config.source_ids || '[\"tpex\"]'::jsonb)
               AS sources(source_id)
        )
        WHERE config_id = 'first-batch'"""
    )
    cursor.execute(
        "SELECT source_ids ? 'tpex' FROM control.collection_configs WHERE config_id = 'first-batch'"
    )
    enabled = cursor.fetchone()
    if enabled is None or not bool(enabled[0]):
        raise RuntimeError("TPEx market-volume source is not enabled")
    cursor.execute(
        "INSERT INTO control.schema_migrations(version) VALUES ('033_liquid_500_tpex_source') ON CONFLICT DO NOTHING"
    )


def _run_control_migration(name: str) -> dict[str, Any]:
    """Apply one allow-listed control-owner migration used by portfolio completeness."""
    if name not in CONTROL_MIGRATIONS:
        raise ValueError("unsupported control migration")
    with _control_plane() as control:
        with control.connection.transaction(), control.connection.cursor() as cursor:
            if name == CONTROL_MIGRATION_PRIVATE_STOCK_MASTER_READ:
                _apply_private_stock_master_read(cursor)
            elif name == CONTROL_MIGRATION_PORTFOLIO_MARKET_COVERAGE:
                _apply_portfolio_market_coverage(cursor)
            elif name == CONTROL_MIGRATION_LIQUID_500:
                _apply_liquid_500(cursor)
            else:
                _apply_liquid_500_tpex_source(cursor)
    return {
        "component": "ingestion-core",
        "status": "succeeded",
        "operation": "control_migration",
        "migration": name,
    }


def _failure_details(error: Exception) -> list[dict[str, str]]:
    """Return only allow-listed aggregate failure fields from collect_stage()."""
    if not isinstance(error, RuntimeError):
        return []
    try:
        payload = json.loads(str(error))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    failures = payload.get("failures") if isinstance(payload, dict) else None
    if not isinstance(failures, list):
        return []
    result: list[dict[str, str]] = []
    for item in failures[:20]:
        if not isinstance(item, dict):
            continue
        safe = {
            key: str(item[key])[:80]
            for key in ("dataset", "date", "error")
            if item.get(key) is not None
        }
        if safe:
            result.append(safe)
    return result


def main() -> None:
    started = monotonic()
    try:
        control_migration = os.environ.get("JANUS_CONTROL_MIGRATION", "").strip()
        if control_migration:
            result = _run_control_migration(control_migration)
        else:
            operation = (
                consume_queued_collection
                if os.environ.get("QUEUE_CONSUMER", "false").lower() in {"1", "true", "yes"}
                else run_scheduled_collection
            )
            result = operation()
        result["duration_ms"] = round((monotonic() - started) * 1000)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except Exception as error:
        output: dict[str, Any] = {
            "component": "ingestion-core",
            "status": "failed",
            "error_code": type(error).__name__.upper()[:64],
            "duration_ms": round((monotonic() - started) * 1000),
        }
        failures = _failure_details(error)
        if failures:
            output["failures"] = failures
        print(json.dumps(output, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
