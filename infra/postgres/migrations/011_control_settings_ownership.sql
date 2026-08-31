SET search_path = control, public;
ALTER TABLE admin_settings OWNER TO janus_control;
ALTER TABLE admin_audit OWNER TO janus_control;
ALTER SEQUENCE admin_audit_audit_id_seq OWNER TO janus_control;
INSERT INTO schema_migrations(version) VALUES ('011_control_settings_ownership') ON CONFLICT (version) DO NOTHING;
RESET ROLE;
