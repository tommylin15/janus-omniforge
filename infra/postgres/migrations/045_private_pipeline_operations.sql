\set ON_ERROR_STOP on
BEGIN;
-- Retry-safe: CREATE/GRANT/INSERT are idempotent; a blocked dev attempt may be rerun after ingestion is idle.
SET ROLE janus_control;

-- One row of deidentified operational evidence. No owner, symbol, trade, or
-- holdings content is allowed in this table.
CREATE TABLE IF NOT EXISTS control.private_pipeline_status (
    pipeline_name text PRIMARY KEY,
    checkpoint_change_id bigint NOT NULL DEFAULT 0 CHECK (checkpoint_change_id >= 0),
    latest_change_id bigint NOT NULL DEFAULT 0 CHECK (latest_change_id >= 0),
    pending_changes bigint NOT NULL DEFAULT 0 CHECK (pending_changes >= 0),
    latest_ledger_version bigint NOT NULL DEFAULT 0 CHECK (latest_ledger_version >= 0),
    valuation_date date,
    last_result text NOT NULL CHECK (last_result IN ('running','succeeded','failed')),
    execution_name text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (checkpoint_change_id <= latest_change_id)
);

REVOKE ALL ON control.private_pipeline_status FROM PUBLIC;
GRANT USAGE ON SCHEMA control TO janus_private_pipeline;
GRANT SELECT ON control.private_pipeline_status TO janus_web_control;
GRANT SELECT, INSERT, UPDATE ON control.private_pipeline_status TO janus_private_pipeline;

-- PHASE: acceptance
SELECT
  has_table_privilege('janus_web_control','control.private_pipeline_status','SELECT'),
  has_table_privilege('janus_private_pipeline','control.private_pipeline_status','SELECT'),
  has_table_privilege('janus_private_pipeline','control.private_pipeline_status','INSERT'),
  has_table_privilege('janus_private_pipeline','control.private_pipeline_status','UPDATE'),
  NOT has_table_privilege('janus_public_api','control.private_pipeline_status','SELECT');

INSERT INTO control.schema_migrations(version)
VALUES ('045_private_pipeline_operations')
ON CONFLICT(version) DO NOTHING;

RESET ROLE;
COMMIT;
