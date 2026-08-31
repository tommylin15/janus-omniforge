SET ROLE janus_control;
SET search_path = control, public;
UPDATE collection_configs
SET source_ids = '["taiex","tpex-benchmark","twse","mops","finmind"]'::jsonb
WHERE config_id = 'first-batch';
INSERT INTO schema_migrations(version) VALUES ('012_first_batch_source_ids') ON CONFLICT (version) DO NOTHING;
RESET ROLE;
