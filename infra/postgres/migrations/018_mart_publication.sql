\set ON_ERROR_STOP on

SET ROLE janus_publication;

CREATE TABLE IF NOT EXISTS publication.mart_report_index (
    execution_id uuid NOT NULL,
    analysis_as_of date NOT NULL,
    scope_type text NOT NULL CHECK (scope_type IN ('market','industry','symbol')),
    scope_id text NOT NULL CHECK (btrim(scope_id) <> ''),
    core_snapshot_id text NOT NULL CHECK (btrim(core_snapshot_id) <> ''),
    artifact_uri text NOT NULL CHECK (artifact_uri LIKE 'gs://%'),
    artifact_hash char(71) NOT NULL CHECK (artifact_hash ~ '^sha256:[0-9a-f]{64}$'),
    deterministic_hash char(71) NOT NULL CHECK (deterministic_hash ~ '^sha256:[0-9a-f]{64}$'),
    table_identifier text NOT NULL CHECK (table_identifier = 'mart.mart_scoped_analysis_v1'),
    iceberg_snapshot_id bigint NOT NULL,
    schema_version text NOT NULL,
    feature_version text NOT NULL,
    model_version text NOT NULL,
    governance_snapshot_version text NOT NULL,
    prompt_version text NOT NULL,
    prompt_hash char(71) NOT NULL CHECK (prompt_hash ~ '^sha256:[0-9a-f]{64}$'),
    completeness double precision NOT NULL CHECK (completeness BETWEEN 0 AND 1),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    data_quality text NOT NULL CHECK (data_quality IN ('good','warning','critical','unknown')),
    analysis_outcome text NOT NULL CHECK (analysis_outcome IN ('complete','invalid','review_required','risk_blocked','insufficient_data')),
    publication_status text NOT NULL CHECK (publication_status IN ('draft','blocked','publishable','published','superseded')),
    created_at timestamptz NOT NULL DEFAULT now(),
    ready_at timestamptz,
    retention_until date NOT NULL,
    PRIMARY KEY (execution_id, scope_type, scope_id)
);

CREATE INDEX IF NOT EXISTS mart_report_index_history
    ON publication.mart_report_index (scope_type, scope_id, analysis_as_of DESC);

CREATE TABLE IF NOT EXISTS publication.mart_report_outbox (
    execution_id uuid NOT NULL,
    scope_type text NOT NULL,
    scope_id text NOT NULL,
    event_type text NOT NULL CHECK (event_type = 'mart.report.ready.v1'),
    artifact_uri text NOT NULL CHECK (artifact_uri LIKE 'gs://%'),
    publication_status text NOT NULL CHECK (publication_status IN ('publishable','published')),
    schema_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz,
    PRIMARY KEY (execution_id, scope_type, scope_id),
    FOREIGN KEY (execution_id, scope_type, scope_id)
        REFERENCES publication.mart_report_index (execution_id, scope_type, scope_id)
);

CREATE OR REPLACE VIEW publication.publishable_mart_reports AS
SELECT execution_id, analysis_as_of, scope_type, scope_id, core_snapshot_id,
       artifact_uri, artifact_hash, deterministic_hash, table_identifier,
       iceberg_snapshot_id, schema_version, feature_version, model_version,
       governance_snapshot_version, prompt_version, prompt_hash,
       completeness, confidence, data_quality, analysis_outcome,
       publication_status, created_at, ready_at
FROM publication.mart_report_index
WHERE analysis_outcome = 'complete'
  AND publication_status IN ('publishable','published')
  AND ready_at IS NOT NULL;

CREATE OR REPLACE FUNCTION publication.register_mart_report(
    p_execution_id uuid, p_analysis_as_of date, p_scope_type text, p_scope_id text,
    p_core_snapshot_id text, p_artifact_uri text, p_artifact_hash text,
    p_deterministic_hash text, p_table_identifier text, p_iceberg_snapshot_id bigint,
    p_schema_version text, p_feature_version text, p_model_version text,
    p_governance_snapshot_version text, p_prompt_version text, p_prompt_hash text,
    p_completeness double precision, p_confidence double precision,
    p_data_quality text, p_analysis_outcome text, p_publication_status text,
    p_retention_until date
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = publication, pg_catalog AS $$
DECLARE existing publication.mart_report_index%ROWTYPE;
BEGIN
    INSERT INTO publication.mart_report_index (
        execution_id, analysis_as_of, scope_type, scope_id, core_snapshot_id,
        artifact_uri, artifact_hash, deterministic_hash, table_identifier,
        iceberg_snapshot_id, schema_version, feature_version, model_version,
        governance_snapshot_version, prompt_version, prompt_hash, completeness,
        confidence, data_quality, analysis_outcome, publication_status, retention_until
    ) VALUES (
        p_execution_id, p_analysis_as_of, p_scope_type, p_scope_id, p_core_snapshot_id,
        p_artifact_uri, p_artifact_hash, p_deterministic_hash, p_table_identifier,
        p_iceberg_snapshot_id, p_schema_version, p_feature_version, p_model_version,
        p_governance_snapshot_version, p_prompt_version, p_prompt_hash, p_completeness,
        p_confidence, p_data_quality, p_analysis_outcome, p_publication_status, p_retention_until
    ) ON CONFLICT (execution_id, scope_type, scope_id) DO NOTHING;

    SELECT * INTO existing FROM publication.mart_report_index
    WHERE execution_id=p_execution_id AND scope_type=p_scope_type AND scope_id=p_scope_id;
    IF existing.artifact_uri <> p_artifact_uri
       OR existing.artifact_hash <> p_artifact_hash
       OR existing.deterministic_hash <> p_deterministic_hash
       OR existing.iceberg_snapshot_id <> p_iceberg_snapshot_id THEN
        RAISE EXCEPTION 'immutable Mart publication conflict';
    END IF;

    RETURN true;
END;
$$;

RESET ROLE;

CREATE OR REPLACE FUNCTION control.transition_mart_analysis(
    p_execution_id uuid, p_worker_id text, p_status text, p_retry_count integer, p_error_code text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = control, pg_catalog AS $$
DECLARE changed integer;
BEGIN
    UPDATE control.executions
    SET status=p_status,retry_count=p_retry_count,error_code=p_error_code,
        finished_at=CASE WHEN p_status IN ('succeeded','failed') THEN now() END,
        claimed_by=NULL,claimed_until=NULL
    WHERE execution_id=p_execution_id AND trigger_type='analysis'
      AND status='running' AND claimed_by=p_worker_id;
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed = 1 AND p_status = 'succeeded' THEN
        UPDATE publication.mart_report_index
        SET ready_at=COALESCE(ready_at, now())
        WHERE execution_id=p_execution_id AND analysis_outcome='complete'
          AND publication_status IN ('publishable','published');
        INSERT INTO publication.mart_report_outbox (
            execution_id, scope_type, scope_id, event_type, artifact_uri,
            publication_status, schema_version
        ) SELECT execution_id, scope_type, scope_id, 'mart.report.ready.v1',
                 artifact_uri, publication_status, '1.0.0'
          FROM publication.mart_report_index
         WHERE execution_id=p_execution_id AND ready_at IS NOT NULL
        ON CONFLICT (execution_id, scope_type, scope_id) DO NOTHING;
    END IF;
    RETURN changed = 1;
END;
$$;

REVOKE ALL ON publication.mart_report_index, publication.mart_report_outbox FROM janus_mart_publication;
REVOKE ALL ON FUNCTION publication.register_mart_report(
    uuid,date,text,text,text,text,text,text,text,bigint,text,text,text,text,text,text,
    double precision,double precision,text,text,text,date
) FROM PUBLIC;
REVOKE ALL ON FUNCTION control.transition_mart_analysis(uuid, text, text, integer, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION publication.register_mart_report(
    uuid,date,text,text,text,text,text,text,text,bigint,text,text,text,text,text,text,
    double precision,double precision,text,text,text,date
) TO janus_mart_publication;
GRANT EXECUTE ON FUNCTION control.transition_mart_analysis(uuid, text, text, integer, text) TO janus_mart_publication;
GRANT SELECT ON publication.publishable_mart_reports TO janus_mart_publication;

INSERT INTO control.schema_migrations(version) VALUES ('018_mart_publication')
ON CONFLICT (version) DO NOTHING;
