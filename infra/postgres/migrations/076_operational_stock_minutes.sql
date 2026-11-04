\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

-- Page-demanded Shioaji/TWSE observations only. These are NOT official OHLC
-- candles and cannot claim the day's actual intraday extrema.
CREATE TABLE IF NOT EXISTS control.operational_symbol_minutes (
  symbol text NOT NULL CHECK (symbol ~ '^[0-9A-Z]{4,10}$'),
  minute_at timestamptz NOT NULL,
  quote_at timestamptz NOT NULL,
  price numeric(20,4) NOT NULL CHECK (price > 0),
  received_at timestamptz NOT NULL,
  source text NOT NULL CHECK (source IN ('shioaji','twse_mis')),
  PRIMARY KEY (symbol,minute_at)
);
CREATE INDEX IF NOT EXISTS operational_symbol_minutes_cleanup
  ON control.operational_symbol_minutes(minute_at);
GRANT SELECT, INSERT, UPDATE, DELETE ON control.operational_symbol_minutes TO janus_private_api;
REVOKE ALL ON control.operational_symbol_minutes FROM PUBLIC;

-- PHASE: acceptance
SELECT
  to_regclass('control.operational_symbol_minutes') IS NOT NULL,
  has_table_privilege('janus_private_api','control.operational_symbol_minutes','SELECT'),
  has_table_privilege('janus_private_api','control.operational_symbol_minutes','INSERT'),
  has_table_privilege('janus_private_api','control.operational_symbol_minutes','UPDATE'),
  has_table_privilege('janus_private_api','control.operational_symbol_minutes','DELETE'),
  NOT has_table_privilege('janus_public_api','control.operational_symbol_minutes','SELECT');

INSERT INTO control.schema_migrations(version) VALUES('076_operational_stock_minutes')
  ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
