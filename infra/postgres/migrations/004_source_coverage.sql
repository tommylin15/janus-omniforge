\set ON_ERROR_STOP on
SET ROLE janus_control;
SET search_path TO control;

ALTER TABLE collection_configs
    ADD COLUMN IF NOT EXISTS coverage_tier text NOT NULL DEFAULT 'market_wide',
    ADD COLUMN IF NOT EXISTS cadence text NOT NULL DEFAULT 'daily',
    ADD COLUMN IF NOT EXISTS scope text NOT NULL DEFAULT 'market',
    ADD COLUMN IF NOT EXISTS authorization_status text NOT NULL DEFAULT 'official',
    ADD COLUMN IF NOT EXISTS retention_class text NOT NULL DEFAULT 'core_standard',
    ADD COLUMN IF NOT EXISTS contains_pii boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS republish_allowed boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS max_symbols integer NOT NULL DEFAULT 50;

ALTER TABLE stock_master
    ADD COLUMN IF NOT EXISTS listing_status text NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS effective_from timestamptz NOT NULL DEFAULT now();

ALTER TABLE stock_master
    DROP CONSTRAINT IF EXISTS stock_master_listing_status_check,
    ADD CONSTRAINT stock_master_listing_status_check CHECK (listing_status IN ('listed','suspended','delisted','unknown'));

ALTER TABLE collection_configs
    DROP CONSTRAINT IF EXISTS collection_configs_coverage_tier_check,
    ADD CONSTRAINT collection_configs_coverage_tier_check CHECK (coverage_tier IN ('market_wide','core_focus','market_macro')),
    DROP CONSTRAINT IF EXISTS collection_configs_authorization_status_check,
    ADD CONSTRAINT collection_configs_authorization_status_check CHECK (authorization_status IN ('official','approved_fallback','candidate','blocked')),
    DROP CONSTRAINT IF EXISTS collection_configs_max_symbols_check,
    ADD CONSTRAINT collection_configs_max_symbols_check CHECK (max_symbols BETWEEN 1 AND 50);

CREATE TABLE IF NOT EXISTS coverage_memberships (
    membership_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    coverage_tier text NOT NULL CHECK (coverage_tier IN ('market_wide','core_focus','market_macro')),
    symbol text NOT NULL REFERENCES stock_master(symbol) ON DELETE RESTRICT,
    effective_from timestamptz NOT NULL,
    effective_to timestamptz,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    owner text NOT NULL CHECK (btrim(owner) <> ''),
    UNIQUE (coverage_tier, symbol, effective_from),
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);
CREATE INDEX IF NOT EXISTS coverage_memberships_lookup_idx ON coverage_memberships(coverage_tier, symbol, effective_from, effective_to);

INSERT INTO control.schema_migrations(version) VALUES ('004_source_coverage')
ON CONFLICT (version) DO NOTHING;
RESET ROLE;
