\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE janus_control;

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT c.conname
      INTO constraint_name
      FROM pg_constraint c
     WHERE c.conrelid = 'control.batch_occurrences'::regclass
       AND c.contype = 'c'
       AND pg_get_constraintdef(c.oid) LIKE '%status%'
       AND pg_get_constraintdef(c.oid) LIKE '%pending%'
       AND pg_get_constraintdef(c.oid) LIKE '%ambiguous%'
     ORDER BY c.conname
     LIMIT 1;

    IF constraint_name IS NULL THEN
        RAISE EXCEPTION 'batch occurrence status constraint not found';
    END IF;

    EXECUTE format(
        'ALTER TABLE control.batch_occurrences DROP CONSTRAINT %I',
        constraint_name
    );
END
$$;

ALTER TABLE control.batch_occurrences
    ADD CONSTRAINT batch_occurrences_status_check
    CHECK (state->>'status' IN (
        'pending',
        'dispatching',
        'running',
        'ambiguous',
        'succeeded',
        'failed',
        'skipped'
    ));

-- PHASE: acceptance
SELECT
    EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.conrelid = 'control.batch_occurrences'::regclass
           AND c.contype = 'c'
           AND c.conname = 'batch_occurrences_status_check'
           AND pg_get_constraintdef(c.oid) LIKE '%skipped%'
           AND pg_get_constraintdef(c.oid) LIKE '%succeeded%'
    ),
    NOT EXISTS (
        SELECT 1
          FROM control.batch_occurrences
         WHERE state->>'status' NOT IN (
             'pending',
             'dispatching',
             'running',
             'ambiguous',
             'succeeded',
             'failed',
             'skipped'
         )
    );

INSERT INTO control.schema_migrations(version)
VALUES ('049_batch_occurrence_skipped_status')
ON CONFLICT (version) DO NOTHING;

COMMIT;
