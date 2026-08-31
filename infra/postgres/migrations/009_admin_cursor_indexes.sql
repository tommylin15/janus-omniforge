\set ON_ERROR_STOP on
SET ROLE janus_control;
SET search_path TO control;

CREATE INDEX IF NOT EXISTS executions_admin_page_idx
    ON executions (requested_at DESC, execution_id DESC);

INSERT INTO schema_migrations(version) VALUES ('009_admin_cursor_indexes')
ON CONFLICT (version) DO NOTHING;
RESET ROLE;
