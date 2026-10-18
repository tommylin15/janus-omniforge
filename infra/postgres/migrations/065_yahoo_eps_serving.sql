-- User-approved third-party EPS supplement; existing official sources unchanged.
BEGIN;
ALTER TABLE control.market_serving_recent
    DROP CONSTRAINT IF EXISTS market_serving_recent_source_id_check;
ALTER TABLE control.market_serving_recent
    ADD CONSTRAINT market_serving_recent_source_id_check CHECK (
        source_id IN ('twse','tpex','taiex','mops') OR
        (source_id='yahoo-finance' AND dataset_id='financials'
         AND coalesce(payload_json->>'metric','')='eps_single_quarter'
         AND coalesce(payload_json->>'period_basis','')='single_quarter'
         AND coalesce(payload_json->>'unit','')='TWD_per_share')
    );
INSERT INTO control.schema_migrations(version) VALUES ('065_yahoo_eps_serving')
ON CONFLICT(version) DO NOTHING;
COMMIT;
