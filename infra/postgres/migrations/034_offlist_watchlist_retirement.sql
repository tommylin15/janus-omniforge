BEGIN;

GRANT SELECT ON control.liquid_500_versions, control.liquid_500_members TO janus_private_pipeline;
GRANT UPDATE ON private.watchlist, private.users TO janus_private_pipeline;
GRANT INSERT ON private.change_log TO janus_private_pipeline;
GRANT EXECUTE ON FUNCTION control.record_deep_tracking_demand(text) TO janus_private_pipeline;

INSERT INTO control.schema_migrations(version) VALUES ('034_offlist_watchlist_retirement')
ON CONFLICT (version) DO NOTHING;

COMMIT;
