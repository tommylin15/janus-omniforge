\set ON_ERROR_STOP on

-- Passwords are supplied as psql variables by the operator. They must never
-- be committed, logged, or stored in VM metadata.
SELECT format(
    'CREATE ROLE janus_web_control LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
    :'web_control_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janus_web_control') \gexec
SELECT format(
    'CREATE ROLE janus_web_catalog LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
    :'web_catalog_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janus_web_catalog') \gexec

ALTER ROLE janus_web_control PASSWORD :'web_control_password';
ALTER ROLE janus_web_catalog PASSWORD :'web_catalog_password';
GRANT CONNECT ON DATABASE janus_control TO janus_web_control, janus_web_catalog;

GRANT USAGE ON SCHEMA control TO janus_web_control;
GRANT SELECT ON control.schema_migrations TO janus_web_control;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    control.stock_master,
    control.collection_configs,
    control.collection_symbols,
    control.executions,
    control.execution_symbols,
    control.execution_items,
    control.source_health,
    control.coverage_memberships,
    control.admin_settings,
    control.admin_audit
TO janus_web_control;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA control TO janus_web_control;
ALTER ROLE janus_web_control IN DATABASE janus_control SET statement_timeout = '15s';
ALTER ROLE janus_web_control IN DATABASE janus_control SET idle_in_transaction_session_timeout = '15s';

GRANT USAGE ON SCHEMA catalog, public TO janus_web_catalog;
GRANT SELECT ON catalog.iceberg_tables, catalog.iceberg_namespace_properties TO janus_web_catalog;
GRANT SELECT ON public.iceberg_tables, public.iceberg_namespace_properties TO janus_web_catalog;
ALTER ROLE janus_web_catalog IN DATABASE janus_control SET default_transaction_read_only = on;
ALTER ROLE janus_web_catalog IN DATABASE janus_control SET statement_timeout = '60s';
ALTER ROLE janus_web_catalog IN DATABASE janus_control SET idle_in_transaction_session_timeout = '15s';

INSERT INTO control.schema_migrations(version) VALUES ('007_web_runtime_roles')
ON CONFLICT (version) DO NOTHING;
