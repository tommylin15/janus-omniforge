\set ON_ERROR_STOP on

BEGIN;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('janus_web_control','janus_web_catalog','janus_public_api')
             AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication)) THEN
    RAISE EXCEPTION 'web runtime role is privileged';
  END IF;
  IF has_table_privilege('janus_public_api', 'publication.mart_report_index', 'SELECT') THEN
    RAISE EXCEPTION 'public API can read the owner table';
  END IF;
  IF NOT has_table_privilege('janus_public_api', 'publication.publishable_mart_reports', 'SELECT') THEN
    RAISE EXCEPTION 'public API cannot read publishable view';
  END IF;
END $$;

INSERT INTO control.stock_master(symbol, name, market, enabled)
VALUES ('JANUS_OK', 'acceptance enabled', 'TWSE', true),
       ('JANUS_OFF', 'acceptance disabled', 'TWSE', false)
ON CONFLICT (symbol) DO UPDATE SET enabled=EXCLUDED.enabled;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM publication.enabled_stock_symbols WHERE symbol='JANUS_OK')
     OR EXISTS (SELECT 1 FROM publication.enabled_stock_symbols WHERE symbol='JANUS_OFF') THEN
    RAISE EXCEPTION 'enabled stock publication regression';
  END IF;
END $$;

INSERT INTO publication.mart_report_index(
  execution_id, analysis_as_of, scope_type, scope_id, core_snapshot_id,
  artifact_uri, artifact_hash, deterministic_hash, table_identifier,
  iceberg_snapshot_id, schema_version, feature_version, model_version,
  governance_snapshot_version, prompt_version, prompt_hash, completeness,
  confidence, data_quality, analysis_outcome, publication_status, ready_at,
  retention_until
) VALUES
('00000000-0000-0000-0000-000000000061', CURRENT_DATE, 'symbol', 'JANUS_OK', 'acceptance',
 'gs://acceptance/published', 'sha256:' || repeat('1',64), 'sha256:' || repeat('2',64),
 'mart.mart_scoped_analysis_v1', 61, '1', '1', '1', '1', '1', 'sha256:' || repeat('3',64),
 1, 1, 'good', 'complete', 'published', now(), CURRENT_DATE + 1),
('00000000-0000-0000-0000-000000000062', CURRENT_DATE + 1, 'symbol', 'JANUS_OK', 'acceptance',
 'gs://acceptance/blocked', 'sha256:' || repeat('4',64), 'sha256:' || repeat('5',64),
 'mart.mart_scoped_analysis_v1', 62, '1', '1', '1', '1', '1', 'sha256:' || repeat('6',64),
 1, 1, 'good', 'complete', 'blocked', now(), CURRENT_DATE + 1)
ON CONFLICT DO NOTHING;

DO $$
BEGIN
  IF (SELECT count(*) FROM publication.publishable_mart_reports
      WHERE scope_type='symbol' AND scope_id='JANUS_OK') <> 1 THEN
    RAISE EXCEPTION 'blocked publication escaped the fail-closed view';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='publication'
                 AND indexname='mart_report_index_history') THEN
    RAISE EXCEPTION 'publication history index is missing';
  END IF;
END $$;

ROLLBACK;
