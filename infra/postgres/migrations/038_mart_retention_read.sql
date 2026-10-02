\set ON_ERROR_STOP on
BEGIN;

-- Read only the public snapshot references required to protect cleanup.
GRANT SELECT (table_identifier, iceberg_snapshot_id, artifact_uri)
ON publication.mart_report_index TO janus_mart_publication;

INSERT INTO control.schema_migrations(version)
VALUES ('038_mart_retention_read') ON CONFLICT(version) DO NOTHING;

COMMIT;
