\set ON_ERROR_STOP on

BEGIN;

GRANT USAGE ON SCHEMA control TO janus_publication;
GRANT SELECT (symbol, enabled) ON control.stock_master TO janus_publication;

SET ROLE janus_publication;

CREATE OR REPLACE VIEW publication.enabled_stock_symbols
WITH (security_barrier = true) AS
SELECT upper(symbol) AS symbol
FROM control.stock_master
WHERE enabled = true;

RESET ROLE;

GRANT SELECT ON publication.enabled_stock_symbols TO janus_public_api;

INSERT INTO control.schema_migrations(version) VALUES ('023_public_stock_index')
ON CONFLICT (version) DO NOTHING;

COMMIT;
