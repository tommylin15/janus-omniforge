\set ON_ERROR_STOP on
BEGIN;
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
INSERT INTO control.schema_migrations(version) VALUES ('073_intraday_taiex_minutes')
    ON CONFLICT DO NOTHING;
COMMIT;
