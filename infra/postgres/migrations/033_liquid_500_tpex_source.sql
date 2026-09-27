\\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE janus_control;

UPDATE control.collection_configs AS config
SET source_ids = (
    SELECT jsonb_agg(DISTINCT source_id ORDER BY source_id)
    FROM jsonb_array_elements_text(config.source_ids || '["tpex"]'::jsonb) AS sources(source_id)
)
WHERE config_id = 'first-batch';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM control.collection_configs
        WHERE config_id = 'first-batch' AND source_ids ? 'tpex'
    ) THEN
        RAISE EXCEPTION 'TPEx market-volume source is not enabled';
    END IF;
END;
$$;

INSERT INTO control.schema_migrations(version)
VALUES ('033_liquid_500_tpex_source')
ON CONFLICT (version) DO NOTHING;
COMMIT;
