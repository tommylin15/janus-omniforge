\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- Rebuildable shared market read model: never contains owner identifiers.
CREATE TABLE IF NOT EXISTS control.operational_last_quotes (
    symbol varchar(16) PRIMARY KEY,
    price numeric(20,4) NOT NULL CHECK (price > 0),
    quote_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL,
    session text NOT NULL CHECK (session IN ('regular','off_session')),
    source text NOT NULL CHECK (source = 'twse_mis'),
    route_version text NOT NULL CHECK (route_version = 'quote-router.v1'),
    CHECK (quote_at <= received_at)
);
REVOKE ALL ON control.operational_last_quotes FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON control.operational_last_quotes TO janus_private_api;

-- Immutable owner-scoped profile revisions, including explicit cash declarations.
-- Declared cash is not a canonical cash ledger balance.
CREATE TABLE IF NOT EXISTS private.broker_profile_revisions (
    user_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    fee_discount_multiplier numeric(5,4) NOT NULL CHECK (fee_discount_multiplier BETWEEN 0 AND 1),
    minimum_fee numeric(20,4) NOT NULL CHECK (minimum_fee >= 0),
    cash_strategy text NOT NULL CHECK (cash_strategy IN ('reserve','balanced','invested')),
    declared_cash numeric(20,4) CHECK (declared_cash >= 0),
    cash_as_of date,
    currency char(3) NOT NULL DEFAULT 'TWD' CHECK (currency = 'TWD'),
    rule_version text NOT NULL DEFAULT 'broker-profile.v1',
    idempotency_key varchar(128) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id,version),
    UNIQUE (user_id,idempotency_key),
    CHECK ((declared_cash IS NULL) = (cash_as_of IS NULL))
);
REVOKE ALL ON private.broker_profile_revisions FROM PUBLIC;
GRANT SELECT, INSERT ON private.broker_profile_revisions TO janus_private_api;
GRANT SELECT, DELETE ON private.broker_profile_revisions TO janus_private_pipeline;

-- PHASE: acceptance
SELECT has_table_privilege('janus_private_api','control.operational_last_quotes','UPDATE'),
       has_table_privilege('janus_private_api','private.broker_profile_revisions','INSERT'),
       has_table_privilege('janus_private_pipeline','private.broker_profile_revisions','DELETE'),
       NOT has_table_privilege('janus_public_api','private.broker_profile_revisions','SELECT');
INSERT INTO control.schema_migrations(version) VALUES ('044_quotes_broker_profile')
ON CONFLICT(version) DO NOTHING;
RESET ROLE;
COMMIT;
