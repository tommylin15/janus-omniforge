BEGIN;

GRANT USAGE ON SCHEMA control TO janus_private_api, janus_private_pipeline;
GRANT SELECT ON control.stock_master TO janus_private_api, janus_private_pipeline;

COMMIT;
