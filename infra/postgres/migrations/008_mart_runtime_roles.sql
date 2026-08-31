\set ON_ERROR_STOP on

-- Passwords are supplied by the operator and never stored in VM metadata.
SELECT format(
    'CREATE ROLE janus_mart_catalog LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
    :'mart_catalog_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janus_mart_catalog') \gexec
SELECT format(
    'CREATE ROLE janus_mart_publication LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
    :'mart_publication_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janus_mart_publication') \gexec

ALTER ROLE janus_mart_catalog PASSWORD :'mart_catalog_password';
ALTER ROLE janus_mart_publication PASSWORD :'mart_publication_password';
GRANT CONNECT ON DATABASE janus_control TO janus_mart_catalog, janus_mart_publication;

GRANT USAGE ON SCHEMA catalog, public TO janus_mart_catalog;
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.iceberg_tables, catalog.iceberg_namespace_properties TO janus_mart_catalog;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.iceberg_tables, public.iceberg_namespace_properties TO janus_mart_catalog;

GRANT USAGE ON SCHEMA publication TO janus_mart_publication;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA publication TO janus_mart_publication;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA publication TO janus_mart_publication;
ALTER DEFAULT PRIVILEGES FOR ROLE janus_publication IN SCHEMA publication
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO janus_mart_publication;
ALTER DEFAULT PRIVILEGES FOR ROLE janus_publication IN SCHEMA publication
    GRANT USAGE, SELECT ON SEQUENCES TO janus_mart_publication;

ALTER ROLE janus_mart_catalog IN DATABASE janus_control SET statement_timeout = '60s';
ALTER ROLE janus_mart_catalog IN DATABASE janus_control SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE janus_mart_publication IN DATABASE janus_control SET statement_timeout = '30s';
ALTER ROLE janus_mart_publication IN DATABASE janus_control SET idle_in_transaction_session_timeout = '15s';

INSERT INTO control.schema_migrations(version) VALUES ('008_mart_runtime_roles')
ON CONFLICT (version) DO NOTHING;
