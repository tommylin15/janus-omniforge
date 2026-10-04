\set ON_ERROR_STOP on

BEGIN;

-- private.users is deliberately not permanently referenceable by janus_control.
-- Mirror the bounded migration pattern from 024: grant only while the FK is created,
-- then revoke before commit.
GRANT REFERENCES ON private.users TO janus_control;

SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS private.current_positions (
    user_id uuid NOT NULL REFERENCES private.users(user_id) ON DELETE CASCADE,
    symbol varchar(16) NOT NULL,
    currency char(3) NOT NULL,
    shares numeric(20,8) NOT NULL CHECK (shares > 0),
    average_cost numeric(30,10) NOT NULL CHECK (average_cost >= 0),
    cost_basis numeric(30,10) NOT NULL CHECK (cost_basis >= 0),
    ledger_version bigint NOT NULL CHECK (ledger_version >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, symbol, currency)
);

CREATE INDEX IF NOT EXISTS current_positions_user_idx
    ON private.current_positions(user_id, symbol);

CREATE OR REPLACE FUNCTION private.refresh_current_positions(p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = private, pg_catalog
AS $$
DECLARE
    event_row record;
    current_row private.current_positions%ROWTYPE;
    next_shares numeric(20,8);
    next_cost numeric(30,10);
    latest_version bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(p_user_id::text));

    SELECT ledger_version INTO latest_version
      FROM private.users
     WHERE user_id = p_user_id;
    IF latest_version IS NULL THEN
        RAISE EXCEPTION 'private user not found';
    END IF;

    DELETE FROM private.current_positions WHERE user_id = p_user_id;

    FOR event_row IN
        SELECT e.*
          FROM private.ledger_events e
         WHERE e.user_id = p_user_id
           AND e.event_action <> 'REVERSAL'
           AND NOT EXISTS (
               SELECT 1
                 FROM private.ledger_events reversal
                WHERE reversal.user_id = e.user_id
                  AND reversal.event_action = 'REVERSAL'
                  AND reversal.reverses_event_id = e.event_id
           )
         ORDER BY e.trade_date, e.ledger_version
    LOOP
        IF event_row.event_type = 'BUY' THEN
            SELECT * INTO current_row
              FROM private.current_positions
             WHERE user_id = p_user_id
               AND symbol = event_row.symbol
               AND currency = event_row.currency;

            IF NOT FOUND THEN
                next_shares := event_row.shares;
                next_cost := event_row.shares * event_row.price + event_row.fee + event_row.tax;
                INSERT INTO private.current_positions(
                    user_id, symbol, currency, shares, average_cost, cost_basis, ledger_version, updated_at
                ) VALUES (
                    p_user_id, event_row.symbol, event_row.currency, next_shares,
                    next_cost / next_shares, next_cost, latest_version, now()
                );
            ELSE
                next_shares := current_row.shares + event_row.shares;
                next_cost := current_row.cost_basis + event_row.shares * event_row.price + event_row.fee + event_row.tax;
                UPDATE private.current_positions
                   SET shares = next_shares,
                       cost_basis = next_cost,
                       average_cost = next_cost / next_shares,
                       ledger_version = latest_version,
                       updated_at = now()
                 WHERE user_id = p_user_id
                   AND symbol = event_row.symbol
                   AND currency = event_row.currency;
            END IF;

        ELSIF event_row.event_type = 'SELL' THEN
            SELECT * INTO current_row
              FROM private.current_positions
             WHERE user_id = p_user_id
               AND symbol = event_row.symbol
               AND currency = event_row.currency;
            IF NOT FOUND OR current_row.shares < event_row.shares THEN
                RAISE EXCEPTION 'operational position replay detected oversell for %', event_row.symbol;
            END IF;

            next_shares := current_row.shares - event_row.shares;
            next_cost := current_row.cost_basis - current_row.average_cost * event_row.shares;
            IF next_shares = 0 THEN
                DELETE FROM private.current_positions
                 WHERE user_id = p_user_id
                   AND symbol = event_row.symbol
                   AND currency = event_row.currency;
            ELSE
                UPDATE private.current_positions
                   SET shares = next_shares,
                       cost_basis = GREATEST(next_cost, 0),
                       average_cost = current_row.average_cost,
                       ledger_version = latest_version,
                       updated_at = now()
                 WHERE user_id = p_user_id
                   AND symbol = event_row.symbol
                   AND currency = event_row.currency;
            END IF;

        ELSIF event_row.event_type = 'STOCK_DIV' THEN
            SELECT * INTO current_row
              FROM private.current_positions
             WHERE user_id = p_user_id
               AND symbol = event_row.symbol
               AND currency = event_row.currency;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'stock dividend has no operational position for %', event_row.symbol;
            END IF;
            next_shares := current_row.shares + event_row.shares;
            UPDATE private.current_positions
               SET shares = next_shares,
                   average_cost = CASE WHEN next_shares > 0 THEN current_row.cost_basis / next_shares ELSE 0 END,
                   ledger_version = latest_version,
                   updated_at = now()
             WHERE user_id = p_user_id
               AND symbol = event_row.symbol
               AND currency = event_row.currency;
        END IF;
        -- CASH_DIV does not change shares or cost basis.
    END LOOP;

    UPDATE private.current_positions
       SET ledger_version = latest_version,
           updated_at = now()
     WHERE user_id = p_user_id;
END;
$$;

CREATE OR REPLACE FUNCTION private.refresh_current_positions_trigger()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = private, pg_catalog
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM private.refresh_current_positions(OLD.user_id);
    ELSIF TG_OP = 'UPDATE' AND OLD.user_id IS DISTINCT FROM NEW.user_id THEN
        PERFORM private.refresh_current_positions(OLD.user_id);
        PERFORM private.refresh_current_positions(NEW.user_id);
    ELSE
        PERFORM private.refresh_current_positions(NEW.user_id);
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS ledger_refresh_current_positions ON private.ledger_events;
CREATE CONSTRAINT TRIGGER ledger_refresh_current_positions
AFTER INSERT OR UPDATE OR DELETE ON private.ledger_events
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION private.refresh_current_positions_trigger();

DO $$
DECLARE
    target_user uuid;
BEGIN
    FOR target_user IN SELECT user_id FROM private.users ORDER BY user_id LOOP
        PERFORM private.refresh_current_positions(target_user);
    END LOOP;
END;
$$;

RESET ROLE;

REVOKE REFERENCES ON private.users FROM janus_control;
REVOKE ALL ON private.current_positions FROM PUBLIC;
REVOKE ALL ON FUNCTION private.refresh_current_positions(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION private.refresh_current_positions_trigger() FROM PUBLIC;
GRANT SELECT ON private.current_positions TO janus_private_api, janus_private_pipeline;
GRANT DELETE ON private.current_positions TO janus_private_pipeline;

INSERT INTO control.schema_migrations(version)
VALUES ('041_operational_position_projection')
ON CONFLICT(version) DO NOTHING;

COMMIT;
