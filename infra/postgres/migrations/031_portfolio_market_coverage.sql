SET ROLE janus_control;

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
      AND cc.enabled
      AND cc.collection_enabled
      AND cc.dataset_id = 'ohlcv'
      AND cc.batch_scope = 'symbol'
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

REVOKE ALL ON FUNCTION control.request_portfolio_market_coverage(text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION control.request_portfolio_market_coverage(text[]) TO janus_private_pipeline;

RESET ROLE;
