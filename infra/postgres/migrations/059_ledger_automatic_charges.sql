\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- Existing immutable amounts remain intact; historical repair appends corrections.
ALTER TABLE private.ledger_events ADD COLUMN IF NOT EXISTS fee_rule_snapshot jsonb;

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
        WITH RECURSIVE lineage AS (
            SELECT event_id, ledger_version AS trade_order
              FROM private.ledger_events
             WHERE user_id=p_user_id AND replaces_event_id IS NULL
            UNION ALL
            SELECT child.event_id, parent.trade_order
              FROM private.ledger_events child JOIN lineage parent ON child.replaces_event_id=parent.event_id
             WHERE child.user_id=p_user_id
        )
        SELECT e.*
          FROM private.ledger_events e JOIN lineage USING(event_id)
         WHERE e.user_id = p_user_id
           AND e.event_action <> 'REVERSAL'
           AND NOT EXISTS (
               SELECT 1
                 FROM private.ledger_events reversal
                WHERE reversal.user_id = e.user_id
                  AND reversal.event_action = 'REVERSAL'
                  AND reversal.reverses_event_id = e.event_id
           )
         ORDER BY e.trade_date, lineage.trade_order
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
RESET ROLE;
-- PHASE: control-finalize
SET ROLE janus_control;
REVOKE CREATE ON SCHEMA private FROM janus_private_api;
-- PHASE: acceptance
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='private' AND table_name='ledger_events'
      AND column_name='fee_rule_snapshot' AND data_type='jsonb'
), NOT has_table_privilege('janus_public_api','private.ledger_events','SELECT');
INSERT INTO control.schema_migrations(version) VALUES ('059_ledger_automatic_charges')
ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
