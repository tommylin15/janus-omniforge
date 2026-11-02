\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE private.personal_strategy_state ADD COLUMN IF NOT EXISTS draft jsonb;
INSERT INTO control.schema_migrations(version) VALUES ('072_personal_strategy_draft') ON CONFLICT DO NOTHING;
COMMIT;
