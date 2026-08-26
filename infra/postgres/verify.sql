SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication
FROM pg_roles
WHERE rolname LIKE 'janus_%'
ORDER BY rolname;
SHOW max_connections;
SHOW shared_buffers;
SHOW work_mem;
SHOW statement_timeout;
SHOW idle_in_transaction_session_timeout;

