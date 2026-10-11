\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- Widen the capability upper bound without modifying any owner, history or report.
ALTER TABLE private.ceo_capability_revisions
DROP CONSTRAINT ceo_capability_revisions_daily_quota_check;
ALTER TABLE private.ceo_capability_revisions
ADD CONSTRAINT ceo_capability_revisions_daily_quota_check
CHECK (daily_quota BETWEEN 0 AND 50);

-- PHASE: acceptance
SELECT
    EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='private.ceo_capability_revisions'::regclass
          AND conname='ceo_capability_revisions_daily_quota_check'
          AND contype='c' AND convalidated AND pg_get_constraintdef(oid) LIKE '%50%'
    ),
    NOT has_table_privilege('janus_public_api','private.ceo_capability_revisions','SELECT'),
    NOT has_table_privilege('janus_mart_publication','private.ledger_events','SELECT');
INSERT INTO control.schema_migrations(version)
VALUES ('052_ceo_daily_quota_50') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
