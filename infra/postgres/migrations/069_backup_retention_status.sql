\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
ALTER TABLE control.ledger_backup_requests
    ADD COLUMN IF NOT EXISTS retention_status text NOT NULL DEFAULT 'pending'
        CHECK (retention_status IN ('pending','succeeded','failed')),
    ADD COLUMN IF NOT EXISTS retention_receipt jsonb;
INSERT INTO control.schema_migrations(version) VALUES ('069_backup_retention_status') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
