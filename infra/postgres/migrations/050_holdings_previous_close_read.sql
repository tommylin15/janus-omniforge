\set ON_ERROR_STOP on
BEGIN;
-- PHASE: control-prepare
SET ROLE janus_control;
GRANT USAGE ON SCHEMA publication TO janus_private_api;
RESET ROLE;

-- PHASE: publication-apply
SET ROLE janus_publication;
GRANT SELECT ON publication.stock_serving_recent TO janus_private_api;
RESET ROLE;

-- PHASE: control-finalize
SET ROLE janus_control;
SELECT has_schema_privilege('janus_private_api','publication','USAGE'),
       has_table_privilege('janus_private_api','publication.stock_serving_recent','SELECT'),
       NOT has_table_privilege('janus_public_api','private.current_positions','SELECT');
INSERT INTO control.schema_migrations(version)
VALUES ('050_holdings_previous_close_read') ON CONFLICT(version) DO NOTHING;
RESET ROLE;
COMMIT;
