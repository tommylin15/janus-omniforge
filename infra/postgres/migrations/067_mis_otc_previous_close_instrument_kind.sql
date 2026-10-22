\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- MIS previous session close (y) is persisted with exact symbol and source;
-- no prior-session calendar date is invented.
ALTER TABLE control.operational_last_quotes
    ADD COLUMN IF NOT EXISTS previous_close numeric(20,4)
    CHECK (previous_close IS NULL OR previous_close > 0);

-- Verified public instrument classes, not owner data. Read-only roles.
GRANT SELECT ON control.official_instrument_identity_provenance
    TO janus_private_api, janus_public_api;

-- PHASE: acceptance
SELECT
  has_column_privilege('janus_private_api','control.operational_last_quotes','previous_close','SELECT'),
  has_column_privilege('janus_private_api','control.operational_last_quotes','previous_close','UPDATE'),
  has_table_privilege('janus_public_api','control.official_instrument_identity_provenance','SELECT'),
  NOT has_table_privilege('janus_public_api','control.official_instrument_identity_provenance','INSERT');

INSERT INTO control.schema_migrations(version)
VALUES ('067_mis_otc_previous_close_instrument_kind') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
