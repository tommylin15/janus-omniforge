SET search_path = control, public;
ALTER TABLE executions ADD COLUMN IF NOT EXISTS request_options jsonb NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(request_options) = 'object');
INSERT INTO schema_migrations(version) VALUES ('010_execution_runtime_options') ON CONFLICT (version) DO NOTHING;
RESET ROLE;
