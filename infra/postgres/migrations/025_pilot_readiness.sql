\set ON_ERROR_STOP on

SET ROLE janus_publication;

CREATE TABLE IF NOT EXISTS publication.pilot_release_baselines (
    baseline_id uuid PRIMARY KEY,
    baseline_type text NOT NULL CHECK (baseline_type IN ('monthly','material_change','named_epoch')),
    epoch_name varchar(96) NOT NULL,
    lineage_hash char(71) NOT NULL UNIQUE CHECK (lineage_hash ~ '^sha256:[0-9a-f]{64}$'),
    git_sha varchar(64) NOT NULL CHECK (git_sha ~ '^[0-9a-f]{7,64}$'),
    image_digest char(71) NOT NULL CHECK (image_digest ~ '^sha256:[0-9a-f]{64}$'),
    governance_revision varchar(128) NOT NULL,
    prompt_version varchar(128) NOT NULL,
    prompt_hash char(71) NOT NULL CHECK (prompt_hash ~ '^sha256:[0-9a-f]{64}$'),
    schema_revision varchar(128) NOT NULL,
    model_provider varchar(64) NOT NULL,
    model_version varchar(128) NOT NULL,
    source_config_revision varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE publication.mart_report_index
    ADD COLUMN IF NOT EXISTS pilot_baseline_id uuid REFERENCES publication.pilot_release_baselines(baseline_id),
    ADD COLUMN IF NOT EXISTS membership_snapshot_hash char(71)
        CHECK (membership_snapshot_hash IS NULL OR membership_snapshot_hash ~ '^sha256:[0-9a-f]{64}$');

CREATE TABLE IF NOT EXISTS publication.pilot_analysis_outcomes (
    analysis_execution_id uuid NOT NULL,
    scope_type text NOT NULL CHECK (scope_type = 'symbol'),
    scope_id varchar(20) NOT NULL,
    analysis_as_of date NOT NULL,
    horizon_days smallint NOT NULL CHECK (horizon_days IN (5,20,60)),
    pilot_baseline_id uuid NOT NULL REFERENCES publication.pilot_release_baselines(baseline_id),
    membership_snapshot_hash char(71) NOT NULL CHECK (membership_snapshot_hash ~ '^sha256:[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('pending','valid','excluded')),
    exclusion_reason varchar(64),
    benchmark_id varchar(32) NOT NULL DEFAULT 'TAIEX',
    entry_date date,
    outcome_date date,
    return_ratio numeric(20,10),
    benchmark_return_ratio numeric(20,10),
    relative_return_ratio numeric(20,10),
    mfe_ratio numeric(20,10),
    mae_ratio numeric(20,10),
    price_snapshot_id bigint,
    benchmark_snapshot_id bigint,
    provenance_id char(71) NOT NULL CHECK (provenance_id ~ '^sha256:[0-9a-f]{64}$'),
    evaluated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (analysis_execution_id, scope_type, scope_id, horizon_days),
    FOREIGN KEY (analysis_execution_id, scope_type, scope_id)
        REFERENCES publication.mart_report_index(execution_id, scope_type, scope_id),
    CHECK ((status='excluded') = (exclusion_reason IS NOT NULL)),
    CHECK (status <> 'valid' OR (entry_date IS NOT NULL AND outcome_date IS NOT NULL
        AND return_ratio IS NOT NULL AND benchmark_return_ratio IS NOT NULL
        AND relative_return_ratio IS NOT NULL AND mfe_ratio IS NOT NULL AND mae_ratio IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS pilot_analysis_outcomes_pending
    ON publication.pilot_analysis_outcomes(status, analysis_as_of, scope_id)
    WHERE status='pending';

CREATE OR REPLACE FUNCTION publication.register_pilot_baseline(
    p_baseline_id uuid, p_baseline_type text, p_epoch_name text, p_lineage_hash text,
    p_git_sha text, p_image_digest text, p_governance_revision text,
    p_prompt_version text, p_prompt_hash text, p_schema_revision text,
    p_model_provider text, p_model_version text, p_source_config_revision text
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=publication,pg_catalog AS $$
DECLARE existing publication.pilot_release_baselines%ROWTYPE;
BEGIN
    INSERT INTO publication.pilot_release_baselines(
        baseline_id,baseline_type,epoch_name,lineage_hash,git_sha,image_digest,
        governance_revision,prompt_version,prompt_hash,schema_revision,
        model_provider,model_version,source_config_revision
    ) VALUES (
        p_baseline_id,p_baseline_type,p_epoch_name,p_lineage_hash,p_git_sha,p_image_digest,
        p_governance_revision,p_prompt_version,p_prompt_hash,p_schema_revision,
        p_model_provider,p_model_version,p_source_config_revision
    ) ON CONFLICT (lineage_hash) DO NOTHING;
    SELECT * INTO existing FROM publication.pilot_release_baselines WHERE lineage_hash=p_lineage_hash;
    IF existing.baseline_id <> p_baseline_id OR existing.git_sha <> p_git_sha
       OR existing.image_digest <> p_image_digest OR existing.prompt_hash <> p_prompt_hash THEN
        RAISE EXCEPTION 'immutable Pilot baseline conflict';
    END IF;
    RETURN existing.baseline_id;
END;
$$;

CREATE OR REPLACE FUNCTION publication.register_pilot_mart_report(
    p_execution_id uuid, p_analysis_as_of date, p_scope_type text, p_scope_id text,
    p_core_snapshot_id text, p_artifact_uri text, p_artifact_hash text,
    p_deterministic_hash text, p_table_identifier text, p_iceberg_snapshot_id bigint,
    p_schema_version text, p_feature_version text, p_model_version text,
    p_governance_snapshot_version text, p_prompt_version text, p_prompt_hash text,
    p_completeness double precision, p_confidence double precision,
    p_data_quality text, p_analysis_outcome text, p_publication_status text,
    p_retention_until date, p_pilot_baseline_id uuid, p_membership_snapshot_hash text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=publication,pg_catalog AS $$
DECLARE changed integer;
BEGIN
    PERFORM publication.register_mart_report(
        p_execution_id,p_analysis_as_of,p_scope_type,p_scope_id,p_core_snapshot_id,
        p_artifact_uri,p_artifact_hash,p_deterministic_hash,p_table_identifier,
        p_iceberg_snapshot_id,p_schema_version,p_feature_version,p_model_version,
        p_governance_snapshot_version,p_prompt_version,p_prompt_hash,p_completeness,
        p_confidence,p_data_quality,p_analysis_outcome,p_publication_status,p_retention_until
    );
    UPDATE publication.mart_report_index
       SET pilot_baseline_id=p_pilot_baseline_id,
           membership_snapshot_hash=p_membership_snapshot_hash
     WHERE execution_id=p_execution_id AND scope_type=p_scope_type AND scope_id=p_scope_id
       AND (pilot_baseline_id IS NULL OR pilot_baseline_id=p_pilot_baseline_id)
       AND (membership_snapshot_hash IS NULL OR membership_snapshot_hash=p_membership_snapshot_hash);
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 1 THEN RAISE EXCEPTION 'immutable Pilot report lineage conflict'; END IF;
    RETURN true;
END;
$$;

RESET ROLE;

SET ROLE janus_control;

CREATE TABLE IF NOT EXISTS private.analysis_feedback (
    feedback_id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES private.users(user_id),
    analysis_execution_id uuid NOT NULL,
    scope_type text NOT NULL CHECK (scope_type IN ('market','industry','symbol')),
    scope_id varchar(80) NOT NULL,
    analysis_hash char(71) NOT NULL CHECK (analysis_hash ~ '^sha256:[0-9a-f]{64}$'),
    feedback text NOT NULL CHECK (feedback IN ('useful','neutral','misleading')),
    reason text CHECK (reason IS NULL OR reason IN (
        'discovered_risk','useful_context','already_known','too_generic','stale',
        'missing_data','wrong_interpretation','other')),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    idempotency_key varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, analysis_execution_id, scope_type, scope_id),
    UNIQUE (user_id, idempotency_key)
);

RESET ROLE;

CREATE OR REPLACE VIEW publication.feedback_analysis_targets
WITH (security_barrier=true) AS
SELECT execution_id,scope_type,scope_id,deterministic_hash
FROM publication.publishable_mart_reports;

REVOKE ALL ON publication.pilot_release_baselines,publication.pilot_analysis_outcomes FROM PUBLIC;
REVOKE ALL ON publication.feedback_analysis_targets FROM PUBLIC;
REVOKE ALL ON private.analysis_feedback FROM PUBLIC;
REVOKE ALL ON FUNCTION publication.register_pilot_baseline(
    uuid,text,text,text,text,text,text,text,text,text,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION publication.register_pilot_mart_report(
    uuid,date,text,text,text,text,text,text,text,bigint,text,text,text,text,text,text,
    double precision,double precision,text,text,text,date,uuid,text) FROM PUBLIC;

GRANT SELECT ON publication.pilot_release_baselines TO janus_mart_publication,janus_web_control;
GRANT SELECT,INSERT,UPDATE ON publication.pilot_analysis_outcomes TO janus_mart_publication;
REVOKE DELETE,TRUNCATE ON publication.pilot_analysis_outcomes FROM janus_mart_publication;
GRANT EXECUTE ON FUNCTION publication.register_pilot_baseline(
    uuid,text,text,text,text,text,text,text,text,text,text,text,text) TO janus_mart_publication;
GRANT EXECUTE ON FUNCTION publication.register_pilot_mart_report(
    uuid,date,text,text,text,text,text,text,text,bigint,text,text,text,text,text,text,
    double precision,double precision,text,text,text,date,uuid,text) TO janus_mart_publication;
GRANT SELECT ON publication.feedback_analysis_targets TO janus_private_api;
GRANT SELECT,INSERT,UPDATE ON private.analysis_feedback TO janus_private_api;
GRANT SELECT,DELETE ON private.analysis_feedback TO janus_private_pipeline;

INSERT INTO control.schema_migrations(version) VALUES ('025_pilot_readiness')
ON CONFLICT(version) DO NOTHING;
