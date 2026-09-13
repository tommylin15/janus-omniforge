\set ON_ERROR_STOP on

BEGIN;
CREATE TABLE control.janus_migration_rollback_probe(value integer);
SELECT 1 / 0;
COMMIT;
