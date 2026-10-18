\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
GRANT SELECT(schema_version,as_of_date,updated_at,snapshot_id)
 ON control.home_market_snapshot TO janus_web_control;
CREATE TABLE IF NOT EXISTS private.usage_preferences (
 user_id uuid PRIMARY KEY, enabled boolean NOT NULL DEFAULT false,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS private.usage_ingest_receipts (
 user_id uuid NOT NULL, batch_id uuid NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id,batch_id)
);
CREATE INDEX IF NOT EXISTS usage_receipts_expiry ON private.usage_ingest_receipts(received_at);
CREATE TABLE IF NOT EXISTS private.usage_recent_events (
 user_id uuid NOT NULL,event_id uuid NOT NULL,session_id uuid NOT NULL,
 feature_id varchar(32) NOT NULL,event_type varchar(24) NOT NULL,action_key varchar(24) NOT NULL,
 outcome varchar(12) NOT NULL,client_time timestamptz NOT NULL,
 active_duration_ms integer NOT NULL CHECK(active_duration_ms BETWEEN 0 AND 60000),
 received_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(user_id,event_id)
);
CREATE INDEX IF NOT EXISTS usage_recent_user_time ON private.usage_recent_events(user_id,client_time DESC);
CREATE INDEX IF NOT EXISTS usage_events_expiry ON private.usage_recent_events(received_at);
CREATE TABLE IF NOT EXISTS private.usage_user_feature_daily (
 user_id uuid NOT NULL,day date NOT NULL,feature_id varchar(32) NOT NULL,
 page_views bigint NOT NULL DEFAULT 0,actions bigint NOT NULL DEFAULT 0,
 successes bigint NOT NULL DEFAULT 0,failures bigint NOT NULL DEFAULT 0,
 sessions bigint NOT NULL DEFAULT 0,
 active_duration_ms bigint NOT NULL DEFAULT 0,last_event_at timestamptz NOT NULL,
 PRIMARY KEY(user_id,day,feature_id)
);
CREATE INDEX IF NOT EXISTS usage_daily_period ON private.usage_user_feature_daily(day,feature_id);
CREATE TABLE IF NOT EXISTS private.usage_daily_sessions (
 user_id uuid NOT NULL,day date NOT NULL,feature_id varchar(32) NOT NULL,session_id uuid NOT NULL,
 PRIMARY KEY(user_id,day,feature_id,session_id)
);
CREATE INDEX IF NOT EXISTS usage_sessions_expiry ON private.usage_daily_sessions(day);
CREATE TABLE IF NOT EXISTS private.usage_monthly_summary (
 month date NOT NULL,feature_id varchar(32) NOT NULL,actions bigint NOT NULL DEFAULT 0,
 active_duration_ms bigint NOT NULL DEFAULT 0,PRIMARY KEY(month,feature_id)
);
CREATE TABLE IF NOT EXISTS private.usage_access_audit (
 actor varchar(254) NOT NULL,target_user_id uuid,view varchar(16) NOT NULL,
 accessed_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON private.usage_preferences,private.usage_ingest_receipts,
 private.usage_recent_events,private.usage_user_feature_daily,private.usage_access_audit FROM PUBLIC;
REVOKE ALL ON private.usage_monthly_summary FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON private.usage_monthly_summary TO janus_private_api;
GRANT SELECT,DELETE ON private.usage_monthly_summary TO janus_private_pipeline;
REVOKE ALL ON private.usage_daily_sessions FROM PUBLIC;
GRANT SELECT,INSERT,DELETE ON private.usage_daily_sessions TO janus_private_api;
GRANT SELECT,DELETE ON private.usage_daily_sessions TO janus_private_pipeline;
GRANT SELECT,INSERT,UPDATE,DELETE ON private.usage_preferences,private.usage_ingest_receipts,
 private.usage_recent_events,private.usage_user_feature_daily TO janus_private_api;
GRANT INSERT ON private.usage_access_audit TO janus_private_api;
GRANT SELECT,DELETE ON private.usage_preferences,private.usage_ingest_receipts,
 private.usage_recent_events,private.usage_user_feature_daily,private.usage_access_audit TO janus_private_pipeline;
-- PHASE: acceptance
SELECT has_table_privilege('janus_private_api','private.usage_recent_events','INSERT'),
 NOT has_table_privilege('janus_public_api','private.usage_recent_events','SELECT');
INSERT INTO control.schema_migrations(version) VALUES ('064_usage_analytics') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
