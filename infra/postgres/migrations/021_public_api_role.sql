\set ON_ERROR_STOP on

SELECT format(
    'CREATE ROLE janus_public_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
    :'web_publication_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janus_public_api') \gexec

ALTER ROLE janus_public_api PASSWORD :'web_publication_password';
GRANT CONNECT ON DATABASE janus_control TO janus_public_api;
GRANT USAGE ON SCHEMA publication TO janus_public_api;
GRANT SELECT ON publication.publishable_mart_reports TO janus_public_api;
REVOKE ALL ON publication.mart_report_index, publication.mart_report_outbox FROM janus_public_api;
ALTER ROLE janus_public_api IN DATABASE janus_control SET default_transaction_read_only = on;
ALTER ROLE janus_public_api IN DATABASE janus_control SET statement_timeout = '5s';
ALTER ROLE janus_public_api IN DATABASE janus_control SET idle_in_transaction_session_timeout = '5s';

INSERT INTO control.schema_migrations(version) VALUES ('021_public_api_role')
ON CONFLICT (version) DO NOTHING;
