\set ON_ERROR_STOP on
SET ROLE janus_control;
SET search_path TO control;

-- Keep the aggregate table bounded. Coverage dimensions are stored as
-- metadata, never raw upstream payloads.
ALTER TABLE source_health
    ADD COLUMN IF NOT EXISTS expected_symbols bigint NOT NULL DEFAULT 0 CHECK (expected_symbols >= 0),
    ADD COLUMN IF NOT EXISTS received_symbols bigint NOT NULL DEFAULT 0 CHECK (received_symbols >= 0),
    ADD COLUMN IF NOT EXISTS cache_hits bigint NOT NULL DEFAULT 0 CHECK (cache_hits >= 0),
    ADD COLUMN IF NOT EXISTS fallback_count bigint NOT NULL DEFAULT 0 CHECK (fallback_count >= 0),
    ADD COLUMN IF NOT EXISTS schema_drift_count bigint NOT NULL DEFAULT 0 CHECK (schema_drift_count >= 0),
    ADD COLUMN IF NOT EXISTS coverage_tier text NOT NULL DEFAULT 'market_wide',
    ADD COLUMN IF NOT EXISTS last_cache_age_seconds double precision;

ALTER TABLE source_health
    DROP CONSTRAINT IF EXISTS source_health_coverage_tier_check,
    ADD CONSTRAINT source_health_coverage_tier_check CHECK (coverage_tier IN ('market_wide','core_focus','market_macro'));

CREATE INDEX IF NOT EXISTS source_health_tier_fetched_idx ON source_health (coverage_tier, last_fetched_at);
INSERT INTO schema_migrations(version) VALUES ('005_source_health_telemetry')
ON CONFLICT (version) DO NOTHING;
RESET ROLE;
