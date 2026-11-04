\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

-- Preserve existing TWSE/TPEx last-success observations while allowing the
-- read-only simulation Shioaji feed to be stored with truthful provenance.
ALTER TABLE control.operational_last_quotes
    DROP CONSTRAINT IF EXISTS operational_last_quotes_source_check;
ALTER TABLE control.operational_last_quotes
    ADD CONSTRAINT operational_last_quotes_source_check
    CHECK (source IN ('twse_mis', 'tpex_openapi_eod', 'shioaji'));

-- PHASE: acceptance
SELECT EXISTS (
  SELECT 1 FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
  WHERE n.nspname = 'control'
    AND t.relname = 'operational_last_quotes'
    AND c.conname = 'operational_last_quotes_source_check'
    AND pg_get_constraintdef(c.oid) LIKE '%shioaji%'
), has_table_privilege('janus_private_api',
                        'control.operational_last_quotes', 'UPDATE');

INSERT INTO control.schema_migrations(version)
VALUES ('074_shioaji_quote_source') ON CONFLICT DO NOTHING;
COMMIT;
