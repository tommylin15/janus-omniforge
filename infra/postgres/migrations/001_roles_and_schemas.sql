\set ON_ERROR_STOP on

-- Password variables are supplied by the out-of-band operator. Never commit
-- values or pass them through Terraform/startup metadata.
CREATE ROLE janus_control LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE janus_catalog LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE janus_publication LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE janus_audit LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

ALTER ROLE janus_control PASSWORD :'control_password';
ALTER ROLE janus_catalog PASSWORD :'catalog_password';
ALTER ROLE janus_publication PASSWORD :'publication_password';
ALTER ROLE janus_audit PASSWORD :'audit_password';

CREATE DATABASE janus_control;
REVOKE ALL ON DATABASE janus_control FROM PUBLIC;
GRANT CONNECT ON DATABASE janus_control TO janus_control, janus_catalog, janus_publication, janus_audit;

\connect janus_control

CREATE SCHEMA control AUTHORIZATION janus_control;
CREATE SCHEMA catalog AUTHORIZATION janus_catalog;
CREATE SCHEMA publication AUTHORIZATION janus_publication;
CREATE SCHEMA audit AUTHORIZATION janus_audit;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON DATABASE janus_control FROM PUBLIC;

