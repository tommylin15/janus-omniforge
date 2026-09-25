# Ingestion Core job

Implemented foundations:

- immutable JSON/CSV Stage payloads with provenance sidecars;
- deterministic content hashes and idempotent create-if-absent writes;
- execution manifests and quarantine payloads;
- Cloud Run GCS writes using metadata-server short-lived credentials;
- deterministic OHLCV Core DQ and null-preserving incremental merge;
- Iceberg v2 schema and bounded month/symbol-bucket partitioning.

The Stage writer accepts only controlled source/dataset identifiers and safe
path segments. Extreme moves over 11% are retained with a review warning; they
are not silently deleted. Zero handling is field-semantic rather than global.

First-batch normalisation also preserves dataset semantics instead of forcing a
single unit or investor definition. TWSE dealer flows are aggregated from
self-trading and hedging buy/sell columns and checked against the official total
net field by regression tests. Financial statement units preserve explicit
upstream units; per-share metrics such as EPS use `TWD_per_share` rather than a
statement-wide `TWD_thousands` default. Historical rows written before a
normalisation correction require an explicit bounded backfill; deploying new
code alone does not rewrite old Core snapshots.

The ingestion control plane is implemented by `ingestion_core.control` and the
runtime by `ingestion_core.framework`. `SQLiteControlPlane` is the reference
repository for the PostgreSQL control schema: it persists stock master,
collection config, queued executions, item-level availability states, response
cache, incremental cursors, and source-health telemetry. Collection and
analysis are separate queue commands. Adapters implement the common
`SourceAdapter` contract and return `SourceResponse`; timeout, retry, rate
limit, schema drift, fallback, and safe error classification are enforced by
the framework.

`PostgreSQLControlPlane` is the production repository. It uses transaction
scopes, `FOR UPDATE SKIP LOCKED` leases for queue claims, server-side
statement/idle timeouts, and the same transition invariants as the SQLite
reference. `CacheMetadata` stores only a `gs://` payload URI, hash, TTL,
observed time, and state; raw responses never enter PostgreSQL. Use a bounded
connection factory (the VM baseline is 30 server connections); do not create a
connection per request. The migration is an explicit operator action and is
idempotent.
