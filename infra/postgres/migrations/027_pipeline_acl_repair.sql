\set ON_ERROR_STOP on

-- Repair: ensure janus_private_pipeline has SELECT on private.mcp_oauth_codes.
-- DELETE ... WHERE user_id=%s requires SELECT to evaluate the predicate.
-- Migration 026 granted SELECT,DELETE but the apply script had a shell bug
-- that caused the second psql command to run on the host instead of the
-- container, so the grant may be missing on existing dev databases.
GRANT SELECT, DELETE ON private.mcp_oauth_codes TO janus_private_pipeline;

INSERT INTO control.schema_migrations(version)
VALUES ('027_pipeline_acl_repair')
ON CONFLICT(version) DO NOTHING;
