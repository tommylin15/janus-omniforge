# Intelligence Mart job

Feature computation, role analysis, validation, aggregation, and Mart writes
live here.

The current entrypoint is a one-shot runtime smoke. It requires separate
`CATALOG_DB_*` and `PUBLICATION_DB_*` settings, connects with TLS and bounded
timeouts, and fails unless PostgreSQL reports a private server address and the
Mart-specific roles have their expected schema grants. It never prints
passwords or performs feature/evidence writes.

`PostgreSQLAnalysisQueue` leases one persisted `analysis` execution with
`FOR UPDATE SKIP LOCKED`. Completion requires the processor to persist a
`gs://` artifact tied to the claimed immutable Core snapshot; claim/enqueue
success alone cannot mark the execution succeeded.
