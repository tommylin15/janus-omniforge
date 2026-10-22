\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- Private, append-only switch: public/private API cannot enable a research
-- candidate. The read path checks this state on every response, so rollback
-- immediately hides XGBoost without rewriting historical immutable products.
CREATE TABLE IF NOT EXISTS private.risk_model_activation (
    activation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mode text NOT NULL CHECK (mode IN ('ACTIVE', 'DETERMINISTIC')),
    model_sha256 varchar(64),
    source_git_sha varchar(40) NOT NULL CHECK (source_git_sha ~ '^[0-9a-f]{40}$'),
    gcs_registry_generation bigint NOT NULL CHECK (gcs_registry_generation > 0),
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((mode = 'ACTIVE' AND model_sha256 =
      '36c77d0168a1d667223ab915c9b08fd2c1c6608f9f7db2fc046204e922854044')
      OR (mode = 'DETERMINISTIC' AND model_sha256 IS NULL)),
    UNIQUE (gcs_registry_generation)
);
-- No initial ACTIVE default: absence is deterministic.
REVOKE ALL ON private.risk_model_activation FROM PUBLIC;
GRANT SELECT ON private.risk_model_activation TO janus_private_api,janus_mart_publication;
GRANT INSERT ON private.risk_model_activation TO janus_mart_publication;
GRANT USAGE ON SEQUENCE private.risk_model_activation_activation_id_seq TO janus_mart_publication;

-- Successful write is never an update of old rows.
CREATE OR REPLACE FUNCTION control.risk_activation_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'risk activation ledger is append-only';
END;
$$;
REVOKE ALL ON FUNCTION control.risk_activation_immutable() FROM PUBLIC;
DROP TRIGGER IF EXISTS risk_activation_immutable ON private.risk_model_activation;
CREATE TRIGGER risk_activation_immutable BEFORE UPDATE OR DELETE
ON private.risk_model_activation FOR EACH ROW
EXECUTE FUNCTION control.risk_activation_immutable();

-- PHASE: acceptance
SELECT
    has_table_privilege('janus_private_api','private.risk_model_activation','SELECT'),
    NOT has_table_privilege('janus_private_api','private.risk_model_activation','INSERT'),
    has_table_privilege('janus_mart_publication','private.risk_model_activation','INSERT');
INSERT INTO control.schema_migrations(version) VALUES ('068_risk_model_activation') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
