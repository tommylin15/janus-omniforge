\set ON_ERROR_STOP on

SET ROLE janus_publication;

CREATE OR REPLACE FUNCTION publication.review_mart_report(
    p_execution_id uuid, p_scope_type text, p_scope_id text, p_action text
) RETURNS TABLE(publication_status text, updated_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = publication, pg_catalog AS $$
DECLARE
    changed integer;
BEGIN
    IF p_action = 'block' THEN
        RETURN QUERY UPDATE publication.mart_report_index
            SET publication_status='blocked'
          WHERE execution_id=p_execution_id AND scope_type=p_scope_type
            AND scope_id=p_scope_id AND analysis_outcome='complete'
            AND publication_status IN ('publishable','published')
        RETURNING mart_report_index.publication_status, now();
    ELSIF p_action = 'unblock' THEN
        RETURN QUERY UPDATE publication.mart_report_index
            SET publication_status='publishable'
          WHERE execution_id=p_execution_id AND scope_type=p_scope_type
            AND scope_id=p_scope_id AND analysis_outcome='complete'
            AND publication_status='blocked'
        RETURNING mart_report_index.publication_status, now();
    ELSE
        RAISE EXCEPTION 'invalid Mart publication review action';
    END IF;
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed = 0 THEN
        RAISE EXCEPTION 'Mart report is not eligible for the requested publication transition';
    END IF;
END;
$$;

RESET ROLE;
GRANT EXECUTE ON FUNCTION publication.review_mart_report(uuid,text,text,text) TO janus_web_control;

INSERT INTO control.schema_migrations(version) VALUES ('022_mart_publication_review')
ON CONFLICT (version) DO NOTHING;
