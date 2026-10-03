\set ON_ERROR_STOP on
BEGIN;

-- Core retention uses only the existing de-identified symbol projection.
-- Its control role already owns the history tables; no private-table access.
GRANT EXECUTE ON FUNCTION control.mart_ai_target_symbols(date) TO janus_control;

INSERT INTO control.schema_migrations(version) VALUES ('040_core_retention_targets')
ON CONFLICT (version) DO NOTHING;
COMMIT;
