\set ON_ERROR_STOP on

BEGIN;

-- PHASE: control-prepare
SET ROLE janus_control;

-- DRL-01D: a tiny published, non-canonical five-year PE/PB profile.
-- Raw 5Y daily observations remain in official Core Iceberg; no request-time GCS scans.
CREATE TABLE IF NOT EXISTS control.stock_valuation_five_year (
    symbol varchar(20) NOT NULL REFERENCES control.stock_master(symbol) ON DELETE CASCADE,
    metric varchar(16) NOT NULL CHECK (metric IN ('pe_ratio', 'pb_ratio')),
    as_of_date date NOT NULL,
    core_snapshot_id bigint NOT NULL,
    payload_json jsonb NOT NULL CHECK (jsonb_typeof(payload_json) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, metric)
);

RESET ROLE;

GRANT USAGE ON SCHEMA control TO janus_publication;
GRANT SELECT ON control.stock_valuation_five_year TO janus_publication;

-- PHASE: publication
SET ROLE janus_publication;

CREATE OR REPLACE VIEW publication.stock_valuation_five_year
WITH (security_barrier = true) AS
SELECT p.symbol, p.metric, p.as_of_date, p.core_snapshot_id, p.payload_json
FROM control.stock_valuation_five_year AS p
JOIN control.stock_master AS m ON m.symbol = p.symbol
WHERE m.enabled = true;

RESET ROLE;

REVOKE ALL ON publication.stock_valuation_five_year FROM PUBLIC;
GRANT SELECT ON publication.stock_valuation_five_year TO janus_public_api;

-- PHASE: acceptance
SELECT
  to_regclass('publication.stock_valuation_five_year') IS NOT NULL,
  has_table_privilege('janus_public_api', 'publication.stock_valuation_five_year', 'SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('063_stock_valuation_five_year')
ON CONFLICT(version) DO NOTHING;

COMMIT;
