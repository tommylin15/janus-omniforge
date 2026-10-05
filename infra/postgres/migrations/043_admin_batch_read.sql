\set ON_ERROR_STOP on
BEGIN;
-- PHASE: control-prepare
-- Existing Admin identity reads operational state only; no dispatch privileges.
GRANT SELECT ON control.batch_occurrences TO janus_web_control;
CREATE INDEX IF NOT EXISTS batch_occurrences_history_idx
    ON control.batch_occurrences(scheduled_at DESC,occurrence_id DESC);
-- PHASE: publication-apply
GRANT USAGE ON SCHEMA publication TO janus_private_api;
GRANT SELECT ON publication.stock_latest TO janus_private_api;
-- PHASE: control-finalize
INSERT INTO control.schema_migrations(version) VALUES ('043_admin_batch_read')
ON CONFLICT (version) DO NOTHING;
COMMIT;
