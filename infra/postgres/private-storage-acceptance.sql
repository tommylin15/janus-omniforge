\set ON_ERROR_STOP on
BEGIN;

INSERT INTO private.users(user_id,google_sub,display_email) VALUES
  ('00000000-0000-4000-8000-0000000000a1','wbs-4c-storage-a','a@example.invalid'),
  ('00000000-0000-4000-8000-0000000000b2','wbs-4c-storage-b','b@example.invalid');
INSERT INTO private.assistant_threads(user_id,thread_id,runtime,model,assistant_profile) VALUES
  ('00000000-0000-4000-8000-0000000000a1','same-thread','codex','codex','default'),
  ('00000000-0000-4000-8000-0000000000b2','same-thread','codex','codex','default');
INSERT INTO private.assistant_turns(user_id,thread_id,turn_id,idempotency_key) VALUES
  ('00000000-0000-4000-8000-0000000000a1','same-thread','same-turn','turn-key'),
  ('00000000-0000-4000-8000-0000000000b2','same-thread','same-turn','turn-key');
INSERT INTO private.assistant_event_index
  (user_id,thread_id,turn_id,event_id,seq,event_type,payload_digest,idempotency_key) VALUES
  ('00000000-0000-4000-8000-0000000000a1','same-thread','same-turn','same-event',0,'text_delta','sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','event-key'),
  ('00000000-0000-4000-8000-0000000000b2','same-thread','same-turn','same-event',0,'text_delta','sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','event-key');
INSERT INTO private.assistant_event_index
  (user_id,thread_id,turn_id,event_id,seq,event_type,payload_digest,idempotency_key)
  VALUES ('00000000-0000-4000-8000-0000000000a1','same-thread','same-turn','same-event',0,'text_delta','sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','event-key')
  ON CONFLICT(user_id,thread_id,idempotency_key) DO NOTHING;

DO $$
BEGIN
  IF (SELECT count(*) FROM private.assistant_event_index WHERE thread_id='same-thread') <> 2 THEN
    RAISE EXCEPTION 'owner isolation or event replay failed';
  END IF;
  IF (SELECT count(*) FROM private.assistant_event_index
      WHERE user_id='00000000-0000-4000-8000-0000000000a1' AND thread_id='same-thread') <> 1 THEN
    RAISE EXCEPTION 'owner-scoped event query failed';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='private' AND table_name LIKE 'assistant_%'
      AND column_name ~ '(secret|password|credential|access_token|refresh_token|auth_cache|api_key)'
  ) THEN
    RAISE EXCEPTION 'credential-shaped assistant column found';
  END IF;
  IF has_table_privilege('janus_private_api','private.assistant_threads','DELETE') THEN
    RAISE EXCEPTION 'private API role must not hard-delete assistant threads';
  END IF;
END $$;

ROLLBACK;
