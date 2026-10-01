\set ON_ERROR_STOP on
BEGIN;

-- Keep the Mart AI target admission boundary de-identified. The control-plane
-- history stores only symbol-level booleans; it never stores user IDs, share
-- counts, costs, or user-to-symbol mappings.
CREATE TABLE IF NOT EXISTS control.mart_ai_target_history_meta (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    replay_supported_from date NOT NULL
);
INSERT INTO control.mart_ai_target_history_meta(singleton,replay_supported_from)
VALUES (true,timezone('Asia/Taipei',now())::date)
ON CONFLICT(singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS control.mart_ai_target_history (
    history_id bigserial PRIMARY KEY,
    symbol varchar(16) NOT NULL,
    watchlisted boolean NOT NULL,
    held boolean NOT NULL,
    effective_at timestamptz NOT NULL DEFAULT now(),
    CHECK (watchlisted OR held OR (NOT watchlisted AND NOT held))
);
CREATE INDEX IF NOT EXISTS mart_ai_target_history_asof_idx
    ON control.mart_ai_target_history(symbol,effective_at DESC,history_id DESC);

ALTER TABLE control.mart_ai_target_history_meta OWNER TO janus_control;
ALTER TABLE control.mart_ai_target_history OWNER TO janus_control;
ALTER SEQUENCE control.mart_ai_target_history_history_id_seq OWNER TO janus_control;
REVOKE ALL ON control.mart_ai_target_history_meta,control.mart_ai_target_history FROM PUBLIC;

-- The trigger executes with the caller's existing private-table privileges and
-- may write only the de-identified control history. No privileged private read
-- function is exposed to the Mart runtime.
CREATE OR REPLACE FUNCTION control.capture_mart_ai_target_symbol()
RETURNS trigger LANGUAGE plpgsql SET search_path=control,private,pg_catalog AS $$
DECLARE target_symbol varchar(16);
DECLARE is_watchlisted boolean;
DECLARE is_held boolean;
BEGIN
    target_symbol := CASE WHEN TG_OP='DELETE' THEN OLD.symbol ELSE NEW.symbol END;
    PERFORM pg_advisory_xact_lock(hashtext('mart-ai-target:' || target_symbol));

    SELECT EXISTS(
        SELECT 1 FROM private.watchlist w
         WHERE w.symbol=target_symbol AND w.active
    ) INTO is_watchlisted;

    SELECT EXISTS(
        SELECT 1
          FROM (
              SELECT le.user_id,
                     sum(
                         CASE le.event_type
                           WHEN 'BUY' THEN coalesce(le.shares,0)
                           WHEN 'SELL' THEN -coalesce(le.shares,0)
                           WHEN 'STOCK_DIV' THEN coalesce(le.shares,0)
                           ELSE 0
                         END * CASE WHEN le.event_action='REVERSAL' THEN -1 ELSE 1 END
                     ) AS shares
                FROM private.ledger_events le
               WHERE le.symbol=target_symbol
               GROUP BY le.user_id
          ) position
         WHERE position.shares > 0
    ) INTO is_held;

    INSERT INTO control.mart_ai_target_history(symbol,watchlisted,held,effective_at)
    VALUES (target_symbol,is_watchlisted,is_held,now());
    RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END;
$$;
REVOKE ALL ON FUNCTION control.capture_mart_ai_target_symbol() FROM PUBLIC;

-- Only the two existing private workload identities may append de-identified
-- state. They cannot update or delete history rows.
GRANT USAGE ON SCHEMA control TO janus_private_api,janus_private_pipeline;
GRANT INSERT ON control.mart_ai_target_history TO janus_private_api,janus_private_pipeline;
GRANT USAGE,SELECT ON SEQUENCE control.mart_ai_target_history_history_id_seq
    TO janus_private_api,janus_private_pipeline;

DROP TRIGGER IF EXISTS mart_ai_target_watchlist_insert ON private.watchlist;
CREATE TRIGGER mart_ai_target_watchlist_insert
AFTER INSERT ON private.watchlist FOR EACH ROW
EXECUTE FUNCTION control.capture_mart_ai_target_symbol();

DROP TRIGGER IF EXISTS mart_ai_target_watchlist_active_update ON private.watchlist;
CREATE TRIGGER mart_ai_target_watchlist_active_update
AFTER UPDATE OF active ON private.watchlist FOR EACH ROW
WHEN (OLD.active IS DISTINCT FROM NEW.active)
EXECUTE FUNCTION control.capture_mart_ai_target_symbol();

DROP TRIGGER IF EXISTS mart_ai_target_watchlist_delete ON private.watchlist;
CREATE TRIGGER mart_ai_target_watchlist_delete
AFTER DELETE ON private.watchlist FOR EACH ROW
EXECUTE FUNCTION control.capture_mart_ai_target_symbol();

DROP TRIGGER IF EXISTS mart_ai_target_ledger_insert ON private.ledger_events;
CREATE TRIGGER mart_ai_target_ledger_insert
AFTER INSERT ON private.ledger_events FOR EACH ROW
EXECUTE FUNCTION control.capture_mart_ai_target_symbol();

DROP TRIGGER IF EXISTS mart_ai_target_ledger_delete ON private.ledger_events;
CREATE TRIGGER mart_ai_target_ledger_delete
AFTER DELETE ON private.ledger_events FOR EACH ROW
EXECUTE FUNCTION control.capture_mart_ai_target_symbol();

-- Establish the migration-day baseline. The replay floor prevents this current
-- snapshot from being represented as exact history before migration day.
WITH watch AS (
    SELECT symbol,bool_or(active) AS watchlisted
      FROM private.watchlist
     GROUP BY symbol
), ledger_position AS (
    SELECT le.user_id,le.symbol,
           sum(
               CASE le.event_type
                 WHEN 'BUY' THEN coalesce(le.shares,0)
                 WHEN 'SELL' THEN -coalesce(le.shares,0)
                 WHEN 'STOCK_DIV' THEN coalesce(le.shares,0)
                 ELSE 0
               END * CASE WHEN le.event_action='REVERSAL' THEN -1 ELSE 1 END
           ) AS shares
      FROM private.ledger_events le
     GROUP BY le.user_id,le.symbol
), holdings AS (
    SELECT symbol,bool_or(shares > 0) AS held
      FROM ledger_position
     GROUP BY symbol
), symbols AS (
    SELECT symbol FROM watch
    UNION
    SELECT symbol FROM holdings
)
INSERT INTO control.mart_ai_target_history(symbol,watchlisted,held,effective_at)
SELECT s.symbol,coalesce(w.watchlisted,false),coalesce(h.held,false),now()
  FROM symbols s
  LEFT JOIN watch w USING(symbol)
  LEFT JOIN holdings h USING(symbol)
 WHERE coalesce(w.watchlisted,false) OR coalesce(h.held,false);

CREATE OR REPLACE FUNCTION control.mart_ai_target_symbols(p_as_of date)
RETURNS TABLE(symbol varchar(16),watchlisted boolean,held boolean)
LANGUAGE plpgsql SET search_path=control,pg_catalog AS $$
DECLARE replay_floor date;
BEGIN
    IF p_as_of IS NULL THEN
        RAISE EXCEPTION 'analysis_as_of is required' USING ERRCODE='22023';
    END IF;
    SELECT replay_supported_from INTO replay_floor
      FROM control.mart_ai_target_history_meta WHERE singleton=true;
    IF replay_floor IS NULL OR p_as_of < replay_floor THEN
        RAISE EXCEPTION 'AI target replay is unavailable before %', replay_floor USING ERRCODE='22023';
    END IF;
    RETURN QUERY
    WITH latest AS (
        SELECT DISTINCT ON (h.symbol) h.symbol,h.watchlisted,h.held
          FROM control.mart_ai_target_history h
         WHERE h.effective_at < ((p_as_of + 1)::timestamp AT TIME ZONE 'Asia/Taipei')
         ORDER BY h.symbol,h.effective_at DESC,h.history_id DESC
    )
    SELECT l.symbol,l.watchlisted,l.held
      FROM latest l
     WHERE l.watchlisted OR l.held
     ORDER BY l.symbol;
END;
$$;
REVOKE ALL ON FUNCTION control.mart_ai_target_symbols(date) FROM PUBLIC;

-- Mart reads only de-identified control history. Direct private workspace reads
-- remain unavailable to the Mart identity.
GRANT USAGE ON SCHEMA control TO janus_mart_publication;
GRANT SELECT ON control.mart_ai_target_history_meta,control.mart_ai_target_history
    TO janus_mart_publication;
GRANT EXECUTE ON FUNCTION control.mart_ai_target_symbols(date) TO janus_mart_publication;

INSERT INTO control.schema_migrations(version)
VALUES ('036_mart_ai_targets') ON CONFLICT(version) DO NOTHING;

COMMIT;
