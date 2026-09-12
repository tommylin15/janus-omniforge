\set ON_ERROR_STOP on

SET ROLE janus_audit;

CREATE TABLE IF NOT EXISTS audit.governance_revision_heads (
    governance_key text PRIMARY KEY CHECK (governance_key ~ '^[a-z0-9_.:-]{1,80}$'),
    current_version bigint NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit.governance_revisions (
    revision_id uuid PRIMARY KEY,
    governance_key text NOT NULL REFERENCES audit.governance_revision_heads(governance_key),
    version bigint NOT NULL CHECK (version > 0),
    snapshot_version text NOT NULL CHECK (btrim(snapshot_version) <> ''),
    artifact_uri text NOT NULL CHECK (artifact_uri LIKE 'gs://%'),
    artifact_hash char(71) NOT NULL CHECK (artifact_hash ~ '^sha256:[0-9a-f]{64}$'),
    diff_artifact_uri text NOT NULL CHECK (diff_artifact_uri LIKE 'gs://%'),
    diff_artifact_hash char(71) NOT NULL CHECK (diff_artifact_hash ~ '^sha256:[0-9a-f]{64}$'),
    actor text NOT NULL CHECK (btrim(actor) <> ''),
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    retention_until date NOT NULL,
    UNIQUE (governance_key, version)
);

CREATE INDEX IF NOT EXISTS governance_revisions_retention
    ON audit.governance_revisions (retention_until, governance_key, version);

CREATE OR REPLACE VIEW audit.current_governance_revisions AS
SELECT revision_id, revision.governance_key, revision.version, snapshot_version,
       artifact_uri, artifact_hash, diff_artifact_uri, diff_artifact_hash,
       actor, reason, created_at, retention_until
FROM audit.governance_revisions revision
JOIN audit.governance_revision_heads head
  ON head.governance_key=revision.governance_key AND head.current_version=revision.version;

CREATE OR REPLACE FUNCTION audit.register_governance_revision(
    p_revision_id uuid, p_governance_key text, p_expected_version bigint,
    p_snapshot_version text, p_artifact_uri text, p_artifact_hash text,
    p_diff_artifact_uri text, p_diff_artifact_hash text,
    p_actor text, p_reason text, p_retention_until date
) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = audit, pg_catalog AS $$
DECLARE next_version bigint;
BEGIN
    INSERT INTO audit.governance_revision_heads(governance_key)
    VALUES (p_governance_key) ON CONFLICT (governance_key) DO NOTHING;
    UPDATE audit.governance_revision_heads
       SET current_version=current_version+1, updated_at=now()
     WHERE governance_key=p_governance_key AND current_version=p_expected_version
     RETURNING current_version INTO next_version;
    IF next_version IS NULL THEN
        RAISE EXCEPTION 'governance revision conflict' USING ERRCODE='40001';
    END IF;
    INSERT INTO audit.governance_revisions(
        revision_id, governance_key, version, snapshot_version,
        artifact_uri, artifact_hash, diff_artifact_uri, diff_artifact_hash,
        actor, reason, retention_until
    ) VALUES (
        p_revision_id, p_governance_key, next_version, p_snapshot_version,
        p_artifact_uri, p_artifact_hash, p_diff_artifact_uri, p_diff_artifact_hash,
        p_actor, p_reason, p_retention_until
    );
    RETURN next_version;
END;
$$;

CREATE OR REPLACE FUNCTION audit.prune_governance_revisions(p_before date, p_limit integer DEFAULT 100)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = audit, pg_catalog AS $$
DECLARE deleted integer;
BEGIN
    IF p_limit NOT BETWEEN 1 AND 1000 THEN
        RAISE EXCEPTION 'governance retention limit must be 1..1000';
    END IF;
    DELETE FROM audit.governance_revisions revision
     WHERE revision.ctid IN (
        SELECT candidate.ctid
          FROM audit.governance_revisions candidate
          JOIN audit.governance_revision_heads head USING (governance_key)
         WHERE candidate.retention_until < p_before AND candidate.version <> head.current_version
         ORDER BY candidate.retention_until, candidate.created_at
         LIMIT p_limit
     );
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RETURN deleted;
END;
$$;

REVOKE ALL ON audit.governance_revision_heads, audit.governance_revisions FROM PUBLIC, janus_web_control;
REVOKE ALL ON FUNCTION audit.register_governance_revision(
    uuid,text,bigint,text,text,text,text,text,text,text,date
) FROM PUBLIC;
REVOKE ALL ON FUNCTION audit.prune_governance_revisions(date,integer) FROM PUBLIC;
GRANT USAGE ON SCHEMA audit TO janus_web_control;
GRANT SELECT ON audit.current_governance_revisions TO janus_web_control;
GRANT EXECUTE ON FUNCTION audit.register_governance_revision(
    uuid,text,bigint,text,text,text,text,text,text,text,date
) TO janus_web_control;

ALTER ROLE janus_audit IN DATABASE janus_control SET statement_timeout = '15s';
ALTER ROLE janus_audit IN DATABASE janus_control SET idle_in_transaction_session_timeout = '15s';

RESET ROLE;

INSERT INTO control.schema_migrations(version) VALUES ('020_governance_audit')
ON CONFLICT (version) DO NOTHING;
