\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
ALTER TABLE control.collection_cursors ADD COLUMN IF NOT EXISTS coverage_json jsonb;
CREATE TABLE IF NOT EXISTS control.market_universe_versions (
    version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    effective_from timestamptz NOT NULL UNIQUE,
    source_snapshot jsonb NOT NULL CHECK (jsonb_typeof(source_snapshot)='object'),
    membership_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS control.market_universe_members (
    version bigint NOT NULL REFERENCES control.market_universe_versions(version),
    symbol text NOT NULL REFERENCES control.stock_master(symbol),
    market text NOT NULL CHECK (market IN ('TWSE','TPEX')),
    stock_name text NOT NULL,
    PRIMARY KEY(version,symbol)
);
GRANT SELECT,INSERT ON control.market_universe_versions,control.market_universe_members TO janus_web_control;
GRANT USAGE,SELECT ON SEQUENCE control.market_universe_versions_version_seq TO janus_web_control;
GRANT SELECT ON control.market_universe_versions,control.market_universe_members TO janus_private_api;

CREATE OR REPLACE FUNCTION control.specialist_market_symbols(p_as_of date)
RETURNS TABLE(symbol text,membership_version bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=control,pg_catalog AS $$
    SELECT m.symbol,m.version FROM control.market_universe_members m
    WHERE m.version=(SELECT v.version FROM control.market_universe_versions v
        WHERE v.effective_from < ((p_as_of+1)::timestamp AT TIME ZONE 'Asia/Taipei')
        ORDER BY v.effective_from DESC,v.version DESC LIMIT 1)
    UNION ALL
    SELECT m.symbol,m.version FROM control.liquid_500_members m
    WHERE (NOT EXISTS(SELECT 1 FROM control.market_universe_versions) OR
           p_as_of < (SELECT (min(effective_from) AT TIME ZONE 'Asia/Taipei')::date FROM control.market_universe_versions))
      AND m.version=(SELECT v.version FROM control.liquid_500_versions v
        WHERE v.effective_from < ((p_as_of+1)::timestamp AT TIME ZONE 'Asia/Taipei')
        ORDER BY v.effective_from DESC,v.version DESC LIMIT 1)
    ORDER BY symbol
$$;
REVOKE ALL ON FUNCTION control.specialist_market_symbols(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION control.specialist_market_symbols(date) TO janus_mart_publication;
-- PHASE: acceptance
SELECT to_regclass('control.market_universe_versions') IS NOT NULL,
       to_regclass('control.market_universe_members') IS NOT NULL,
       has_table_privilege('janus_private_api','control.market_universe_members','SELECT'),
       NOT has_table_privilege('janus_public_api','control.market_universe_members','INSERT');
INSERT INTO control.schema_migrations(version) VALUES ('055_full_market_universe') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
