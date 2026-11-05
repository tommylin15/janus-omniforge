\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

-- The existing index-minute table (migration 073) has no DELETE permission.
-- Match the existing three-day stock-minute write-time retention; do not run
-- a new scheduler or delete non-minute EOD/position rows.
GRANT DELETE ON control.operational_index_minutes TO janus_private_api;

-- PHASE: acceptance
SELECT
  has_table_privilege('janus_private_api', 'control.operational_index_minutes', 'SELECT'),
  has_table_privilege('janus_private_api', 'control.operational_index_minutes', 'INSERT'),
  has_table_privilege('janus_private_api', 'control.operational_index_minutes', 'UPDATE'),
  has_table_privilege('janus_private_api', 'control.operational_index_minutes', 'DELETE'),
  NOT has_table_privilege('janus_public_api', 'control.operational_index_minutes', 'SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('077_index_minutes_three_day_retention') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
