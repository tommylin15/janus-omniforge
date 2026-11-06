\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

-- Optional broker-published Kbar volume. Historical rows and live quote
-- samples remain distinct; null means unavailable, never synthesized zero.
ALTER TABLE control.operational_session_kbars
  ADD COLUMN IF NOT EXISTS volume numeric(20,0)
    CHECK (volume >= 0 AND volume <= 1000000000000000);

-- PHASE: acceptance
SELECT to_regclass('control.operational_session_kbars') IS NOT NULL,
       EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='control'
                 AND table_name='operational_session_kbars'
                 AND column_name='volume'),
       has_table_privilege('janus_private_api','control.operational_session_kbars','SELECT'),
       NOT has_table_privilege('janus_public_api','control.operational_session_kbars','SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('079_session_kbar_volume') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
