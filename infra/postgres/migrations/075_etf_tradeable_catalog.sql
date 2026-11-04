\\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- Tradable ETF identities share stock_master only for existing FK/read-model
-- compatibility. Never insert them into control.market_universe_members.
-- Source is TWSE's official ISIN directory, validated by the application.
CREATE TABLE IF NOT EXISTS control.etf_catalog_sync_state (
  singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
  last_success_at timestamptz,
  last_count integer NOT NULL DEFAULT 0 CHECK(last_count >= 0),
  updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO control.etf_catalog_sync_state(singleton) VALUES(true)
  ON CONFLICT(singleton) DO NOTHING;
GRANT SELECT, UPDATE ON control.etf_catalog_sync_state TO janus_web_control;
GRANT SELECT ON control.etf_catalog_sync_state TO janus_private_api;

CREATE OR REPLACE FUNCTION control.register_verified_etf(
  p_symbol text, p_name text, p_market text, p_listed_on date
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, control
AS $$
DECLARE
  prior_kind text;
BEGIN
  IF p_symbol !~ '^0[0-9A-Z]{3,7}$'
    OR p_market NOT IN ('TWSE', 'TPEX')
    OR p_name IS NULL OR length(btrim(p_name)) NOT BETWEEN 1 AND 100
    OR p_listed_on IS NULL OR p_listed_on > current_date OR p_listed_on < DATE '1990-01-01'
  THEN
    RAISE EXCEPTION 'invalid official ETF identity' USING ERRCODE = '22023';
  END IF;

  SELECT instrument_kind INTO prior_kind
  FROM control.official_instrument_identity_provenance
  WHERE symbol=p_symbol;
  IF prior_kind IS NOT NULL AND prior_kind NOT IN ('ETF','BOND_ETF') THEN
    RAISE EXCEPTION 'identity conflicts with non ETF instrument'
      USING ERRCODE = '23514';
  END IF;

  INSERT INTO control.stock_master(symbol, name, market, enabled, listing_status)
    VALUES(p_symbol, btrim(p_name), p_market, true, 'listed')
    ON CONFLICT(symbol) DO UPDATE
      SET name=EXCLUDED.name, market=EXCLUDED.market, updated_at=now()
      -- Never re-enable a manually disabled instrument.
      WHERE control.stock_master.symbol ~ '^0[0-9A-Z]{3,7}$';

  INSERT INTO control.official_instrument_identity_provenance
    (symbol, source_id, source_url, listed_on, verified_on, instrument_kind)
  VALUES
    (p_symbol, 'twse_isin_etf',
     'https://isin.twse.com.tw/isin/class_main.jsp',
     p_listed_on, current_date, coalesce(prior_kind, 'ETF'))
  ON CONFLICT(symbol) DO UPDATE
    SET source_id=EXCLUDED.source_id,source_url=EXCLUDED.source_url,
        listed_on=EXCLUDED.listed_on,verified_on=EXCLUDED.verified_on,
        instrument_kind=EXCLUDED.instrument_kind;
  RETURN true;
END;
$$;
REVOKE ALL ON FUNCTION control.register_verified_etf(text,text,text,date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION control.register_verified_etf(text,text,text,date)
  TO janus_private_api, janus_web_control;

-- No grants to public API; model research universe remains untouched.
INSERT INTO control.schema_migrations(version) VALUES
  ('075_etf_tradeable_catalog') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
