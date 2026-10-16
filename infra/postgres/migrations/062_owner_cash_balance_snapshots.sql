\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- Cash is owner-declared; an immutable anchor (ledger_version at save time)
-- prevents applying historical transactions twice. Future trade/correction/
-- reversal cash flows are derived from the existing immutable ledger.
-- No guessed default, no external bank verification, no modification of trades.
CREATE TABLE IF NOT EXISTS private.cash_balance_snapshots (
    user_id uuid NOT NULL,
    version bigint NOT NULL CHECK (version > 0),
    amount numeric(20,4) NOT NULL CHECK (amount >= 0),
    anchor_ledger_version bigint NOT NULL CHECK (anchor_ledger_version >= 0),
    currency char(3) NOT NULL DEFAULT 'TWD' CHECK (currency = 'TWD'),
    idempotency_key varchar(128) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, version),
    UNIQUE (user_id, idempotency_key)
);
REVOKE ALL ON private.cash_balance_snapshots FROM PUBLIC;
GRANT SELECT, INSERT ON private.cash_balance_snapshots TO janus_private_api;
GRANT SELECT, DELETE ON private.cash_balance_snapshots TO janus_private_pipeline;
-- janus_control cannot REFERENCES the legacy private.users owner table.
-- Owner deletion explicitly deletes cash snapshots in complete_deletion;
-- no broad REFERENCES privilege expansion or implicit cascade.

-- PHASE: acceptance
SELECT
    has_table_privilege('janus_private_api','private.cash_balance_snapshots','SELECT'),
    has_table_privilege('janus_private_api','private.cash_balance_snapshots','INSERT'),
    has_table_privilege('janus_private_pipeline','private.cash_balance_snapshots','SELECT'),
    has_table_privilege('janus_private_pipeline','private.cash_balance_snapshots','DELETE'),
    NOT has_table_privilege('janus_public_api','private.cash_balance_snapshots','SELECT'),
    NOT has_table_privilege('janus_private_pipeline','private.cash_balance_snapshots','INSERT');

INSERT INTO control.schema_migrations(version)
VALUES ('062_owner_cash_balance_snapshots') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
