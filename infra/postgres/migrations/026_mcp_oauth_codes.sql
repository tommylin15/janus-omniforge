\set ON_ERROR_STOP on

GRANT REFERENCES ON private.users TO janus_control;
SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS private.mcp_oauth_codes (
    code_hash char(64) PRIMARY KEY CHECK (code_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    client_id text NOT NULL CHECK (length(client_id) <= 512),
    redirect_uri text NOT NULL CHECK (length(redirect_uri) <= 512),
    resource text NOT NULL CHECK (length(resource) <= 512),
    scope text NOT NULL CHECK (length(scope) <= 512),
    code_challenge text NOT NULL CHECK (length(code_challenge) BETWEEN 43 AND 128),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz
);

CREATE INDEX IF NOT EXISTS mcp_oauth_codes_expiry_idx ON private.mcp_oauth_codes(expires_at);
REVOKE ALL ON private.mcp_oauth_codes FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON private.mcp_oauth_codes TO janus_private_api;
GRANT SELECT, DELETE ON private.mcp_oauth_codes TO janus_private_pipeline;

INSERT INTO control.schema_migrations(version) VALUES ('026_mcp_oauth_codes') ON CONFLICT(version) DO NOTHING;

RESET ROLE;
REVOKE REFERENCES ON private.users FROM janus_control;
