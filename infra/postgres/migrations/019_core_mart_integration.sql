\set ON_ERROR_STOP on

SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS control.core_ready_events (
    core_execution_id uuid PRIMARY KEY REFERENCES control.executions(execution_id) ON DELETE RESTRICT,
    analysis_execution_id uuid UNIQUE REFERENCES control.executions(execution_id) ON DELETE RESTRICT,
    config_id text NOT NULL REFERENCES control.collection_configs(config_id) ON DELETE RESTRICT,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (payload->>'eventType' = 'core.dataset.ready.v1'),
    CHECK (payload->>'datasetId' = 'core'),
    CHECK (payload->>'executionId' = core_execution_id::text),
    CHECK (payload->>'coreSnapshotUri' LIKE 'gs://%'),
    CHECK (payload->>'coreSnapshotHash' ~ '^sha256:[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS control.deep_tracking_membership_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol text NOT NULL REFERENCES control.stock_master(symbol) ON DELETE RESTRICT
        CHECK (symbol ~ '^[A-Z0-9_-]{1,16}$'),
    effective_at timestamptz NOT NULL DEFAULT now(),
    active boolean NOT NULL,
    demand_count integer NOT NULL CHECK (demand_count >= 0),
    reason text NOT NULL CHECK (reason IN ('first_follow','demand_changed','last_unfollow'))
);

CREATE INDEX IF NOT EXISTS deep_tracking_membership_history
    ON control.deep_tracking_membership_events(symbol, effective_at DESC, event_id DESC);

RESET ROLE;

INSERT INTO control.deep_tracking_membership_events(symbol,active,demand_count,reason)
SELECT w.symbol,true,count(*),'first_follow'
FROM private.watchlist w
WHERE w.active
GROUP BY w.symbol
HAVING NOT EXISTS (
    SELECT 1 FROM control.deep_tracking_membership_events history WHERE history.symbol=w.symbol
);

SET ROLE janus_control;

CREATE OR REPLACE FUNCTION control.reject_deep_tracking_history_rewrite()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'deep tracking membership history is append-only';
END;
$$;

DROP TRIGGER IF EXISTS deep_tracking_history_append_only ON control.deep_tracking_membership_events;
CREATE TRIGGER deep_tracking_history_append_only
BEFORE UPDATE OR DELETE ON control.deep_tracking_membership_events
FOR EACH ROW EXECUTE FUNCTION control.reject_deep_tracking_history_rewrite();

CREATE OR REPLACE VIEW control.active_deep_tracking_memberships AS
SELECT symbol, effective_at, demand_count
FROM (
    SELECT DISTINCT ON (symbol) symbol, effective_at, active, demand_count
    FROM control.deep_tracking_membership_events
    ORDER BY symbol, effective_at DESC, event_id DESC
) latest
WHERE active;

CREATE OR REPLACE FUNCTION control.record_deep_tracking_demand(p_symbol text)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = control, private, pg_catalog AS $$
DECLARE
    current_count integer;
    previous_count integer;
BEGIN
    IF p_symbol !~ '^[A-Z0-9_-]{1,16}$' THEN
        RAISE EXCEPTION 'invalid deep tracking symbol';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('private-watchlist-symbol-limit'));
    SELECT count(*) INTO current_count FROM private.watchlist WHERE symbol=p_symbol AND active;
    SELECT demand_count INTO previous_count
      FROM control.deep_tracking_membership_events
     WHERE symbol=p_symbol ORDER BY effective_at DESC,event_id DESC LIMIT 1;
    IF previous_count IS DISTINCT FROM current_count THEN
        INSERT INTO control.deep_tracking_membership_events(symbol,active,demand_count,reason)
        VALUES (p_symbol,current_count > 0,current_count,
                CASE WHEN current_count=0 THEN 'last_unfollow'
                     WHEN previous_count IS NULL THEN 'first_follow' ELSE 'demand_changed' END);
    END IF;
END;
$$;

RESET ROLE;

ALTER FUNCTION control.record_deep_tracking_demand(text) OWNER TO janus_private_api;
GRANT USAGE ON SCHEMA control TO janus_private_api;
GRANT INSERT, SELECT ON control.deep_tracking_membership_events TO janus_private_api;
GRANT USAGE, SELECT ON SEQUENCE control.deep_tracking_membership_events_event_id_seq TO janus_private_api;

REVOKE UPDATE, DELETE, TRUNCATE ON control.core_ready_events, control.deep_tracking_membership_events FROM PUBLIC;
REVOKE ALL ON FUNCTION control.record_deep_tracking_demand(text) FROM PUBLIC;
GRANT SELECT ON control.core_ready_events, control.active_deep_tracking_memberships TO janus_web_control;
GRANT USAGE ON SCHEMA control TO janus_private_api;
GRANT EXECUTE ON FUNCTION control.record_deep_tracking_demand(text) TO janus_private_api;
GRANT SELECT ON control.deep_tracking_membership_events, control.active_deep_tracking_memberships TO janus_web_control;

GRANT USAGE ON SCHEMA publication TO janus_web_control;
GRANT SELECT ON publication.mart_report_index, publication.publishable_mart_reports TO janus_web_control;

INSERT INTO control.schema_migrations(version) VALUES ('019_core_mart_integration')
ON CONFLICT (version) DO NOTHING;
