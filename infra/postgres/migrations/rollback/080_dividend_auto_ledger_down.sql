\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

-- 可逆向降版腳本：移除待確認股利草稿表與公共公司行動表（不動既有 private.ledger_events）。
DROP TABLE IF EXISTS private.pending_dividend_events;
DROP TABLE IF EXISTS control.corporate_actions;
DELETE FROM control.schema_migrations WHERE version = '080_dividend_auto_ledger';

RESET ROLE;
COMMIT;
