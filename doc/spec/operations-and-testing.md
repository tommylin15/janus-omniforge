# Operations and testing

最新驗證日期：2026-08-28

## P0 Admin follow-up (2026-08-28)

Admin now has persisted settings and immutable audit metadata in SQLite and
PostgreSQL migration `006_admin_settings_audit.sql`, with optimistic version
checks. The source catalog API/UI exposes cadence, coverage tier, retention,
authorization status, and max-symbol quota; candidate/blocked enabled configs
are rejected. Stock status details expose the aggregate Core summary,
including latest date, row count, DQ warnings, and quarantine count when the
read-only Core runtime is connected. Terraform now includes a Direct VPC Web
Cloud Run service definition and Web access to the existing control/catalog
Secret Manager containers; no secret values are committed or invented.

Frontend Vitest and Playwright configurations/tests were added. Dependencies
were not installed in this restricted environment because the npm registry
request stalled; browser discovery returned no available in-app browser.
Local HTTP smoke returned 200 for `/health`, `/admin/stocks`, and the Admin JS
asset. Python discovery ran 63 tests successfully; Python compileall,
JavaScript syntax, and git diff checks passed. Terraform CLI validation could
not be rerun because the installed Windows launcher is not executable.

## P0 Query／Admin application layer (2026-08-28)

`packages.web_api.CoreQueryService` is the read-only Core application boundary.
Dataset identifiers are allowlisted, symbol/date values are parameterized, and
pagination is bounded. It exposes row count, latest date, null profile, and
quality flags without returning Stage payloads. `apps.web.server` provides a
Cloud Run-compatible WSGI boundary with safe 4xx/5xx responses and a health
endpoint; runtime database wiring remains an explicit deployment configuration.

`packages.admin_api.AdminService` provides bounded stock search, enabled/delete
operations, queued collection/analysis triggers, recent execution/detail views,
and effective-time membership views. It delegates FK/reference protection,
candidate/blocked source rejection, and core-50 limits to the control plane;
collection work is never executed in the request path.

`/admin/stocks` now provides the first responsive Admin Data Operations UI:
10-row stock pages, cross-page selection, separate collection/analysis enqueue,
the latest 50 persisted executions with on-demand safe details, persisted source
health, and effective-time core membership editing. Runtime PostgreSQL wiring,
typed schedule/source authorization editing, audit/optimistic concurrency, and
browser interaction coverage remain open acceptance conditions.

UI acceptance may run against a local browser/Playwright environment or against
the existing GCP dev Cloud Run service when a real runtime is required. After
the manual billing gate has been satisfied, the existing dev service may be
started on demand without separate per-run approval. The cloud path must verify
the actual dev URL, responsive and interaction behavior, Admin API/runtime
connectivity, and safe output; evidence records the Cloud Run revision,
immutable image digest, test URL/time, and scale-to-zero state. This authorization
does not cover production deployment, higher resource limits, or new paid GCP
resources.

Source health summaries are now available from both SQLite reference and
PostgreSQL control adapters. Migration `005_source_health_telemetry.sql` adds
bounded aggregate coverage, cache, fallback, schema-drift, and tier fields;
raw upstream payloads remain excluded.

Validation for this change: 10 focused Admin/API tests passed; JavaScript syntax,
Python compileall, and diff checks passed. Full discovery ran 58 tests: 56 passed
and only the two existing PyIceberg tests failed to import because `pyiceberg` is
not installed. Browser discovery returned no available local browser; visual
interaction remains pending and may be completed through the authorized GCP dev
Cloud Run acceptance path above. No cloud deployment or paid resource was
created.

## PostgreSQL dev/MVP topology

Development PostgreSQL is a self-managed Compute Engine `e2-micro`
VM in `us-central1`, with private networking, no external IP, at most 30 GB
Standard Persistent Disk, and IAP／OS Login. The dev VM is provisioned at private
IP `10.42.0.5`. Free Tier mode does not create scheduled snapshots, backups, HA,
or replicas and is not a production HA decision. Cloud SQL is not part of the
selected dev topology.

The Free Tier target also limits outbound data to 1 GB/month. Eligibility is
evaluated by billing account and region; the resource limits do not guarantee a
zero bill.

## PostgreSQL control integration

`PostgreSQLControlPlane` is the production repository for control metadata. It
uses injected bounded connections, transaction-scoped writes, server-side
statement/idle timeouts, transition checks, and `FOR UPDATE SKIP LOCKED` queue
leases. Response cache payloads remain in GCS; PostgreSQL stores only URI,
hash, TTL, observed time, and state. The migration is idempotent and includes
expiry/health indexes and pruning support. Ingestion private-IP authentication
and control-symbol reads are validated; Web and Mart paths remain pending. The
Trino replacement is complete in the development runtime. No production
deployment was performed.

Provisioning gate: PostgreSQL VM, PostgreSQL repository/migration, private
connectivity, control/catalog schema bootstrap, and PostgreSQL readiness must
pass before a Cloud Run DuckDB runtime deployment is attempted.

DuckDB runs embedded in the Cloud Run ingestion Job and reads/writes Iceberg
data and metadata in GCS. PostgreSQL remains the control DB and SQL catalog
metadata store; it does not store Iceberg data files. The VM has only 1 GiB RAM
and is reserved for PostgreSQL control/catalog metadata.

The source control contract separates `market_wide`, `core_focus`, and
`market_macro` coverage. Collection configs persist cadence, scope,
authorization status, retention class, PII, republishing permission, and a
maximum symbol count. Historical coverage membership is append-only with
effective timestamps; `core_focus` is capped at 50 symbols. Candidate or blocked
sources are rejected before queueing, while source IDs remain available in the
contract for later approval review.

Artifact Registry cost guard: image push/pull, immutable digest, metadata and
cleanup only. Artifact Analysis API, Container Scanning API, vulnerability
scanning and occurrence APIs are prohibited; no scanning API was called during
this change.

## P0 資料控制面與 Ingestion Framework

- Python unit/contract tests：42 targeted tests passed；`compileall` passed；`git diff --check` passed。Full discovery remains blocked only by the local environment missing `pyiceberg` for two existing DuckDB/Iceberg tests。
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

- Python unit/contract tests：39 passed（含 Stage/Core、DuckDB/Iceberg、framework/control、contract、DB session timeout 與 sparse-empty semantics）。
- Python compileall：passed。
- Terraform validate：既有 baseline 曾通過；本次 Windows 環境 Terraform launcher 無法執行，未宣稱本次 IaC 變更已重新 validate。
- Terraform apply：4 bucket IAM bindings added，0 changed，0 destroyed。
- Post-apply Terraform plan：No changes。
- Cloud Build images：`d6f62619-eba6-47b2-b238-c1057774a611` 與
  `fcbae728-f254-458e-8475-0c69b3e5a34f` 均成功。

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

排程 Stage lifecycle 已加入 execution-scoped 模式：payload、sidecar 與 manifest
置於 `executions/{execution_id}/stage/`；Core 成功後以 immutable
`executions/{execution_id}/core-commit.json` 作為清理 fence。清理只接受已有
commit marker 的指定 execution，未 commit 的失敗／重試資料不會被刪除。Cloud
entrypoint 預設啟用此模式，並可用 `PREVIOUS_STAGE_EXECUTION_ID` 指定要清理的前次
成功 execution；Scheduler runtime 與雲端清理 smoke 已完成，詳如下方驗收紀錄。

2026-08-26 runtime smoke 已完成：Cloud Run executions
`janus-ingestion-core-6w8v9` 與 `janus-ingestion-core-vxtcp` 成功；前者輸出
8/8 sources、0 failure、Core reused 79,262，後者以前者的 commit fence 完成
Stage cleanup，前次 `core-commit.json` 保留。Cloud Scheduler
`janus-ingestion-daily` 現為 `ENABLED`，`30 7 * * *`、`Asia/Taipei`。Admin UI／
control DB settings 維護介面仍待後續；完整 incremental merge 已由 DuckDB
runtime 驗收。

DB-backed 五檔 runtime smoke `janus-ingestion-core-nbql7` 成功：從 control DB
讀取 `1102`、`2327`、`2330`、`2381`、`4958`，8 個來源產生 10 個 Stage
objects，`failed=0`、`core_created=0`、`core_reused=419`。FinMind 的 `2381`
與 TWSE events 在該窗口無資料，明確保存為 2 個合法 `empty`，不掩蓋 HTTP／
解析等真正失敗。Direct VPC ingress firewall 使用 private subnet
`10.42.0.0/24` 作 source range，只開放 target tag `janus-postgres-db` 的 5432；
Scheduler 驗收後恢復為 `ENABLED`。

2026-08-28 Trino → DuckDB cutover completed in development. Clean-image
canary `janus-ingestion-core-lngkm` completed in 4m38s with `failed=0`,
`core_created=0`, `core_reused=420`, and `core_updated=0`; the preceding
functional canary `janus-ingestion-core-89q6z` completed with `failed=0` and
`core_created=420`. Both runs read the five configured symbols
(`1102`, `2327`, `2330`, `2381`, `4958`) from the control DB and used the GCS
Iceberg warehouse `gs://gen-lang-client-0593591102-dev-core/warehouse/`.
The final image is
`ingestion-core@sha256:2e72c2a4e39188577e505a215557ebba797e8c5a08d3832243637be8b4fe64af`.
The SQL catalog migration creates the `janus_control.catalog` tables and
PyIceberg-compatible public updatable views; catalog Secret version 3 was
byte-verified against the private `janus_catalog` connection. Trino service,
build trigger, image, rollback tag, and old ingestion digest were removed;
Artifact Registry cleanup is active with dry-run disabled.

Job 亦支援 `INGESTION_DATE` 單日 replay，或以
`BACKFILL_START_DATE`／`BACKFILL_END_DATE` 執行最多 367 個日曆日的 bounded
range replay；`INGESTION_DATASETS` 可限制資料源。每次 replay 都使用新的 execution
ID，並沿用相同 Stage → Core commit fence。

2026-08-28 Web dev deployment：Cloud Build
`fd229529-e8c0-44c4-b0c3-2ef03c1aa691` 使用最小 build context 成功建立並 push
Web image，digest 為
`sha256:a42178256596da6bc0403f9f1bda45bac486da1788c3339ed78a98c2a085be40`。
Cloud Run revision `janus-web-00001-dvz` 已在 `us-central1` ready，使用
`web-runtime`、Direct VPC `private-ranges-only`、`janus-web` network tag，且未
開放匿名存取。Web runtime 已具備可選 PostgreSQL／Iceberg wiring；因尚未配置
Web 專用 control/catalog credential，該 revision 目前使用 safe fallback，DB
connected Web/Admin smoke、Mart Job runtime 與 authenticated HTTP 驗收未宣稱完成。

本機 Python 3.12 已安裝 `duckdb==1.5.5`；`python -m unittest discover -s tests`
結果為 59 tests passed，`compileall` 與 `git diff --check` 通過。

同日 authenticated HTTP smoke 已完成：Cloud SDK `cloud-run-proxy` 已安裝，
`janus-web-00002-472` custom audience 更新後，direct URL 與 localhost proxy
對 `/health`、`/admin/stocks`、`/assets/admin.css` 均回 HTTP 200。Cloud Run
仍為 user Invoker-only，未開放匿名；Token Creator 暫時 binding 已撤銷。

## P0 Core 第一批資料源

`ingestion_core.first_batch` 提供可重播的 credential-free JSON adapter，涵蓋
TAIEX／TPEx benchmark、PE／PB、法人、MOPS／FinMind financials、公司事件與
market activity（融資融券、借券、當沖、注意／處置、issued shares、turnover
等以 metric／unit 表示）。Normalizer 會保留 null 與原始單位，不對缺資料推算；
benchmark collection 與個股行情 collection 分離。`effective_trading_day` 對週末、
休市日與盤前執行回看最近有效交易日。所有 adapter transport 可注入 fixture，
raw payload 仍由 Stage/GCS 層保存，control database 僅保存 cache metadata；SQLite
reference 與 PostgreSQL adapter 均提供 bounded prune。第一批資料源的線上 upstream
API smoke 與實機 workload connectivity 仍需部署後執行。

Cloud Run ingestion Job 已以官方 TWSE／TPEx／MOPS OpenAPI 與 FinMind request
完成第一批 8 個來源的 Stage → Core 雲端 smoke；目前由 embedded DuckDB
寫入 GCS Iceberg。Execution
`janus-ingestion-core-n88jc` 為 8／8 Stage、0 failure，建立／重用合計 79,262
個 natural-key rows，並以來源／觀測日聚合成 8 個 Core partition objects（27.38
MiB）。同日 replay `janus-ingestion-core-nxmwc` 為 `core_created=0`、
`core_reused=79,262`，object count 維持 8，證明 create-if-absent partition commit
不產生重複資料。07:30 `Asia/Taipei` Scheduler 已 ENABLED；前次 Stage cleanup smoke
已完成，日期區間 backfill 與 Admin control 仍待後續驗收。
