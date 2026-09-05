\set ON_ERROR_STOP on

SELECT format('CREATE ROLE janus_private_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'private_api_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='janus_private_api') \gexec
SELECT format('CREATE ROLE janus_private_pipeline LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'private_pipeline_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='janus_private_pipeline') \gexec
ALTER ROLE janus_private_api PASSWORD :'private_api_password';
ALTER ROLE janus_private_pipeline PASSWORD :'private_pipeline_password';
GRANT CONNECT ON DATABASE janus_control TO janus_private_api, janus_private_pipeline;

CREATE SCHEMA IF NOT EXISTS private AUTHORIZATION janus_control;
REVOKE ALL ON SCHEMA private FROM PUBLIC;

CREATE TABLE IF NOT EXISTS private.users (
    user_id uuid PRIMARY KEY,
    google_sub text NOT NULL UNIQUE,
    display_email text NOT NULL,
    ledger_version bigint NOT NULL DEFAULT 0 CHECK (ledger_version >= 0),
    change_version bigint NOT NULL DEFAULT 0 CHECK (change_version >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS private.ledger_events (
    event_id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    ledger_version bigint NOT NULL,
    record_version integer NOT NULL DEFAULT 1 CHECK (record_version > 0),
    event_action text NOT NULL CHECK (event_action IN ('ORIGINAL','REVERSAL','REPLACEMENT')),
    event_type text NOT NULL CHECK (event_type IN ('BUY','SELL','CASH_DIV','STOCK_DIV')),
    trade_date date NOT NULL,
    symbol varchar(16) NOT NULL,
    shares numeric(20,8) CHECK (shares > 0),
    price numeric(20,4) CHECK (price >= 0),
    cash_amount numeric(20,4) CHECK (cash_amount >= 0),
    fee numeric(20,4) NOT NULL DEFAULT 0 CHECK (fee >= 0),
    tax numeric(20,4) NOT NULL DEFAULT 0 CHECK (tax >= 0),
    currency char(3) NOT NULL,
    memo varchar(500),
    idempotency_key varchar(128) NOT NULL,
    reverses_event_id uuid REFERENCES private.ledger_events(event_id),
    replaces_event_id uuid REFERENCES private.ledger_events(event_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, ledger_version),
    UNIQUE (user_id, idempotency_key),
    CHECK ((event_type IN ('BUY','SELL') AND shares IS NOT NULL AND price IS NOT NULL AND cash_amount IS NULL)
        OR (event_type='CASH_DIV' AND cash_amount IS NOT NULL AND shares IS NULL AND price IS NULL)
        OR (event_type='STOCK_DIV' AND shares IS NOT NULL AND price IS NULL AND cash_amount IS NULL)),
    CHECK ((event_action='REVERSAL' AND reverses_event_id IS NOT NULL AND replaces_event_id IS NULL)
        OR (event_action='REPLACEMENT' AND replaces_event_id IS NOT NULL AND reverses_event_id IS NULL)
        OR (event_action='ORIGINAL' AND reverses_event_id IS NULL AND replaces_event_id IS NULL))
);

CREATE TABLE IF NOT EXISTS private.note_index (
    note_id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    current_version integer NOT NULL CHECK (current_version > 0),
    symbol varchar(16),
    trade_event_id uuid,
    needs_follow_up boolean NOT NULL DEFAULT false,
    artifact_ref text NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS private.watchlist (
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    symbol varchar(16) NOT NULL,
    target_price numeric(20,4) CHECK (target_price >= 0),
    sort_order integer NOT NULL CHECK (sort_order >= 0),
    active boolean NOT NULL DEFAULT true,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    idempotency_key varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS private.change_log (
    change_id bigserial PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    change_version bigint NOT NULL,
    kind varchar(32) NOT NULL,
    entity_id text NOT NULL,
    artifact_ref text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, change_version)
);

CREATE TABLE IF NOT EXISTS private.mutation_keys (
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    idempotency_key varchar(128) NOT NULL,
    kind varchar(32) NOT NULL,
    entity_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS private.pipeline_checkpoints (
    pipeline_name varchar(64) PRIMARY KEY,
    change_id bigint NOT NULL CHECK (change_id >= 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS private.deletion_requests (
    request_id uuid PRIMARY KEY,
    user_id uuid NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','COMPLETED')),
    requested_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS ledger_user_date_idx ON private.ledger_events(user_id, trade_date DESC, ledger_version DESC);
CREATE INDEX IF NOT EXISTS ledger_user_symbol_date_idx ON private.ledger_events(user_id, symbol, trade_date DESC);
CREATE INDEX IF NOT EXISTS notes_user_updated_idx ON private.note_index(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS watchlist_user_active_order_idx ON private.watchlist(user_id, active, sort_order);
CREATE INDEX IF NOT EXISTS changes_user_version_idx ON private.change_log(user_id, change_version);

GRANT USAGE ON SCHEMA private TO janus_private_api, janus_private_pipeline;
GRANT SELECT, INSERT, UPDATE ON private.users TO janus_private_api;
GRANT SELECT, INSERT ON private.ledger_events, private.change_log, private.mutation_keys TO janus_private_api;
GRANT SELECT, INSERT, UPDATE ON private.note_index, private.watchlist TO janus_private_api;
GRANT SELECT, INSERT ON private.deletion_requests TO janus_private_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA private TO janus_private_api;
GRANT SELECT ON private.users, private.ledger_events, private.note_index, private.watchlist, private.change_log, private.mutation_keys TO janus_private_pipeline;
GRANT SELECT, INSERT, UPDATE ON private.pipeline_checkpoints TO janus_private_pipeline;
GRANT SELECT, UPDATE, DELETE ON private.deletion_requests TO janus_private_pipeline;
GRANT DELETE ON private.users, private.ledger_events, private.note_index, private.watchlist, private.change_log, private.mutation_keys TO janus_private_pipeline;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA private TO janus_private_pipeline;
GRANT USAGE ON SCHEMA catalog, public TO janus_private_api, janus_private_pipeline;
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.iceberg_tables, catalog.iceberg_namespace_properties TO janus_private_api, janus_private_pipeline;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.iceberg_tables, public.iceberg_namespace_properties TO janus_private_api, janus_private_pipeline;

ALTER ROLE janus_private_api IN DATABASE janus_control SET statement_timeout='15s';
ALTER ROLE janus_private_pipeline IN DATABASE janus_control SET statement_timeout='60s';
ALTER ROLE janus_private_api IN DATABASE janus_control SET idle_in_transaction_session_timeout='15s';
ALTER ROLE janus_private_pipeline IN DATABASE janus_control SET idle_in_transaction_session_timeout='15s';

INSERT INTO control.schema_migrations(version) VALUES ('014_private_workspace') ON CONFLICT(version) DO NOTHING;
