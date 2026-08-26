# Operations and testing

最新驗證日期：2026-08-26

## PostgreSQL dev/MVP topology

Development PostgreSQL is planned as a self-managed Compute Engine `e2-micro`
VM in `us-central1`, with private networking, no external IP, at most 30 GB
Standard Persistent Disk, and IAP／OS Login. Free Tier mode does not create
scheduled snapshots, backups, HA, or replicas. It is not provisioned yet and is
not a production HA decision. Cloud SQL is not part of the selected dev topology.

The Free Tier target also limits outbound data to 1 GB/month. Eligibility is
evaluated by billing account and region; the resource limits do not guarantee a
zero bill.

## PostgreSQL control integration

`PostgreSQLControlPlane` is the production repository for control metadata. It
uses injected bounded connections, transaction-scoped writes, server-side
statement/idle timeouts, transition checks, and `FOR UPDATE SKIP LOCKED` queue
leases. Response cache payloads remain in GCS; PostgreSQL stores only URI,
hash, TTL, observed time, and state. The migration is idempotent and includes
expiry/health indexes and pruning support. Runtime private-IP smoke tests for
ingestion, Web, Mart, and Trino remain pending until those workloads are
deployed; no production deployment was performed.

Provisioning gate: PostgreSQL VM, PostgreSQL repository/migration, private
connectivity, control/catalog schema bootstrap, and PostgreSQL readiness must
pass before Trino JDBC catalog or Trino Cloud Run deployment is attempted.

Trino is planned separately on Cloud Run (2 vCPU, 4–8 GiB, min 0, max 1); it
does not run on the PostgreSQL `e2-micro` VM. The VM has only 1 GiB RAM and is
reserved for PostgreSQL control/catalog metadata.

Artifact Registry cost guard: image push/pull, immutable digest, metadata and
cleanup only. Artifact Analysis API, Container Scanning API, vulnerability
scanning and occurrence APIs are prohibited; no scanning API was called during
this change.

## P0 資料控制面與 Ingestion Framework

- Python unit/contract tests：23 passed；`compileall` passed；`git diff --check` passed。
- Python compileall：passed。
- Control schema：SQLite reference implementation covers stock master with
  collection-reference protection, dataset collection config, separate
  collection/analysis queue commands, persisted execution/items, response
  cache, incremental cursors, and source-health telemetry.
- Execution statuses：queued、running、retrying、succeeded、partial、failed。
- Item availability：success、empty、partial、fallback、stale、unavailable、
  schema_drift、failed。
- Adapter framework：sync/async `SourceAdapter`, bounded timeout, exponential
  backoff, retry-after support, per-source rate limiting, exact schema-drift
  detection, safe error taxonomy, and no raw upstream error persistence.
- Cache/incremental：market-scope responses share one market/day batch key;
  symbol-scope responses retain the exact start boundary; successful primary
  observations advance a cursor with configured overlap. Partial/fallback/stale
  responses are not promoted to successful cache entries.

## P0 Stage／Core

- Python unit/contract tests：12 Stage/Core tests passed（含 2330 closed-loop integration）；framework/control/contract tests 12 passed。
- Python compileall：passed。
- Terraform validate：passed（Google provider 7.45.0）。
- Terraform apply：4 bucket IAM bindings added，0 changed，0 destroyed。
- Post-apply Terraform plan：No changes。
- Docker image build：未執行；目前工作環境沒有 Docker CLI。

Stage writer 使用 immutable create-if-absent、SHA-256 content hash、受控 ID、
去敏 source URL、execution manifest 與 quarantine sidecar。Core DQ 覆蓋
required key、type、date、duplicate、unit、range、schema drift、null-preserving
merge、欄位語意 zero 與極端漲跌保留警示。

2330 Stage → Core closed loop：`ingestion_core.sources` 提供 TWSE／TPEx OHLCV
normalisation；`pipeline.run_2330` 建立 persisted collection execution，將 raw
payload／sidecar／quarantine 寫入 Stage，使用 Core DQ materialise deterministic
OHLCV rows，並透過 event sink 發出 `core.dataset.ready.v1`。Core summary 保存
row count、content hash、date coverage、null profile、warning/quarantine count
與 provenance ID。重跑使用 Stage create-if-absent 與 null-preserving merge；真實
Cloud Run／VM restart smoke、GCS production object 與 PostgreSQL workload connectivity
仍待 runtime deployment 後驗證，未在本次變更中宣稱完成。
