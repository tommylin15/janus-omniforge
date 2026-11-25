\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

-- 公共公司行動（除權息）表：僅含市場公開資訊，嚴禁混入任何私人帳本欄位。
CREATE TABLE IF NOT EXISTS control.corporate_actions (
    action_id uuid PRIMARY KEY,
    symbol varchar(16) NOT NULL,
    market text NOT NULL CHECK (market IN ('TWSE', 'TPEX')),
    security_type text NOT NULL DEFAULT 'common_stock'
        CHECK (security_type IN ('common_stock', 'financial', 'etf', 'reit', 'ky_stock')),
    ex_date date NOT NULL,
    payment_date date,
    action_type text NOT NULL CHECK (action_type IN ('CASH_DIVIDEND', 'STOCK_DIVIDEND')),
    cash_dividend_per_share numeric(18,6) NOT NULL DEFAULT 0 CHECK (cash_dividend_per_share >= 0),
    stock_dividend_ratio numeric(18,8) NOT NULL DEFAULT 0 CHECK (stock_dividend_ratio >= 0),
    par_value numeric(10,4) DEFAULT 10.0 CHECK (par_value IS NULL OR par_value > 0),
    source_name text NOT NULL,
    source_updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (symbol, ex_date, action_type)
);

CREATE INDEX IF NOT EXISTS corporate_actions_ex_date_symbol_idx
    ON control.corporate_actions(ex_date DESC, symbol);
CREATE INDEX IF NOT EXISTS corporate_actions_symbol_ex_date_idx
    ON control.corporate_actions(symbol, ex_date DESC);

-- 私人待確認股利草稿表：嚴格依 user_id 隔離；不加跨 owner 之外鍵耦合以相容既有 bootstrap 資料庫。
CREATE TABLE IF NOT EXISTS private.pending_dividend_events (
    draft_id uuid PRIMARY KEY,
    user_id uuid NOT NULL,
    symbol varchar(16) NOT NULL,
    company_name text,
    security_type text NOT NULL DEFAULT 'common_stock'
        CHECK (security_type IN ('common_stock', 'financial', 'etf', 'reit', 'ky_stock')),
    action_type text NOT NULL CHECK (action_type IN ('CASH_DIVIDEND', 'STOCK_DIVIDEND')),
    ex_date date NOT NULL,
    payment_date date,
    eligible_shares numeric(20,8) NOT NULL CHECK (eligible_shares > 0),
    rate_per_share numeric(18,8) NOT NULL CHECK (rate_per_share > 0),
    gross_cash_amount numeric(20,2),
    estimated_remit_fee numeric(20,2) NOT NULL DEFAULT 0 CHECK (estimated_remit_fee >= 0),
    estimated_nhi_fee numeric(20,2) NOT NULL DEFAULT 0 CHECK (estimated_nhi_fee >= 0),
    net_cash_amount numeric(20,2),
    estimated_stock_shares numeric(20,4),
    fractional_shares numeric(20,6),
    confirmed_stock_shares numeric(20,4),
    status text NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'CONFIRMED', 'DISMISSED', 'ALREADY_RECORDED', 'STALE')),
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    ledger_version_at_calc bigint NOT NULL DEFAULT 0 CHECK (ledger_version_at_calc >= 0),
    confirmed_trade_id uuid,
    user_note varchar(500),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, symbol, ex_date, action_type)
);

CREATE INDEX IF NOT EXISTS pending_dividend_events_user_status_ex_idx
    ON private.pending_dividend_events(user_id, status, ex_date DESC);

REVOKE ALL ON control.corporate_actions, private.pending_dividend_events FROM PUBLIC;
GRANT SELECT ON control.corporate_actions TO janus_private_api, janus_web_control;
GRANT SELECT, INSERT, UPDATE, DELETE ON private.pending_dividend_events TO janus_private_api;
GRANT SELECT, DELETE ON private.pending_dividend_events TO janus_private_pipeline;

-- PHASE: acceptance
SELECT to_regclass('control.corporate_actions') IS NOT NULL,
       to_regclass('private.pending_dividend_events') IS NOT NULL,
       EXISTS (
           SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'control'
              AND table_name = 'corporate_actions'
              AND column_name = 'stock_dividend_ratio'
       ),
       has_table_privilege('janus_private_api', 'control.corporate_actions', 'SELECT'),
       has_table_privilege('janus_private_api', 'private.pending_dividend_events', 'SELECT'),
       has_table_privilege('janus_private_api', 'private.pending_dividend_events', 'INSERT'),
       has_table_privilege('janus_private_api', 'private.pending_dividend_events', 'UPDATE'),
       has_table_privilege('janus_private_api', 'private.pending_dividend_events', 'DELETE'),
       has_table_privilege('janus_private_pipeline', 'private.pending_dividend_events', 'SELECT'),
       has_table_privilege('janus_private_pipeline', 'private.pending_dividend_events', 'DELETE'),
       NOT has_table_privilege('janus_public_api', 'private.pending_dividend_events', 'SELECT'),
       NOT has_table_privilege('janus_public_api', 'control.corporate_actions', 'SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('080_dividend_auto_ledger') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
