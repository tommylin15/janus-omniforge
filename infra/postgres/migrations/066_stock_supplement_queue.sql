\set ON_ERROR_STOP on
BEGIN;
-- PHASE: control-prepare
SET ROLE janus_control;
CREATE TABLE IF NOT EXISTS control.stock_supplement_requests (
    symbol text PRIMARY KEY REFERENCES control.stock_master(symbol),
    demanded boolean NOT NULL,
    generation bigint NOT NULL DEFAULT 1,
    status text NOT NULL CHECK (status IN ('pending','running','partial','succeeded','cancelled')),
    attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    lease_token uuid,
    started_at timestamptz,
    finished_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    receipt jsonb NOT NULL DEFAULT '{}'::jsonb
);
REVOKE ALL ON control.stock_supplement_requests FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON control.stock_supplement_requests TO janus_private_api;
CREATE TABLE IF NOT EXISTS control.stock_supplement_dispatch (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    reserved_at timestamptz
);
INSERT INTO control.stock_supplement_dispatch(singleton) VALUES(true) ON CONFLICT DO NOTHING;
GRANT SELECT,UPDATE ON control.stock_supplement_dispatch TO janus_private_api;
GRANT CREATE ON SCHEMA control TO janus_private_api;
ALTER TABLE control.market_serving_recent DROP CONSTRAINT IF EXISTS market_serving_recent_source_id_check;
ALTER TABLE control.market_serving_recent ADD CONSTRAINT market_serving_recent_source_id_check CHECK (
    source_id IN ('twse','tpex','taiex','mops') OR
    (source_id='yahoo-finance' AND dataset_id='financials'
      AND coalesce(payload_json->>'metric','')='eps_single_quarter'
      AND coalesce(payload_json->>'period_basis','')='single_quarter'
      AND coalesce(payload_json->>'unit','')='TWD_per_share') OR
    (source_id='finmind' AND dataset_id='financials'
      AND coalesce(payload_json->>'metric','')='monthly_revenue'
      AND coalesce(payload_json->>'statement_type','')='monthly_revenue'
      AND coalesce(payload_json->>'unit','')='TWD_thousands')
);
RESET ROLE;
-- PHASE: private-api
SET ROLE janus_private_api;
CREATE OR REPLACE FUNCTION control.sync_stock_supplement_demand()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE target record; active_symbols text[];
BEGIN
    PERFORM pg_advisory_xact_lock(1835102836, 7);
    SELECT array_agg(symbol ORDER BY symbol) INTO active_symbols FROM (
      SELECT symbol FROM private.watchlist WHERE active
      UNION SELECT symbol FROM private.current_positions WHERE shares>0
    ) desired;
    IF cardinality(active_symbols)>1000 THEN RAISE EXCEPTION 'supplement demand limit exceeded'; END IF;
    FOR target IN SELECT sm.symbol FROM control.stock_master sm
      WHERE sm.enabled AND sm.market IN ('TWSE','TPEX') AND sm.symbol=ANY(coalesce(active_symbols,ARRAY[]::text[]))
      ORDER BY sm.symbol
    LOOP
      INSERT INTO control.stock_supplement_requests(symbol,demanded,status)
      VALUES(target.symbol,true,'pending')
      ON CONFLICT(symbol) DO UPDATE SET demanded=true,
        generation=control.stock_supplement_requests.generation+1,
        status='pending',attempts=0,next_attempt_at=now(),lease_token=NULL,updated_at=now()
      WHERE NOT control.stock_supplement_requests.demanded;
    END LOOP;
    UPDATE control.stock_supplement_requests SET demanded=false,status='cancelled',
      generation=generation+1,lease_token=NULL,updated_at=now()
      WHERE demanded AND NOT(symbol=ANY(coalesce(active_symbols,ARRAY[]::text[])));
END;
$$;
REVOKE ALL ON FUNCTION control.sync_stock_supplement_demand() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION control.sync_stock_supplement_demand() TO janus_control,janus_private_pipeline;
RESET ROLE;
-- PHASE: control-finalize
SET ROLE janus_control;
REVOKE CREATE ON SCHEMA control FROM janus_private_api;
-- PHASE: acceptance
SELECT to_regclass('control.stock_supplement_requests') IS NOT NULL,
  NOT has_table_privilege('janus_public_api','control.stock_supplement_requests','SELECT'),
  NOT has_table_privilege('janus_web_control','control.stock_supplement_requests','UPDATE'),
  NOT has_schema_privilege('janus_private_api','control','CREATE'),
  has_function_privilege('janus_control','control.sync_stock_supplement_demand()','EXECUTE');
INSERT INTO control.schema_migrations(version) VALUES('066_stock_supplement_queue') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
