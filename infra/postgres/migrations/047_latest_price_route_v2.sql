\set ON_ERROR_STOP on
BEGIN;

-- PHASE: control-apply
SET ROLE janus_control;

ALTER TABLE control.operational_last_quotes
  DROP CONSTRAINT IF EXISTS operational_last_quotes_route_version_check;
ALTER TABLE control.operational_last_quotes
  ADD CONSTRAINT operational_last_quotes_route_version_check
  CHECK (route_version IN ('quote-router.v1','latest-price.v2'));

-- PHASE: acceptance
SELECT
  EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid=c.conrelid
    JOIN pg_namespace n ON n.oid=t.relnamespace
    WHERE n.nspname='control'
      AND t.relname='operational_last_quotes'
      AND c.conname='operational_last_quotes_route_version_check'
      AND pg_get_constraintdef(c.oid) LIKE '%latest-price.v2%'
  ),
  has_table_privilege('janus_private_api','control.operational_last_quotes','UPDATE'),
  has_table_privilege('janus_private_api','publication.stock_latest','SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('047_latest_price_route_v2')
ON CONFLICT(version) DO NOTHING;

RESET ROLE;
COMMIT;
