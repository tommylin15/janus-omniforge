\set ON_ERROR_STOP on
BEGIN;
-- PHASE: control-apply
-- Published market quotes, not owner data; do not broaden private ledger grants.
GRANT USAGE ON SCHEMA publication TO janus_private_api;
GRANT SELECT ON publication.stock_serving_recent TO janus_private_api;

-- PHASE: acceptance
SELECT has_table_privilege('janus_private_api','publication.stock_serving_recent','SELECT'),
       NOT has_table_privilege('janus_public_api','private.current_positions','SELECT');
INSERT INTO control.schema_migrations(version)
VALUES ('050_holdings_previous_close_read') ON CONFLICT(version) DO NOTHING;
COMMIT;
