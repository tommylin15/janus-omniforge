\set ON_ERROR_STOP on
SELECT version FROM control.schema_migrations
 WHERE version IN ('020_governance_audit', '021_public_api_role') ORDER BY version;
SELECT to_regclass('audit.governance_revision_heads') IS NOT NULL AS governance_heads_ready,
       to_regclass('audit.governance_revisions') IS NOT NULL AS governance_revisions_ready;
SELECT has_table_privilege('janus_public_api', 'publication.publishable_mart_reports', 'SELECT') AS public_view_select,
       has_table_privilege('janus_public_api', 'publication.mart_report_index', 'SELECT') AS public_index_select;
SELECT has_function_privilege(
    'janus_web_control',
    'audit.register_governance_revision(uuid,text,bigint,text,text,text,text,text,text,text,date)',
    'EXECUTE'
) AS governance_cas_execute;
