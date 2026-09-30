\set ON_ERROR_STOP on
BEGIN;

-- Pilot outcome evaluation reads public report metadata; publication writes
-- remain restricted to the existing registration functions.
GRANT SELECT (execution_id, scope_type, scope_id, analysis_as_of,
              pilot_baseline_id, membership_snapshot_hash,
              analysis_outcome, publication_status)
ON publication.mart_report_index TO janus_mart_publication;

INSERT INTO control.schema_migrations(version)
VALUES ('035_mart_outcome_read') ON CONFLICT(version) DO NOTHING;

COMMIT;
