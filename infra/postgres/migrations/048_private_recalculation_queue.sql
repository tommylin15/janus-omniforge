-- Requires ingestion runtime with 048 allow-list support.
\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS private.recalculation_requests (
    request_id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    requested_ledger_version bigint NOT NULL CHECK (requested_ledger_version >= 0),
    status varchar(24) NOT NULL CHECK (status IN (
        'QUEUED','RUNNING','CANCEL_REQUESTED','SUCCEEDED','FAILED','CANCELLED'
    )),
    trigger_source varchar(24) NOT NULL CHECK (trigger_source IN ('mutation','manual')),
    lease_token uuid,
    worker_execution text,
    worker_task_index integer CHECK (worker_task_index IS NULL OR worker_task_index >= 0),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    error_code varchar(80),
    safe_message varchar(300),
    admin_actor varchar(254),
    admin_action varchar(32) CHECK (admin_action IS NULL OR admin_action IN ('cancel','force_failed')),
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS recalculation_one_active_owner_idx
ON private.recalculation_requests(user_id)
WHERE status IN ('QUEUED','RUNNING','CANCEL_REQUESTED');

CREATE INDEX IF NOT EXISTS recalculation_queue_idx
ON private.recalculation_requests(status, requested_at, request_id);

CREATE TABLE IF NOT EXISTS private.recalculation_dispatch (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    active boolean NOT NULL DEFAULT false,
    generation bigint NOT NULL DEFAULT 0 CHECK (generation >= 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO private.recalculation_dispatch(singleton, active, generation)
VALUES (true, false, 0)
ON CONFLICT(singleton) DO NOTHING;

INSERT INTO control.admin_settings(setting_key,value_json,version,updated_by)
VALUES ('private_recalc_workers','{"workers":2}'::jsonb,1,'migration:048')
ON CONFLICT(setting_key) DO NOTHING;

GRANT SELECT, INSERT, UPDATE ON private.recalculation_requests TO janus_private_api;
GRANT SELECT, UPDATE ON private.recalculation_dispatch TO janus_private_api;
GRANT SELECT, UPDATE ON private.recalculation_requests TO janus_private_pipeline;
GRANT SELECT, UPDATE ON private.recalculation_dispatch TO janus_private_pipeline;

-- PHASE: acceptance
SELECT
  has_table_privilege('janus_private_api','private.recalculation_requests','SELECT'),
  has_table_privilege('janus_private_api','private.recalculation_requests','INSERT'),
  has_table_privilege('janus_private_api','private.recalculation_requests','UPDATE'),
  has_table_privilege('janus_private_pipeline','private.recalculation_requests','SELECT'),
  has_table_privilege('janus_private_pipeline','private.recalculation_requests','UPDATE'),
  has_table_privilege('janus_private_api','private.recalculation_dispatch','UPDATE'),
  has_table_privilege('janus_private_pipeline','private.recalculation_dispatch','UPDATE'),
  EXISTS (
    SELECT 1 FROM control.admin_settings
    WHERE setting_key='private_recalc_workers'
      AND (value_json->>'workers')::int BETWEEN 2 AND 8
  );

INSERT INTO control.schema_migrations(version)
VALUES ('048_private_recalculation_queue')
ON CONFLICT(version) DO NOTHING;

RESET ROLE;
COMMIT;
