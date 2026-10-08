\set ON_ERROR_STOP on
BEGIN;
-- PHASE: publication-apply
-- Publication schema belongs to janus_publication. Reuse published public
-- OHLCV only; never grant the public role access to owner positions.
-- The migration change also schedules API deployment after the ACL gate.
SET ROLE janus_publication;
GRANT USAGE ON SCHEMA publication TO janus_private_api;
GRANT SELECT ON publication.stock_serving_recent TO janus_private_api;
SELECT has_schema_privilege('janus_private_api','publication','USAGE'),
       has_table_privilege('janus_private_api','publication.stock_serving_recent','SELECT');
RESET ROLE;

-- PHASE: control-finalize
SET ROLE janus_control;
-- janus_control has no USAGE on publication. Validate that ACL under the
-- publication owner above; do not expand the control identity's permissions.
SELECT NOT has_table_privilege('janus_public_api','private.current_positions','SELECT');
INSERT INTO control.schema_migrations(version)
VALUES ('050_holdings_previous_close_read') ON CONFLICT(version) DO NOTHING;
RESET ROLE;
COMMIT;
