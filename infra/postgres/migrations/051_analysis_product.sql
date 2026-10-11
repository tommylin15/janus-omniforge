\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- Rebuildable serving payloads only; canonical artifacts remain in Mart/GCS.
CREATE TABLE IF NOT EXISTS private.specialist_product (
    execution_id uuid NOT NULL,
    symbol varchar(20) NOT NULL,
    analysis_as_of date NOT NULL,
    content_hash varchar(71) NOT NULL,
    payload_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(execution_id,symbol)
);
CREATE INDEX IF NOT EXISTS specialist_product_latest_idx
ON private.specialist_product(symbol,analysis_as_of DESC,created_at DESC);

CREATE TABLE IF NOT EXISTS private.market_screening_product (
    analysis_as_of date NOT NULL,
    core_snapshot_id text NOT NULL,
    symbol varchar(20) NOT NULL,
    content_hash varchar(71) NOT NULL,
    payload_json jsonb NOT NULL,
    PRIMARY KEY(analysis_as_of,core_snapshot_id,symbol)
);

CREATE TABLE IF NOT EXISTS private.ceo_capability_revisions (
    user_id uuid NOT NULL,
    version bigint NOT NULL CHECK(version > 0),
    enabled boolean NOT NULL,
    daily_quota integer NOT NULL CHECK(daily_quota BETWEEN 0 AND 20),
    cooldown_seconds integer NOT NULL CHECK(cooldown_seconds BETWEEN 60 AND 86400),
    actor varchar(254) NOT NULL,
    reason varchar(500) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(user_id,version)
);
CREATE TABLE IF NOT EXISTS private.ceo_profile_revisions (
    profile_id varchar(40) NOT NULL,
    version bigint NOT NULL CHECK(version > 0),
    approved boolean NOT NULL,
    route_json jsonb NOT NULL,
    actor varchar(254) NOT NULL,
    reason varchar(500) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(profile_id,version)
);
-- Start disabled; migrations never grant capability or provider approval.
INSERT INTO private.ceo_profile_revisions(profile_id,version,approved,route_json,actor,reason)
VALUES ('default',1,false,'{"providers":["codex_cli","openrouter","gemini"],"version":1}',
        'migration:051','Provider/auth/free-tier live gate 尚未驗收')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS private.ceo_requests (
    request_id uuid PRIMARY KEY,
    user_id uuid NOT NULL,
    symbol varchar(20) NOT NULL,
    profile_id varchar(40) NOT NULL,
    profile_version bigint NOT NULL,
    route_json jsonb NOT NULL,
    baseline_json jsonb NOT NULL,
    baseline_hash varchar(71) NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    status varchar(24) NOT NULL CHECK(status IN
        ('QUEUED','RUNNING','CANCEL_REQUESTED','SUCCEEDED','PARTIAL','BLOCKED','FAILED','CANCELLED')),
    lease_token uuid,
    worker_execution text,
    report_json jsonb,
    report_hash varchar(71),
    audit_json jsonb NOT NULL DEFAULT '{}',
    safe_reason varchar(100),
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    UNIQUE(user_id,idempotency_key),
    CHECK ((report_json IS NULL)=(report_hash IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS ceo_one_active_owner_idx ON private.ceo_requests(user_id)
WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED');
CREATE INDEX IF NOT EXISTS ceo_owner_history_idx ON private.ceo_requests(user_id,symbol,requested_at DESC);

CREATE OR REPLACE FUNCTION control.ceo_immutable_terminal() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status IN ('SUCCEEDED','PARTIAL','BLOCKED','FAILED','CANCELLED') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'CEO terminal execution is immutable';
    END IF;
    IF NEW.status IN ('SUCCEEDED','PARTIAL','BLOCKED','FAILED','CANCELLED') THEN
        NEW.finished_at := COALESCE(NEW.finished_at,now());
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION control.ceo_immutable_terminal() FROM PUBLIC;
DROP TRIGGER IF EXISTS ceo_immutable_terminal ON private.ceo_requests;
CREATE TRIGGER ceo_immutable_terminal BEFORE UPDATE ON private.ceo_requests
FOR EACH ROW EXECUTE FUNCTION control.ceo_immutable_terminal();

-- Worker sees only explicit CEO requests and deidentified baseline artifacts,
-- never private.users, ledger_events, current_positions or notes.
GRANT USAGE ON SCHEMA private TO janus_mart_publication;
GRANT SELECT,INSERT ON private.specialist_product TO janus_mart_publication;
GRANT SELECT,INSERT ON private.market_screening_product TO janus_mart_publication;
GRANT SELECT ON private.market_screening_product TO janus_private_api;
GRANT SELECT ON private.specialist_product TO janus_private_api;
GRANT SELECT,INSERT ON private.ceo_capability_revisions,private.ceo_profile_revisions TO janus_private_api;
GRANT SELECT,INSERT ON private.ceo_requests TO janus_private_api;
GRANT UPDATE(status,safe_reason) ON private.ceo_requests TO janus_private_api;
GRANT SELECT ON private.ceo_requests,private.ceo_capability_revisions,private.ceo_profile_revisions TO janus_mart_publication;
GRANT UPDATE(status,lease_token,worker_execution,started_at,finished_at,report_json,report_hash,audit_json,safe_reason)
ON private.ceo_requests TO janus_mart_publication;

-- PHASE: acceptance
SELECT
    has_table_privilege('janus_private_api','private.specialist_product','SELECT'),
    has_table_privilege('janus_mart_publication','private.specialist_product','INSERT'),
    has_table_privilege('janus_private_api','private.ceo_requests','INSERT'),
    has_column_privilege('janus_mart_publication','private.ceo_requests','report_json','UPDATE'),
    NOT has_table_privilege('janus_public_api','private.ceo_requests','SELECT'),
    NOT has_table_privilege('janus_mart_publication','private.ledger_events','SELECT'),
    NOT has_table_privilege('janus_mart_publication','private.current_positions','SELECT');
INSERT INTO control.schema_migrations(version) VALUES ('051_analysis_product') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
