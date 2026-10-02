\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE janus_control;
CREATE TABLE IF NOT EXISTS control.batch_occurrences (
    occurrence_id text PRIMARY KEY,
    scheduled_at timestamptz NOT NULL,
    state jsonb NOT NULL CHECK (jsonb_typeof(state)='object'),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (state ? 'status'),
    CHECK (state->>'status' IN ('pending','dispatching','running','ambiguous','succeeded','failed'))
);
CREATE INDEX IF NOT EXISTS batch_occurrences_active_idx ON control.batch_occurrences(scheduled_at)
    WHERE state->>'status' IN ('dispatching','running','ambiguous');
CREATE TABLE IF NOT EXISTS control.batch_event_outbox (
    event_id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    exported_at timestamptz
);
CREATE INDEX IF NOT EXISTS batch_event_outbox_pending_idx ON control.batch_event_outbox(created_at)
    WHERE exported_at IS NULL;
REVOKE ALL ON control.batch_occurrences,control.batch_event_outbox FROM PUBLIC;
INSERT INTO control.schema_migrations(version) VALUES ('037_batch_controller') ON CONFLICT DO NOTHING;
COMMIT;
