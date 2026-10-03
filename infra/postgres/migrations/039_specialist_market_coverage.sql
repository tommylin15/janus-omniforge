\set ON_ERROR_STOP on
BEGIN;
-- Expose only the already approved public market pool. No private-table grants.
CREATE OR REPLACE FUNCTION control.specialist_market_symbols(p_as_of date)
RETURNS TABLE(symbol text, membership_version bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=control,pg_catalog AS $$
    SELECT m.symbol, m.version
      FROM control.liquid_500_members m
     WHERE m.version=(
         SELECT v.version FROM control.liquid_500_versions v
          WHERE v.effective_from < ((p_as_of+1)::timestamp AT TIME ZONE 'Asia/Taipei')
          ORDER BY v.effective_from DESC,v.version DESC LIMIT 1)
     ORDER BY m.rank,m.symbol
$$;
ALTER FUNCTION control.specialist_market_symbols(date) OWNER TO janus_control;
REVOKE ALL ON FUNCTION control.specialist_market_symbols(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION control.specialist_market_symbols(date) TO janus_mart_publication;
INSERT INTO control.schema_migrations(version) VALUES ('039_specialist_market_coverage') ON CONFLICT DO NOTHING;
COMMIT;
