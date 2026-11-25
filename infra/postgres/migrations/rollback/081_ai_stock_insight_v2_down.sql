\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

DROP TABLE IF EXISTS control.stock_insight_v2_snapshots;
DELETE FROM control.schema_migrations WHERE version = '081_ai_stock_insight_v2';

RESET ROLE;
COMMIT;
