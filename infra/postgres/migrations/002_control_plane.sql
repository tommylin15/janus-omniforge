\set ON_ERROR_STOP on
SET ROLE janus_control;
SET search_path TO control;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stock_master (
    symbol text PRIMARY KEY CHECK (symbol ~ '^[A-Z0-9_-]{1,20}$'),
    name text NOT NULL CHECK (btrim(name) <> ''),
    market text NOT NULL CHECK (market IN ('TWSE', 'TPEX')),
    enabled boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collection_configs (
    config_id text PRIMARY KEY,
    dataset_id text NOT NULL,
    source_ids jsonb NOT NULL CHECK (jsonb_typeof(source_ids) = 'array'),
    expected_fields jsonb NOT NULL CHECK (jsonb_typeof(expected_fields) = 'array'),
    market text NOT NULL CHECK (market IN ('TWSE', 'TPEX')),
    enabled boolean NOT NULL DEFAULT true,
    collection_enabled boolean NOT NULL DEFAULT true,
    analysis_enabled boolean NOT NULL DEFAULT true,
    lookback_days integer NOT NULL CHECK (lookback_days >= 0),
    overlap_days integer NOT NULL CHECK (overlap_days >= 0),
    full_refresh_interval_days integer NOT NULL CHECK (full_refresh_interval_days >= 0),
    batch_scope text NOT NULL CHECK (batch_scope IN ('market', 'symbol'))
);

CREATE TABLE IF NOT EXISTS collection_symbols (
    config_id text NOT NULL REFERENCES collection_configs(config_id) ON DELETE RESTRICT,
    symbol text NOT NULL REFERENCES stock_master(symbol) ON DELETE RESTRICT,
    PRIMARY KEY (config_id, symbol)
);

CREATE TABLE IF NOT EXISTS executions (
    execution_id uuid PRIMARY KEY,
    trace_id uuid NOT NULL,
    config_id text NOT NULL REFERENCES collection_configs(config_id) ON DELETE RESTRICT,
    trigger_type text NOT NULL CHECK (trigger_type IN ('collection', 'analysis')),
    status text NOT NULL CHECK (status IN ('queued','running','succeeded','partial','failed','retrying')),
    requested_symbols jsonb NOT NULL CHECK (jsonb_typeof(requested_symbols) = 'array'),
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    error_code text,
    claimed_by text,
    claimed_until timestamptz
);
CREATE INDEX IF NOT EXISTS executions_recent_idx ON executions (requested_at DESC);
CREATE INDEX IF NOT EXISTS executions_claim_idx ON executions (status, claimed_until, requested_at)
    WHERE status IN ('queued', 'retrying');

CREATE TABLE IF NOT EXISTS execution_symbols (
    execution_id uuid NOT NULL REFERENCES executions(execution_id) ON DELETE CASCADE,
    symbol text NOT NULL REFERENCES stock_master(symbol) ON DELETE RESTRICT,
    PRIMARY KEY (execution_id, symbol)
);

CREATE TABLE IF NOT EXISTS execution_items (
    execution_id uuid NOT NULL REFERENCES executions(execution_id) ON DELETE CASCADE,
    item_key text NOT NULL,
    source_id text NOT NULL,
    dataset_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('success','empty','partial','fallback','stale','unavailable','schema_drift','failed')),
    rows_received integer NOT NULL DEFAULT 0 CHECK (rows_received >= 0),
    retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    cache_hit boolean NOT NULL DEFAULT false,
    is_fallback boolean NOT NULL DEFAULT false,
    error_code text,
    safe_message text,
    PRIMARY KEY (execution_id, item_key)
);

-- Payload remains in GCS; PostgreSQL stores metadata only.
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key text PRIMARY KEY,
    source_id text NOT NULL,
    dataset_id text NOT NULL,
    payload_uri text NOT NULL CHECK (payload_uri LIKE 'gs://%'),
    content_hash text NOT NULL,
    fetched_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    observed_at timestamptz,
    state text NOT NULL CHECK (state IN ('success','empty','partial','fallback','stale','unavailable','schema_drift','failed')),
    CHECK (expires_at > fetched_at)
);

CREATE TABLE IF NOT EXISTS collection_cursors (
    cursor_key text PRIMARY KEY,
    last_observed_at timestamptz,
    last_success_at timestamptz
);

CREATE TABLE IF NOT EXISTS source_health (
    source_id text NOT NULL,
    dataset_id text NOT NULL,
    success_count bigint NOT NULL DEFAULT 0 CHECK (success_count >= 0),
    failure_count bigint NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
    total_latency_ms double precision NOT NULL DEFAULT 0 CHECK (total_latency_ms >= 0),
    last_fetched_at timestamptz,
    latest_observation_at timestamptz,
    last_state text,
    PRIMARY KEY (source_id, dataset_id)
);

CREATE INDEX IF NOT EXISTS response_cache_expiry_idx ON response_cache (expires_at);
CREATE INDEX IF NOT EXISTS source_health_fetched_idx ON source_health (last_fetched_at);

INSERT INTO schema_migrations(version) VALUES ('001_roles_and_schemas'), ('002_control_plane')
ON CONFLICT (version) DO NOTHING;
RESET ROLE;
