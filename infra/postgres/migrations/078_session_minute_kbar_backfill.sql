\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;
SET LOCAL lock_timeout = '5s';

-- Broker-authorized historical 1-minute bars are distinct from operational
-- last-tick snapshots; never label them as real-time, or overwrite quote rows.
CREATE TABLE IF NOT EXISTS control.operational_session_kbars (
  symbol text NOT NULL CHECK (symbol = 'TAIEX' OR symbol ~ '^[0-9A-Z]{4,10}$'),
  minute_at timestamptz NOT NULL,
  price numeric(20,4) NOT NULL CHECK (price > 0),
  source text NOT NULL CHECK (source = 'shioaji_kbars'),
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol,minute_at)
);
CREATE INDEX IF NOT EXISTS operational_session_kbars_retention
  ON control.operational_session_kbars(minute_at);

-- Atomic cross-instance claim, 90-minute retry cooldown, max three attempts
-- per symbol per Taipei session; no additional scheduler or paid resource.
CREATE TABLE IF NOT EXISTS control.operational_kbar_backfill_state (
  symbol text NOT NULL CHECK (symbol = 'TAIEX' OR symbol ~ '^[0-9A-Z]{4,10}$'),
  trade_day date NOT NULL,
  last_attempt_at timestamptz NOT NULL,
  attempts smallint NOT NULL DEFAULT 1 CHECK (attempts BETWEEN 1 AND 3),
  last_status text NOT NULL DEFAULT 'reserved'
    CHECK (last_status IN ('reserved','available','missing','unavailable','invalid')),
  last_saved integer NOT NULL DEFAULT 0 CHECK (last_saved BETWEEN 0 AND 271),
  completed_at timestamptz,
  PRIMARY KEY (symbol,trade_day)
);
CREATE INDEX IF NOT EXISTS operational_kbar_backfill_state_retention
  ON control.operational_kbar_backfill_state(trade_day);
GRANT SELECT,INSERT,UPDATE,DELETE ON control.operational_session_kbars
  TO janus_private_api;
GRANT SELECT,INSERT,UPDATE,DELETE ON control.operational_kbar_backfill_state
  TO janus_private_api;
REVOKE ALL ON control.operational_session_kbars FROM PUBLIC;
REVOKE ALL ON control.operational_kbar_backfill_state FROM PUBLIC;

-- PHASE: acceptance
SELECT to_regclass('control.operational_session_kbars') IS NOT NULL,
       to_regclass('control.operational_kbar_backfill_state') IS NOT NULL,
       has_table_privilege('janus_private_api','control.operational_session_kbars','INSERT'),
       has_table_privilege('janus_private_api','control.operational_session_kbars','DELETE'),
       has_table_privilege('janus_private_api','control.operational_kbar_backfill_state','INSERT'),
       NOT has_table_privilege('janus_public_api','control.operational_session_kbars','SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('078_session_minute_kbar_backfill') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
