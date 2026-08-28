-- Bounded Admin control-plane settings with immutable audit metadata.
SET search_path = control, public;
CREATE TABLE IF NOT EXISTS admin_settings (
    setting_key text PRIMARY KEY,
    value_json jsonb NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text NOT NULL CHECK (length(trim(updated_by)) > 0)
);
CREATE TABLE IF NOT EXISTS admin_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action text NOT NULL,
    resource text NOT NULL,
    resource_key text NOT NULL,
    actor text NOT NULL,
    detail_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS admin_audit_recent_idx ON admin_audit (created_at DESC);
INSERT INTO schema_migrations(version) VALUES ('006_admin_settings_audit') ON CONFLICT (version) DO NOTHING;
RESET ROLE;
