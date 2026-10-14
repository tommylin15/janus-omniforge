\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- 寫入時預聚合 (Write-time Aggregation) 首頁市場快照
CREATE TABLE IF NOT EXISTS control.home_market_snapshot (
    snapshot_id int PRIMARY KEY DEFAULT 1,
    schema_version text NOT NULL DEFAULT 'market-home.v1',
    as_of_date date NOT NULL,
    payload_json jsonb NOT NULL CHECK (jsonb_typeof(payload_json) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT single_row_check CHECK (snapshot_id = 1)
);

RESET ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE ON control.home_market_snapshot TO janus_control;
GRANT SELECT ON control.home_market_snapshot TO janus_publication;

-- PHASE: publication
SET ROLE janus_publication;
CREATE OR REPLACE VIEW publication.home_market_snapshot
WITH (security_barrier=true) AS
SELECT snapshot_id, schema_version, as_of_date, payload_json, updated_at
FROM control.home_market_snapshot;

RESET ROLE;
REVOKE ALL ON publication.home_market_snapshot FROM PUBLIC;
GRANT SELECT ON publication.home_market_snapshot TO janus_public_api;

-- PHASE: acceptance
SELECT has_table_privilege('janus_public_api', 'publication.home_market_snapshot', 'SELECT'),
    NOT has_table_privilege('janus_public_api', 'control.home_market_snapshot', 'INSERT'),
    NOT has_table_privilege('janus_public_api', 'publication.home_market_snapshot', 'INSERT');

INSERT INTO control.schema_migrations(version) VALUES ('057_home_market_snapshot') ON CONFLICT DO NOTHING;
COMMIT;
