\set ON_ERROR_STOP on

BEGIN;

-- PHASE: control-prepare
SET ROLE janus_control;

-- This is a rebuildable operational read model.  Do not couple it to the
-- historical owner of private.users with a foreign key: older dev databases
-- may have bootstrap-owned private tables.  Referential integrity is checked
-- by migration/runtime acceptance instead.
CREATE TABLE IF NOT EXISTS private.current_positions (
    user_id uuid NOT NULL,
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

REVOKE ALL ON private.current_positions FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON private.current_positions TO janus_private_api;
GRANT SELECT, DELETE ON private.current_positions TO janus_private_pipeline;

-- The API role owns the replay function because it already has bounded read
-- access to the private ledger and user row.  CREATE is temporary and revoked
-- in the final phase.
GRANT CREATE ON SCHEMA private TO janus_private_api;
RESET ROLE;

-- PHASE: private-api
SET ROLE janus_private_api;

CREATE OR REPLACE FUNCTION private.refresh_current_positions(p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
SET search_path = private, pg_catalog
AS $$
DECLARE
    event_row record;
    current_row private.current_positions%ROWTYPE;
    next_shares numeric(20,8);
    next_cost numeric(30,10);
    latest_version bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('current-positions:' || p_user_id::text));

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

REVOKE ALL ON FUNCTION private.refresh_current_positions(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION private.refresh_current_positions(uuid) TO janus_private_api;

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

-- PHASE: control-finalize
SET ROLE janus_control;
REVOKE CREATE ON SCHEMA private FROM janus_private_api;

INSERT INTO control.schema_migrations(version)
VALUES ('041_operational_position_projection')
ON CONFLICT(version) DO NOTHING;

RESET ROLE;
COMMIT;
