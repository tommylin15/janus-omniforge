# PostgreSQL Free Tier bootstrap

The VM uses a pinned Google COS image, private IP only, and no Cloud NAT. A
pinned PostgreSQL 16 image must first be published to an approved Google-hosted
registry without Artifact Analysis or Container Scanning. The bootstrap
operator then connects through IAP/OS Login, supplies the bootstrap, control,
catalog, publication, audit, Web control, and Web catalog Secret Manager values to
`psql` variables, and applies migrations in numeric order. Values must never be
written to this repository, Terraform, VM metadata, startup scripts, shell
history, or logs.

The server baseline is sized for 1 GiB RAM and 30 connections. Migrations are a
separate operator action and are never coupled to a web deployment. The
readiness query verifies the database and four workload schemas without
exposing credentials.

Free Tier mode intentionally has no external IP, NAT, snapshot schedule,
automated backup, HA, or replica. PostgreSQL metadata can be lost with the VM;
GCS remains the durable store for raw/cache payloads and lake data.

Incremental Web role rollout uses `scripts/gcp/apply-web-postgres-migration.sh`.
It accepts only an immutable PostgreSQL digest, reads the two Web passwords from
stdin, replaces the running container while preserving the data volume, applies
migration `007`, and restores the previous image automatically if the rollout
fails.

Deployed dev baseline (2026-08-26): PostgreSQL 16.15 at immutable image digest
`sha256:e81c2f294e85fbb0c1ff2d19263a169d987a881c54e21ca8339df4501a7fa636`
on private endpoint `10.42.0.5`. Artifact Registry vulnerability scanning is
disabled because the Container Scanning API remains disabled.
