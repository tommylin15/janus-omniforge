\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS private.assistant_threads (
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    thread_id varchar(128) NOT NULL,
    runtime varchar(16) NOT NULL CHECK (runtime IN ('openrouter','gemini','codex')),
    model varchar(256) NOT NULL,
    assistant_profile varchar(128) NOT NULL,
    skill_profile varchar(128),
    parent_thread_id varchar(128),
    status varchar(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ARCHIVED','DELETING')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, thread_id),
    FOREIGN KEY (user_id, parent_thread_id) REFERENCES private.assistant_threads(user_id, thread_id)
);

CREATE TABLE IF NOT EXISTS private.assistant_turns (
    user_id uuid NOT NULL,
    thread_id varchar(128) NOT NULL,
    turn_id varchar(128) NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','COMPLETED','CANCELLED','ERROR')),
    skill_id varchar(128),
    skill_revision integer CHECK (skill_revision > 0),
    context_artifact_ref text,
    continuation jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key varchar(128) NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    PRIMARY KEY (user_id, thread_id, turn_id),
    UNIQUE (user_id, thread_id, idempotency_key),
    FOREIGN KEY (user_id, thread_id) REFERENCES private.assistant_threads(user_id, thread_id) ON DELETE CASCADE,
    CHECK ((skill_id IS NULL) = (skill_revision IS NULL))
);

CREATE TABLE IF NOT EXISTS private.assistant_event_index (
    user_id uuid NOT NULL,
    thread_id varchar(128) NOT NULL,
    turn_id varchar(128) NOT NULL,
    event_id varchar(128) NOT NULL,
    seq bigint NOT NULL CHECK (seq >= 0),
    event_type varchar(32) NOT NULL CHECK (event_type IN ('text_delta','item_upsert','tool_request','tool_result','approval_request','approval_resolved','citation','usage','turn_completed','turn_cancelled','turn_error')),
    payload_digest char(71) NOT NULL CHECK (payload_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_ref text,
    status varchar(16) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PERSISTED')),
    idempotency_key varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    persisted_at timestamptz,
    PRIMARY KEY (user_id, thread_id, event_id),
    UNIQUE (user_id, thread_id, seq),
    UNIQUE (user_id, thread_id, idempotency_key),
    FOREIGN KEY (user_id, thread_id, turn_id) REFERENCES private.assistant_turns(user_id, thread_id, turn_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS private.assistant_skill_revisions (
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    skill_id varchar(128) NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    content_digest char(71) NOT NULL CHECK (content_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_ref text,
    status varchar(16) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PERSISTED')),
    idempotency_key varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, skill_id, revision),
    UNIQUE (user_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS private.assistant_skill_state (
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    skill_id varchar(128) NOT NULL,
    current_revision integer NOT NULL CHECK (current_revision > 0),
    enabled boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, skill_id),
    FOREIGN KEY (user_id, skill_id, current_revision)
      REFERENCES private.assistant_skill_revisions(user_id, skill_id, revision)
);

CREATE TABLE IF NOT EXISTS private.assistant_approvals (
    user_id uuid NOT NULL,
    thread_id varchar(128) NOT NULL,
    turn_id varchar(128) NOT NULL,
    request_id varchar(128) NOT NULL,
    operation varchar(64) NOT NULL,
    scope varchar(128) NOT NULL,
    params_digest char(71) NOT NULL CHECK (params_digest ~ '^sha256:[0-9a-f]{64}$'),
    status varchar(16) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','DENIED','EXPIRED','CANCELLED')),
    artifact_ref text NOT NULL,
    expires_at timestamptz NOT NULL,
    resolved_at timestamptz,
    PRIMARY KEY (user_id, thread_id, turn_id, request_id),
    FOREIGN KEY (user_id, thread_id, turn_id) REFERENCES private.assistant_turns(user_id, thread_id, turn_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS private.assistant_usage_reservations (
    user_id uuid NOT NULL,
    thread_id varchar(128) NOT NULL,
    reservation_id varchar(128) NOT NULL,
    provider varchar(16) NOT NULL CHECK (provider IN ('openrouter','gemini','codex')),
    units bigint NOT NULL CHECK (units > 0),
    status varchar(16) NOT NULL DEFAULT 'RESERVED' CHECK (status IN ('RESERVED','COMMITTED','RELEASED')),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, thread_id, reservation_id),
    FOREIGN KEY (user_id, thread_id) REFERENCES private.assistant_threads(user_id, thread_id) ON DELETE CASCADE
);

ALTER TABLE private.deletion_requests DROP CONSTRAINT IF EXISTS deletion_requests_status_check;
ALTER TABLE private.deletion_requests ADD CONSTRAINT deletion_requests_status_check
  CHECK (status IN ('QUEUED','CLEANUP_PENDING','COMPLETED'));
ALTER TABLE private.deletion_requests ADD COLUMN IF NOT EXISTS cleanup_pending text[] NOT NULL DEFAULT '{}';
ALTER TABLE private.deletion_requests DROP CONSTRAINT IF EXISTS deletion_requests_cleanup_pending_check;
ALTER TABLE private.deletion_requests ADD CONSTRAINT deletion_requests_cleanup_pending_check
  CHECK (cardinality(cleanup_pending) <= 8);

CREATE INDEX IF NOT EXISTS assistant_threads_user_updated_idx ON private.assistant_threads(user_id, updated_at DESC, thread_id);
CREATE INDEX IF NOT EXISTS assistant_turns_user_thread_started_idx ON private.assistant_turns(user_id, thread_id, started_at DESC);
CREATE INDEX IF NOT EXISTS assistant_events_user_thread_seq_idx ON private.assistant_event_index(user_id, thread_id, seq);
CREATE INDEX IF NOT EXISTS assistant_approvals_user_pending_idx ON private.assistant_approvals(user_id, status, expires_at);
CREATE INDEX IF NOT EXISTS assistant_skills_user_status_idx ON private.assistant_skill_revisions(user_id, status, skill_id, revision DESC);
CREATE INDEX IF NOT EXISTS assistant_usage_user_status_idx ON private.assistant_usage_reservations(user_id, status, expires_at);

GRANT SELECT, INSERT, UPDATE ON private.assistant_threads, private.assistant_turns,
  private.assistant_event_index, private.assistant_skill_revisions, private.assistant_skill_state,
  private.assistant_approvals, private.assistant_usage_reservations TO janus_private_api;
GRANT SELECT, DELETE ON private.assistant_threads, private.assistant_turns, private.assistant_event_index,
  private.assistant_skill_revisions, private.assistant_skill_state, private.assistant_approvals,
  private.assistant_usage_reservations TO janus_private_pipeline;
GRANT UPDATE (status, cleanup_pending) ON private.deletion_requests TO janus_private_pipeline;

INSERT INTO control.schema_migrations(version) VALUES ('016_private_assistant_storage') ON CONFLICT(version) DO NOTHING;
