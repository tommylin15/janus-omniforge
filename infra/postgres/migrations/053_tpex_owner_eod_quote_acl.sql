\set ON_ERROR_STOP on
BEGIN;
-- 053: Owner-held TPEx official EOD, independently of research-500 coverage.
-- Scope: one rebuildable non-owner quote table only; no public grant.
SET ROLE janus_control;

ALTER TABLE control.operational_last_quotes
    DROP CONSTRAINT IF EXISTS operational_last_quotes_source_check;
ALTER TABLE control.operational_last_quotes
    ADD CONSTRAINT operational_last_quotes_source_check
    CHECK (source IN ('twse_mis', 'tpex_openapi_eod'));

ALTER TABLE control.operational_last_quotes
    DROP CONSTRAINT IF EXISTS operational_last_quotes_session_check;
ALTER TABLE control.operational_last_quotes
    ADD CONSTRAINT operational_last_quotes_session_check
    CHECK (session IN ('regular', 'off_session', 'official_close'));

-- Prevent mislabeled TPEx observations (never present EOD as an MIS tick).
ALTER TABLE control.operational_last_quotes
    DROP CONSTRAINT IF EXISTS operational_last_quotes_tpex_official_identity_check;
ALTER TABLE control.operational_last_quotes
    ADD CONSTRAINT operational_last_quotes_tpex_official_identity_check
    CHECK (source <> 'tpex_openapi_eod'
           OR (session = 'official_close' AND route_version = 'latest-price.v2'));

-- Existing private API already has SELECT/INSERT/UPDATE from migration 044.
-- Private Mart needs these same table-limited verbs to refresh/persist the
-- authorized, public, owner-requested EOD snapshot in the quote read model.
GRANT SELECT, INSERT, UPDATE ON control.operational_last_quotes TO janus_private_pipeline;

-- PHASE: acceptance
SELECT
    has_schema_privilege('janus_private_pipeline', 'control', 'USAGE'),
    has_table_privilege('janus_private_pipeline', 'control.operational_last_quotes', 'SELECT'),
    has_table_privilege('janus_private_pipeline', 'control.operational_last_quotes', 'INSERT'),
    has_table_privilege('janus_private_pipeline', 'control.operational_last_quotes', 'UPDATE'),
    has_table_privilege('janus_private_api', 'control.operational_last_quotes', 'SELECT'),
    has_table_privilege('janus_private_api', 'control.operational_last_quotes', 'INSERT'),
    has_table_privilege('janus_private_api', 'control.operational_last_quotes', 'UPDATE'),
    NOT has_table_privilege('janus_public_api', 'control.operational_last_quotes', 'SELECT'),
    EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'control.operational_last_quotes'::regclass
          AND conname = 'operational_last_quotes_source_check'
          AND pg_get_constraintdef(oid) LIKE '%tpex_openapi_eod%'
    ),
    EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'control.operational_last_quotes'::regclass
          AND conname = 'operational_last_quotes_session_check'
          AND pg_get_constraintdef(oid) LIKE '%official_close%'
    ),
    EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'control.operational_last_quotes'::regclass
          AND conname = 'operational_last_quotes_tpex_official_identity_check'
          AND pg_get_constraintdef(oid) LIKE '%latest-price.v2%'
    );

INSERT INTO control.schema_migrations(version)
VALUES ('053_tpex_owner_eod_quote_acl')
ON CONFLICT(version) DO NOTHING;
RESET ROLE;
COMMIT;
