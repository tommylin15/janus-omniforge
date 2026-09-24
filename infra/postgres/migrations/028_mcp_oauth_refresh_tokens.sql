\set ON_ERROR_STOP on

GRANT REFERENCES ON private.users TO janus_control;
SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS private.mcp_oauth_refresh_tokens (
    token_hash char(64) PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    client_id text NOT NULL CHECK (length(client_id) <= 512),
    resource text NOT NULL CHECK (length(resource) <= 512),
    scope text NOT NULL CHECK (length(scope) <= 512),
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz
);

CREATE INDEX IF NOT EXISTS mcp_oauth_refresh_tokens_user_idx
    ON private.mcp_oauth_refresh_tokens(user_id);
REVOKE ALL ON private.mcp_oauth_refresh_tokens FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON private.mcp_oauth_refresh_tokens TO janus_private_api;
GRANT SELECT, DELETE ON private.mcp_oauth_refresh_tokens TO janus_private_pipeline;

INSERT INTO control.schema_migrations(version) VALUES ('028_mcp_oauth_refresh_tokens') ON CONFLICT(version) DO NOTHING;

RESET ROLE;
REVOKE REFERENCES ON private.users FROM janus_control;
