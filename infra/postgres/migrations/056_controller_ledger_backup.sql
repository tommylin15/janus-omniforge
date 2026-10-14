\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
CREATE TABLE IF NOT EXISTS control.ledger_backup_requests (
    backup_date date PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('queued','running','succeeded','failed')),
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    size_bytes bigint,
    sha256 text,
    error_code text,
    CHECK (status <> 'succeeded' OR
           (size_bytes IS NOT NULL AND size_bytes >= 1024 AND sha256 IS NOT NULL
            AND sha256 ~ '^[a-f0-9]{64}$' AND completed_at IS NOT NULL))
);
REVOKE ALL ON control.ledger_backup_requests FROM PUBLIC;
-- Existing controller identity requests and observes; the existing VM local
-- database administrator claims and records actual pg_dump/upload receipts.
-- PHASE: acceptance
SELECT to_regclass('control.ledger_backup_requests') IS NOT NULL,
       NOT has_table_privilege('janus_public_api','control.ledger_backup_requests','SELECT'),
       NOT has_table_privilege('janus_private_api','control.ledger_backup_requests','INSERT');
INSERT INTO control.schema_migrations(version) VALUES ('056_controller_ledger_backup') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
