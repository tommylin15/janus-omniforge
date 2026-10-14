\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- Restore listed/OTC official data; full-market membership is versioned in 055.
UPDATE control.collection_configs SET source_ids=source_ids || '["tpex"]'::jsonb
WHERE config_id='first-batch' AND NOT source_ids ? 'tpex';
UPDATE control.stock_master SET enabled=true,updated_at=now()
WHERE market='TPEX' AND listing_status='listed';

CREATE TABLE IF NOT EXISTS control.market_serving_recent (
    dataset_id text NOT NULL CHECK (dataset_id IN ('benchmark','institutional','market-activity','financials')),
    symbol varchar(20) NOT NULL,
    natural_key text NOT NULL,
    sort_at timestamptz NOT NULL,
    payload_json jsonb NOT NULL CHECK (jsonb_typeof(payload_json)='object'),
    source_id text NOT NULL CHECK (source_id IN ('twse','tpex','taiex','mops')),
    provenance_id text NOT NULL CHECK (btrim(provenance_id)<>''),
    execution_id uuid NOT NULL,
    core_snapshot_id bigint,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(dataset_id,symbol,natural_key)
);
CREATE INDEX IF NOT EXISTS market_serving_recent_lookup_idx
    ON control.market_serving_recent(dataset_id,symbol,sort_at DESC);
CREATE INDEX IF NOT EXISTS market_serving_recent_date_idx
    ON control.market_serving_recent(dataset_id,sort_at DESC);
RESET ROLE;
GRANT SELECT ON control.market_serving_recent TO janus_publication;
-- PHASE: publication
SET ROLE janus_publication;
CREATE OR REPLACE VIEW publication.market_serving_recent
WITH (security_barrier=true) AS
SELECT dataset_id,symbol,sort_at,payload_json,source_id,provenance_id,execution_id,core_snapshot_id,natural_key
FROM control.market_serving_recent;
RESET ROLE;
REVOKE ALL ON publication.market_serving_recent FROM PUBLIC;
GRANT SELECT ON publication.market_serving_recent TO janus_public_api;

-- PHASE: acceptance
SELECT has_table_privilege('janus_public_api','publication.market_serving_recent','SELECT'),
    NOT has_table_privilege('janus_public_api','control.market_serving_recent','INSERT'),
    NOT has_table_privilege('janus_public_api','publication.market_serving_recent','INSERT');
INSERT INTO control.schema_migrations(version) VALUES ('054_market_serving') ON CONFLICT DO NOTHING;
COMMIT;
