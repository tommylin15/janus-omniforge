\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';
CREATE TABLE IF NOT EXISTS control.operational_index_minutes (
    benchmark_id text NOT NULL CHECK (benchmark_id = 'TAIEX'),
    minute_at timestamptz NOT NULL,
    quote_at timestamptz NOT NULL,
    price numeric(20,4) NOT NULL CHECK (price > 0),
    received_at timestamptz NOT NULL,
    source text NOT NULL CHECK (source IN ('shioaji','twse_mis')),
    PRIMARY KEY (benchmark_id, minute_at)
);
CREATE INDEX IF NOT EXISTS operational_index_minutes_recent
    ON control.operational_index_minutes (minute_at DESC);
GRANT SELECT, INSERT, UPDATE ON control.operational_index_minutes TO janus_private_api;
REVOKE ALL ON control.operational_index_minutes FROM PUBLIC;
-- PHASE: acceptance
SELECT
  to_regclass('control.operational_index_minutes') IS NOT NULL,
  has_table_privilege('janus_private_api','control.operational_index_minutes','SELECT'),
  has_table_privilege('janus_private_api','control.operational_index_minutes','INSERT'),
  has_table_privilege('janus_private_api','control.operational_index_minutes','UPDATE');
INSERT INTO control.schema_migrations(version) VALUES ('073_intraday_taiex_minutes')
    ON CONFLICT DO NOTHING;
COMMIT;
