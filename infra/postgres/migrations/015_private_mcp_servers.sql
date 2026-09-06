\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS private.mcp_servers (
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    server_id varchar(40) NOT NULL,
    config_ref varchar(64) NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    tool_grants text[] NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, server_id),
    CHECK (cardinality(tool_grants) <= 128)
);

CREATE INDEX IF NOT EXISTS mcp_servers_user_enabled_idx ON private.mcp_servers(user_id, enabled, server_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON private.mcp_servers TO janus_private_api;
GRANT SELECT, DELETE ON private.mcp_servers TO janus_private_pipeline;

INSERT INTO control.schema_migrations(version) VALUES ('015_private_mcp_servers') ON CONFLICT(version) DO NOTHING;
