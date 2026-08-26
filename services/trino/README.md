# Trino service

Trino 474 is built from the pinned upstream image. The image contains only
non-secret configuration; Cloud Run injects catalog credentials from Secret
Manager and uses the `trino-runtime` service account for GCS ADC.

Required runtime environment:

- `GCP_PROJECT_ID`, `CORE_BUCKET`
- `CATALOG_DB_HOST`, `CATALOG_DB_NAME`, `CATALOG_DB_USER`
- `CATALOG_DB_PASSWORD` (Secret Manager only)

The JDBC catalog tables are created by PostgreSQL migration
`003_iceberg_jdbc_catalog.sql`. Query concurrency is capped at two and spill
data is temporary under `/tmp`; no query state is persisted on the VM.

The Cloud Run definition is in `infra/terraform/trino_service.tf`. It is
private, IAM-invoker-only, Direct VPC egress, 2 vCPU, 4 GiB, and max one
instance. Deployment and smoke tests remain gated by the PostgreSQL/private
connectivity prerequisites in `doc/todo.md`.
