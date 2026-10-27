\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
ALTER TABLE control.market_serving_recent DROP CONSTRAINT IF EXISTS market_serving_recent_source_id_check;
ALTER TABLE control.market_serving_recent ADD CONSTRAINT market_serving_recent_source_id_check CHECK (
    source_id IN ('twse','tpex','taiex','mops') OR
    (source_id='yahoo-finance' AND dataset_id='financials'
      AND coalesce(payload_json->>'metric','')='eps_single_quarter'
      AND coalesce(payload_json->>'period_basis','')='single_quarter'
      AND coalesce(payload_json->>'unit','')='TWD_per_share') OR
    (source_id IN ('finmind','yahoo-finance') AND dataset_id='financials'
      AND coalesce(payload_json->>'metric','')='monthly_revenue'
      AND coalesce(payload_json->>'statement_type','')='monthly_revenue'
      AND coalesce(payload_json->>'unit','')='TWD_thousands')
);
RESET ROLE;
INSERT INTO control.schema_migrations(version) VALUES ('070_yahoo_revenue_serving')
ON CONFLICT(version) DO NOTHING;
COMMIT;
