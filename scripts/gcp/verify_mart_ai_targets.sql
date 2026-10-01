\set ON_ERROR_STOP on
-- Existing dev database only. All synthetic private rows and projections roll back.
BEGIN;
SET LOCAL statement_timeout='15s';
SET LOCAL ROLE janus_private_api;
INSERT INTO private.users(user_id,google_sub,display_email) VALUES
('aa000000-0000-0000-0000-000000000001','mart-ai-acceptance-1','acceptance-1.invalid'),
('aa000000-0000-0000-0000-000000000002','mart-ai-acceptance-2','acceptance-2.invalid');
INSERT INTO private.watchlist(user_id,symbol,sort_order,idempotency_key) VALUES
('aa000000-0000-0000-0000-000000000001','__AI_W',0,'mart-ai-w'),
('aa000000-0000-0000-0000-000000000001','__AI_B',1,'mart-ai-b1'),
('aa000000-0000-0000-0000-000000000002','__AI_B',0,'mart-ai-b2');
INSERT INTO private.ledger_events(event_id,user_id,ledger_version,event_action,event_type,trade_date,symbol,shares,price,currency,idempotency_key) VALUES
('ab000000-0000-0000-0000-000000000001','aa000000-0000-0000-0000-000000000001',1,'ORIGINAL','BUY',current_date,'__AI_H',1,1,'TWD','mart-ai-h'),
('ab000000-0000-0000-0000-000000000002','aa000000-0000-0000-0000-000000000002',1,'ORIGINAL','BUY',current_date,'__AI_B',1,1,'TWD','mart-ai-b');
SET LOCAL ROLE janus_mart_publication;
DO $$
DECLARE day date := timezone('Asia/Taipei',now())::date;
BEGIN
    ASSERT (SELECT count(*) FROM control.mart_ai_target_symbols(day) WHERE symbol IN ('__AI_W','__AI_H','__AI_B'))=3;
    ASSERT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(day) WHERE symbol='__AI_W' AND watchlisted AND NOT held);
    ASSERT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(day) WHERE symbol='__AI_H' AND held AND NOT watchlisted);
    ASSERT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(day) WHERE symbol='__AI_B' AND held AND watchlisted);
    BEGIN
        PERFORM 1 FROM private.watchlist LIMIT 0;
        RAISE EXCEPTION 'private watchlist read was allowed';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM 1 FROM private.ledger_events LIMIT 0;
        RAISE EXCEPTION 'private ledger read was allowed';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM * FROM control.mart_ai_target_symbols((SELECT replay_supported_from-1 FROM control.mart_ai_target_history_meta));
        RAISE EXCEPTION 'pre-floor replay was accepted';
    EXCEPTION WHEN invalid_parameter_value THEN NULL;
    END;
END $$;
SET LOCAL ROLE janus_private_api;
UPDATE private.watchlist SET active=false WHERE user_id='aa000000-0000-0000-0000-000000000001' AND symbol='__AI_B';
SET LOCAL ROLE janus_mart_publication;
DO $$ BEGIN
    ASSERT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(timezone('Asia/Taipei',now())::date) WHERE symbol='__AI_B' AND watchlisted AND held);
END $$;
SET LOCAL ROLE janus_private_api;
UPDATE private.watchlist SET active=false WHERE user_id='aa000000-0000-0000-0000-000000000002' AND symbol='__AI_B';
UPDATE private.watchlist SET active=false WHERE symbol='__AI_W';
SET LOCAL ROLE janus_mart_publication;
DO $$ BEGIN
    ASSERT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(timezone('Asia/Taipei',now())::date) WHERE symbol='__AI_B' AND NOT watchlisted AND held);
    ASSERT NOT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(timezone('Asia/Taipei',now())::date) WHERE symbol='__AI_W');
END $$;
SET LOCAL ROLE janus_private_api;
INSERT INTO private.ledger_events(event_id,user_id,ledger_version,event_action,event_type,trade_date,symbol,shares,price,currency,idempotency_key) VALUES
('ab000000-0000-0000-0000-000000000003','aa000000-0000-0000-0000-000000000002',2,'ORIGINAL','SELL',current_date,'__AI_B',1,1,'TWD','mart-ai-sell');
SET LOCAL ROLE janus_mart_publication;
DO $$ BEGIN
    ASSERT NOT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(timezone('Asia/Taipei',now())::date) WHERE symbol='__AI_B');
END $$;
RESET ROLE;
UPDATE control.mart_ai_target_history
   SET effective_at=((timezone('Asia/Taipei',now())::date+1)::timestamp AT TIME ZONE 'Asia/Taipei')
 WHERE symbol='__AI_W' AND NOT watchlisted AND NOT held;
SET LOCAL ROLE janus_mart_publication;
DO $$ BEGIN
    ASSERT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(timezone('Asia/Taipei',now())::date) WHERE symbol='__AI_W');
    ASSERT NOT EXISTS(SELECT 1 FROM control.mart_ai_target_symbols(timezone('Asia/Taipei',now())::date+1) WHERE symbol='__AI_W');
END $$;
ROLLBACK;
SELECT 'passed: watch-only, held-only, dedup, multi-owner, held-after-unwatch, exit, as-of-replay, replay-floor, private-isolation';
