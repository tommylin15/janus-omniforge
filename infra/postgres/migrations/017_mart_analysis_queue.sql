\set ON_ERROR_STOP on

GRANT USAGE ON SCHEMA control TO janus_mart_publication;
GRANT SELECT (
    execution_id, config_id, trigger_type, status, requested_symbols,
    requested_at, retry_count, claimed_by, claimed_until, request_options
) ON control.executions TO janus_mart_publication;

CREATE OR REPLACE FUNCTION control.claim_mart_analysis(p_worker_id text, p_lease_seconds integer)
RETURNS TABLE(execution_id text, config_id text, requested_symbols jsonb, retry_count integer, request_options jsonb)
LANGUAGE sql SECURITY DEFINER SET search_path = control, pg_catalog AS $$
    WITH candidate AS (
        SELECT e.execution_id FROM control.executions e
        WHERE e.trigger_type='analysis'
          AND e.status IN ('queued','retrying','running')
          AND (e.claimed_until IS NULL OR e.claimed_until < now())
        ORDER BY e.requested_at FOR UPDATE SKIP LOCKED LIMIT 1
    )
    UPDATE control.executions e
    SET status='running', claimed_by=p_worker_id,
        claimed_until=now()+(p_lease_seconds * interval '1 second'),
        started_at=COALESCE(e.started_at,now())
    FROM candidate
    WHERE e.execution_id=candidate.execution_id
    RETURNING e.execution_id::text,e.config_id,e.requested_symbols,e.retry_count,e.request_options;
$$;

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
    RETURN changed = 1;
END;
$$;

REVOKE ALL ON FUNCTION control.claim_mart_analysis(text, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION control.transition_mart_analysis(uuid, text, text, integer, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION control.claim_mart_analysis(text, integer) TO janus_mart_publication;
GRANT EXECUTE ON FUNCTION control.transition_mart_analysis(uuid, text, text, integer, text) TO janus_mart_publication;
GRANT UPDATE (
    status, started_at, finished_at, retry_count, error_code, claimed_by, claimed_until
) ON control.executions TO janus_mart_publication;

INSERT INTO control.schema_migrations(version) VALUES ('017_mart_analysis_queue')
ON CONFLICT (version) DO NOTHING;
