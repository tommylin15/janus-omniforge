\set ON_ERROR_STOP on
BEGIN;
-- Execute with the existing migration bootstrap identity; no password changes.
ALTER TABLE private.watchlist ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'C' CHECK(tier IN ('A','B','C'));
ALTER TABLE private.watchlist ADD COLUMN IF NOT EXISTS tier_confirmed boolean NOT NULL DEFAULT false;
ALTER TABLE private.watchlist ADD COLUMN IF NOT EXISTS sync_locked boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS private.personal_strategy_state (
 user_id uuid PRIMARY KEY REFERENCES private.users(user_id) ON DELETE CASCADE,
 active_version uuid, paused boolean NOT NULL DEFAULT false, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS private.personal_strategies (
 version_id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES private.users(user_id) ON DELETE CASCADE,
 week_start date NOT NULL, rules jsonb NOT NULL, markdown text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,week_start)
);
CREATE TABLE IF NOT EXISTS private.personal_research_requests (
 request_id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES private.users(user_id) ON DELETE CASCADE,
 kind text NOT NULL CHECK(kind IN ('strategy','premarket','intraday','postmarket','saturday')),
 period_start date NOT NULL, idempotency_key text NOT NULL, input_hash text NOT NULL,
 status text NOT NULL CHECK(status IN ('QUEUED','RUNNING','READY','PARTIAL','FAILED')),
 input_json jsonb NOT NULL, checkpoint jsonb NOT NULL DEFAULT '{}',
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 2),
 lease_token uuid, lease_until timestamptz, safe_error text, model text,
 sync_receipt jsonb NOT NULL DEFAULT '{}',
 requested_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
 UNIQUE(user_id,idempotency_key), UNIQUE(user_id,kind,period_start)
);
CREATE TABLE IF NOT EXISTS private.personal_reports (
 report_id uuid PRIMARY KEY REFERENCES private.personal_research_requests(request_id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES private.users(user_id) ON DELETE CASCADE,
 kind text NOT NULL CHECK(kind IN ('premarket','intraday','postmarket','saturday')),
 strategy_version uuid NOT NULL REFERENCES private.personal_strategies(version_id),
 status text NOT NULL CHECK(status IN ('READY','PARTIAL')), markdown text NOT NULL,
 sources jsonb NOT NULL, sync_result jsonb NOT NULL, model text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS personal_report_history ON private.personal_reports(user_id,kind,created_at DESC);
CREATE TABLE IF NOT EXISTS private.personal_strategy_seeds (
 user_id uuid PRIMARY KEY REFERENCES private.users(user_id) ON DELETE CASCADE,
 documents jsonb NOT NULL, content_hash text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON private.personal_strategy_state,private.personal_strategies,private.personal_research_requests,
 private.personal_reports,private.personal_strategy_seeds FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE,DELETE ON private.personal_strategy_state,private.personal_strategies,
 private.personal_research_requests,private.personal_reports,private.personal_strategy_seeds TO janus_private_api;
GRANT DELETE ON private.personal_strategy_state,private.personal_strategies,
 private.personal_research_requests,private.personal_reports,private.personal_strategy_seeds TO janus_private_pipeline;
INSERT INTO control.schema_migrations(version) VALUES ('071_personal_strategy') ON CONFLICT DO NOTHING;
COMMIT;
