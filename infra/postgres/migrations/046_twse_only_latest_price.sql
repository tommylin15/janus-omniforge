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

CREATE OR REPLACE FUNCTION control.request_portfolio_market_coverage(requested_symbols text[])
RETURNS TABLE(symbol text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
  WITH eligible AS (
    SELECT sm.symbol, cc.config_id
    FROM control.stock_master AS sm
    JOIN control.collection_configs AS cc
      ON cc.market = sm.market
    WHERE sm.enabled
      AND sm.market='TWSE'
      AND cc.market='TWSE'
      AND cc.enabled
      AND cc.collection_enabled
      AND cc.dataset_id='ohlcv'
      AND cc.batch_scope='symbol'
      AND cc.coverage_tier <> 'core_focus'
      AND sm.symbol = ANY(requested_symbols)
  ),
  inserted AS (
    INSERT INTO control.collection_symbols(config_id, symbol)
    SELECT config_id, symbol
    FROM eligible
    ON CONFLICT (config_id, symbol) DO NOTHING
    RETURNING symbol
  )
  SELECT DISTINCT eligible.symbol
  FROM eligible
  ORDER BY eligible.symbol
$function$;

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
