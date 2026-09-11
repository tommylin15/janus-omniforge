# Intelligence Mart job

This one-shot Cloud Run Job consumes a persisted analysis execution, reads only
the exact Core Iceberg snapshots carried by its immutable manifest, computes
deterministic features and five role payloads, validates PIT evidence, aggregates
the result, and writes public Iceberg v2/Parquet tables.

The current entrypoint is a one-shot runtime smoke. It requires separate
`CATALOG_DB_*` and `PUBLICATION_DB_*` settings, connects with TLS and bounded
timeouts, and fails unless PostgreSQL reports a private server address and the
Mart-specific roles have their expected schema grants. It never prints
passwords or performs feature/evidence writes.

`PostgreSQLAnalysisQueue` leases one persisted `analysis` execution with
`FOR UPDATE SKIP LOCKED`. Completion requires the processor to persist a
`gs://` artifact tied to the claimed immutable Core snapshot; claim/enqueue
success alone cannot mark the execution succeeded.

Set `MART_OPERATION=queue`, `MART_BUCKET`, `GCP_PROJECT_ID`, and the bounded
catalog/publication database settings to process one execution. The default
warehouse is `gs://$MART_BUCKET/warehouse`; an override must remain in that
bucket. Full feature, evidence, role, aggregate, and report payloads stay in
Iceberg/GCS. PostgreSQL receives only immutable artifact metadata through
`publication.register_mart_report`, and only complete `publishable`/`published`
rows appear in `publication.publishable_mart_reports`.

Optional public narration is enabled only with `MART_LLM_ENABLED=true` and
`GEMINI_API_KEY`. It uses the repository prompt in `prompts/`, Gemini structured
output, grounded evidence IDs and bounded retry. Paid Gemini remains fail-closed;
LLM output is stored separately and cannot modify deterministic fields.
