\set ON_ERROR_STOP on

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM control.schema_migrations WHERE version='025_pilot_readiness') THEN
    RAISE EXCEPTION 'Pilot readiness migration is not recorded';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema='publication' AND table_name='pilot_release_baselines'
       AND column_name IN ('git_sha','image_digest','feature_revision','signal_revision','source_config_revision')
     GROUP BY table_schema,table_name HAVING count(*)=5
  ) THEN
    RAISE EXCEPTION 'Pilot baseline lineage columns are incomplete';
  END IF;
  IF to_regclass('publication.pilot_analysis_outcomes') IS NULL
     OR to_regclass('private.analysis_feedback') IS NULL
     OR to_regclass('publication.feedback_analysis_targets') IS NULL THEN
    RAISE EXCEPTION 'Pilot readiness relations are incomplete';
  END IF;
  IF has_table_privilege('janus_mart_publication','publication.pilot_analysis_outcomes','DELETE') THEN
    RAISE EXCEPTION 'Mart role can delete Pilot outcomes';
  END IF;
  IF NOT has_table_privilege('janus_private_api','publication.feedback_analysis_targets','SELECT')
     OR NOT has_table_privilege('janus_private_api','private.analysis_feedback','INSERT')
     OR has_table_privilege('janus_private_api','private.analysis_feedback','DELETE') THEN
    RAISE EXCEPTION 'Feedback privileges are not bounded';
  END IF;
  IF has_table_privilege('janus_control','private.users','REFERENCES') THEN
    RAISE EXCEPTION 'Temporary FK grant was not revoked';
  END IF;
END $$;

SET ROLE janus_mart_publication;
SELECT publication.register_pilot_baseline(
  '00000000-0000-4000-8000-0000000000f1', 'named_epoch', 'pilot-acceptance',
  'sha256:' || repeat('a',64), repeat('b',40), 'sha256:' || repeat('c',64),
  'gov-acceptance', 'prompt-acceptance', 'sha256:' || repeat('d',64),
  'schema-acceptance', 'feature-acceptance', 'signal-acceptance',
  'deterministic', 'model-acceptance', 'source-acceptance');
RESET ROLE;

DO $$
BEGIN
  IF (SELECT count(*) FROM publication.pilot_release_baselines
      WHERE epoch_name='pilot-acceptance') <> 1 THEN
    RAISE EXCEPTION 'Pilot baseline registration failed';
  END IF;
END $$;

ROLLBACK;
