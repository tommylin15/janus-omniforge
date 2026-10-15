\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- 061: Verified public TPEx daily official closes; separate from Core canonical.
-- One immutable shared price per symbol/session; no owner data or backdated
-- fills from a newer session. source_uri and record_sha256 preserve provenance.
CREATE TABLE IF NOT EXISTS control.official_tpex_eod_history (
    symbol varchar(16) NOT NULL REFERENCES control.stock_master(symbol),
    trade_date date NOT NULL,
    price numeric(20,4) NOT NULL CHECK (price > 0),
    source_uri text NOT NULL CHECK (left(source_uri, 24) = 'https://www.tpex.org.tw/'),
    record_sha256 text NOT NULL CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    first_observed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol,trade_date)
);
REVOKE ALL ON control.official_tpex_eod_history FROM PUBLIC;
GRANT SELECT,INSERT ON control.official_tpex_eod_history TO janus_private_api;
GRANT SELECT,INSERT ON control.official_tpex_eod_history TO janus_private_pipeline;

-- PHASE: acceptance
SELECT
    to_regclass('control.official_tpex_eod_history') IS NOT NULL,
    has_table_privilege('janus_private_pipeline','control.official_tpex_eod_history','SELECT'),
    has_table_privilege('janus_private_pipeline','control.official_tpex_eod_history','INSERT'),
    has_table_privilege('janus_private_api','control.official_tpex_eod_history','SELECT'),
    has_table_privilege('janus_private_api','control.official_tpex_eod_history','INSERT'),
    NOT has_table_privilege('janus_public_api','control.official_tpex_eod_history','SELECT'),
    NOT has_table_privilege('janus_private_pipeline','control.official_tpex_eod_history','UPDATE'),
    NOT has_table_privilege('janus_private_api','control.official_tpex_eod_history','DELETE');

INSERT INTO control.schema_migrations(version)
VALUES ('061_tpex_official_eod_daily') ON CONFLICT(version) DO NOTHING;
RESET ROLE;
COMMIT;
