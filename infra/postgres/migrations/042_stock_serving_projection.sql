\set ON_ERROR_STOP on

BEGIN;

SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS control.stock_serving_recent (
    dataset_id text NOT NULL CHECK (dataset_id IN ('ohlcv','valuation','events')),
    symbol varchar(20) NOT NULL REFERENCES control.stock_master(symbol) ON DELETE CASCADE,
    natural_key text NOT NULL CHECK (btrim(natural_key) <> ''),
    sort_at timestamptz NOT NULL,
    payload_json jsonb NOT NULL CHECK (jsonb_typeof(payload_json) = 'object'),
    source_id text NOT NULL CHECK (btrim(source_id) <> ''),
    provenance_id text NOT NULL CHECK (btrim(provenance_id) <> ''),
    execution_id uuid NOT NULL,
    core_snapshot_id bigint,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_id, symbol, natural_key)
);

CREATE INDEX IF NOT EXISTS stock_serving_recent_lookup_idx
    ON control.stock_serving_recent(dataset_id, symbol, sort_at DESC);
CREATE INDEX IF NOT EXISTS stock_serving_recent_retention_idx
    ON control.stock_serving_recent(dataset_id, sort_at);

RESET ROLE;

GRANT USAGE ON SCHEMA control TO janus_publication;
GRANT SELECT ON control.stock_serving_recent TO janus_publication;

SET ROLE janus_publication;

CREATE OR REPLACE VIEW publication.stock_serving_recent
WITH (security_barrier = true) AS
SELECT s.dataset_id, s.symbol, s.sort_at, s.payload_json, s.core_snapshot_id
FROM control.stock_serving_recent s
JOIN control.stock_master m ON m.symbol = s.symbol
WHERE m.enabled = true;

CREATE OR REPLACE VIEW publication.stock_latest
WITH (security_barrier = true) AS
SELECT DISTINCT ON (symbol, dataset_id)
       symbol, dataset_id, sort_at, payload_json, core_snapshot_id
FROM publication.stock_serving_recent
ORDER BY symbol, dataset_id, sort_at DESC;

RESET ROLE;

REVOKE ALL ON publication.stock_serving_recent, publication.stock_latest FROM PUBLIC;
GRANT SELECT ON publication.stock_serving_recent, publication.stock_latest TO janus_public_api;

INSERT INTO control.schema_migrations(version)
VALUES ('042_stock_serving_projection')
ON CONFLICT(version) DO NOTHING;

COMMIT;
