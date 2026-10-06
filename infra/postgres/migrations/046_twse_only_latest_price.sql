\set ON_ERROR_STOP on
BEGIN;

-- PHASE: control-apply
SET ROLE janus_control;

-- TPEx is retired from the active Janus product scope. Preserve historical
-- rows, source ids, execution history and Core data for auditability. Only
-- TWSE configs may have retired TPEx fallbacks removed from their active route.
UPDATE control.collection_configs
SET source_ids = source_ids - 'tpex' - 'tpex-benchmark'
WHERE market='TWSE'
  AND (source_ids ? 'tpex' OR source_ids ? 'tpex-benchmark')
  AND jsonb_array_length(source_ids - 'tpex' - 'tpex-benchmark') > 0;

UPDATE control.collection_configs
SET enabled=false, collection_enabled=false, analysis_enabled=false
WHERE market='TPEX';

UPDATE control.stock_master
SET enabled=false, updated_at=now()
WHERE market='TPEX' AND enabled;

-- PHASE: acceptance
SELECT
  NOT EXISTS (
    SELECT 1 FROM control.collection_configs
    WHERE enabled AND (
      market='TPEX' OR source_ids ? 'tpex' OR source_ids ? 'tpex-benchmark'
    )
  ),
  NOT EXISTS (
    SELECT 1 FROM control.stock_master WHERE enabled AND market='TPEX'
  ),
  NOT EXISTS (
    SELECT 1 FROM control.collection_configs
    WHERE jsonb_array_length(source_ids)=0
  ),
  has_table_privilege('janus_private_api','publication.stock_latest','SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('046_twse_only_latest_price')
ON CONFLICT(version) DO NOTHING;

RESET ROLE;
COMMIT;
