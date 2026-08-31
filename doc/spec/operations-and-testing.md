# Operations and testing

最新驗證日期：2026-08-31

最新完整本機驗證：`python -m pytest -q tests` 為 98 tests passed，Python compileall
passed；同日既有 Vitest 2/2、Playwright Admin interaction 5/5、TypeScript typecheck、
ESLint 與 static Web production build 驗證仍為 passed。Playwright 測試 worker 會自行啟停本地 HTTP
server，5 項測試完成後 clean exit 0。Repository root 的未追蹤 `token-savior/` 是
獨立工具，已排除於本專案 ESLint；pytest 固定以正式 `tests/` 為界。真人 Google
login 未執行。Windows
PowerShell 執行 Node.js 指令須使用 `npm.cmd`／`npx.cmd`，不得為避免 `.ps1`
ExecutionPolicy 阻擋而放寬系統政策。Web runtime 已加入 Google allowlist
session、不可由 request body 偽造的
authenticated audit actor、Web 專用 control/catalog role migration，以及不建立
namespace 的 read-only catalog reader。Dev migration、credential 切換與 Cloud Run
實機 role isolation 已完成；真人 Google 帳號登入及 OAuth Console redirect URI
仍需一次人工確認。

## P0 Iceberg schema evolution tests (2026-08-31)

Core Iceberg regression 驗證 additive nullable 欄位會取得新 field ID，既有 field
IDs 保持穩定；舊 rows 對新增欄位回傳 null，既有 snapshot 保留且仍可讀。
不相容型別變更會在 commit 前被拒絕，不產生新 snapshot 或改寫既有資料；欄位語意
或單位改變仍依契約建立新 table version。Iceberg targeted pytest 5/5、完整
`python -m pytest -q tests` 98/98、適用的 Python compileall 與
`git diff --check` passed；本切片未操作 GCP。

## P0 2330 Source → Stage → Core → Admin integration (2026-08-31)

本機 integration regression 以 injected 2330 TWSE source fixture 建立 persisted
collection execution，驗證 raw／quarantine Stage objects、Core materialization 與
Admin HTTP status query。Admin 結果涵蓋 latest Core date、dataset coverage、row
count、DQ warning count、quarantine count，以及 persisted execution／provenance
關聯；response 不含 raw payload、object URI、secret、完整 upstream error 或
traceback，Admin query 期間 source adapter 呼叫數不增加。

同日 replay 維持單一 Core natural-key row 與相同 content hash，且 incoming null
close 未覆蓋既有有效值。Targeted pytest 11/11、完整 `python -m pytest -q tests`
96/96 與適用的 Python compileall passed；未操作 GCP，既有 dev migration
`009_admin_cursor_indexes` 未重複套用。

## P0 Admin cursor dev migration (2026-08-31)

PostgreSQL migration `009_admin_cursor_indexes` 已套用至既有 dev VM
`janus-postgres-dev`。`control.schema_migrations` 已記錄該 version；
`control.executions_admin_page_idx` 的實際定義為
`CREATE INDEX executions_admin_page_idx ON control.executions USING btree (requested_at DESC, execution_id DESC)`。
PostgreSQL readiness 回報 accepting connections，VM／container 暫存 migration 檔案均已清除。

套用前後的唯讀資源盤點一致：project `gen-lang-client-0593591102` 只有既有
`us-central1-a` `e2-micro` VM 與單一 30 GB `pd-standard` boot disk，VM 只有
private IP `10.42.0.5`、無 external IP；snapshot 與 Cloud Router／NAT 清單為空。
未重建 image、未重啟 PostgreSQL container、未建立額外雲端資源，且未部署
production 或呼叫 Artifact Analysis／Container Scanning／occurrence API。

## P0 Mart runtime connectivity (2026-08-31)

PostgreSQL build `36823a97-1ef1-4046-9700-37223be1bdf0` 產生 immutable digest
`sha256:6fe7049c87c07429ab4eb8563a704ff9d54951dbe28338e1ac657b2ae50ebd51`；
migration `008_mart_runtime_roles.sql` 已建立 non-superuser／non-createdb／
non-createrole／non-replication 的 `janus_mart_catalog` 與
`janus_mart_publication`，HBA 僅允許 `10.42.0.0/24` TLS 連線。

Mart 修正版 build `9a94e089-a89b-4e44-9351-3c9fb166b569` 產生 digest
`sha256:cbd336ace6629c1a78769673ad5415f0d6475a42766510f9b9ef2ea7d24fd007`。
Cloud Run Job `janus-intelligence-mart` 使用專用 service account、Direct VPC
`private-ranges-only`、`janus-intelligence-mart` network tag、固定 Secret version 1、
1 CPU／1 GiB／300 秒 timeout／1 retry。Execution
`janus-intelligence-mart-hd86r` 成功；catalog／publication 皆回報 private address、
bounded privileges `ok`。第一次 execution `janus-intelligence-mart-rpwjj` 只因
PostgreSQL 回傳 CIDR 形式 `172.17.0.2/32` 被驗證器誤判，已以 `ip_interface` 修正並
留下 regression test。臨時 VM Secret IAM 已撤銷，local／VM credential temp files
均已清除。

Cloud Scheduler `janus-ingestion-daily` 目前只呼叫 `janus-ingestion-core:run`；Mart
尚未排程。WBS／todo 已要求 ingestion DQ／Core commit 成功後由
`core.dataset.ready.v1` workflow／event 觸發 Mart，不得以同時獨立排程取代依賴。

Google login handoff 在驗證 ID token 後，以短效簽章 handoff 完成同源 POST；第二段
回應使用 `303 See Other`，在同一 response 設定 HttpOnly session cookie 並導向
`/admin/stocks`。不得使用零秒 meta refresh，以免瀏覽器在 cookie 提交前先載入
Admin、被誤判未登入而退回 `/login`。Auth 專項 7/7 與全套 78/78 tests passed。

## P0 Web runtime deployment (2026-08-30)

PostgreSQL migration `007_web_runtime_roles.sql` 已套用至 dev，Web control role
對明確列出的 control tables 使用一致的 SELECT／INSERT／UPDATE／DELETE 權限；
catalog role 對 catalog metadata 為 SELECT-only，且
`default_transaction_read_only=on`。實機權限查詢結果為
`catalog_write_tables=0`、`control_dml_missing=0`。兩個 role 均不是 superuser、
createdb、createrole 或 replication role。

PostgreSQL build `da62fdb1-f3f5-4436-bc28-0a18edd4e9ac` 的 immutable image digest
為 `sha256:f81ef216a81b003edd6b319cb2ab04f65b453c34c1fae09d8cf7f44e9de993b7`。
Web build `5d919396-ad8a-490e-a07c-30c33c3060bb` 的 immutable image digest 為
`sha256:1be0cb5e7cb5056fc2805de3eb9f44214cb969d13e991186872ad39cb32e8123`；
Cloud Run revision `janus-web-00023-ccj` ready 且承接全部 dev traffic。

Cloud Run 保持 `allUsers` invoker，由 application middleware 執行 allowlist session
驗證。未登入 smoke：`/health` 與 `/login` 回 200、`/admin/stocks` 轉址至
`/login`、Core API 回 401；短效合成簽章 session smoke 對 Admin 與
`/api/v1/core/2330/summary` 均回 200。revision ERROR log 查詢無結果，證明 Web
runtime 已透過 Direct VPC private path 使用專用 control/catalog credential。

Web catalog Secret 目前只保留 version 3 enabled，先前版本已 disabled；Web session
Secret 只保留 raw-byte 驗證為 48-byte ASCII、無 BOM 的 version 4 enabled，versions
1–3 均 disabled。Secret 值沒有寫入 repository 或正式驗證輸出；後續輪替必須依
`doc/runbook-dev-deploy.md` 的 raw-byte、runtime、disable-old-version 順序執行。

## Dev delivery automation and artifact retention (2026-08-28)

Terraform is no longer a repository or deployment dependency. Dev bootstrap is
performed by the explicitly authorized, idempotent
`scripts/gcp/provision-dev.sh`; it verifies the fixed PostgreSQL Free Tier shape
and does not create a missing PostgreSQL VM automatically.

Automatic runtime deployment is owned by three regional GCP Cloud Build
Developer Connect triggers, all restricted to branch `^main$` and component
paths:

- `janus-ingestion-core` (`5e201f5a-c206-4006-92b9-40a53c4155ed`):
  `jobs/ingestion-core/**`, contracts, observability, and `cloudbuild.yaml`.
- `janus-intelligence-mart` (`b8215cb9-1823-401d-b293-65fbdf73ce30`):
  `jobs/intelligence-mart/**`, contracts, observability, and `cloudbuild.yaml`.
- `janus-web` (`c08067dd-5c44-414f-9e8d-9d94e89b4089`): `apps/web/**` and
  `cloudbuild.yaml`.

Documentation-only and `scripts/gcp/**` changes do not trigger runtime builds.
The former two triggers were deleted before these three current triggers were
created. `.github/workflows/deploy-dev.yml` is manual-only (`workflow_dispatch`)
and restricted to `main`; its repository variables are
`GCP_WIF_PROVIDER` and `GCP_CI_SERVICE_ACCOUNT`. No long-lived service-account
JSON key is used. A path-matching push has not yet been used as end-to-end
evidence for the new trigger set; automatic trigger acceptance remains pending.

The last directly verified runtime deployments remain Cloud Build
`baf5b915-ee80-477b-8ec8-dc1e981fc23a` for ingestion-core at
`sha256:16248df5e95afea4cc099016c4c6e1722eade307b53d2065514f7d517f596e8e`
and `e021a691-2a0e-42eb-bffd-b25c2ee2ead2` for web at
`sha256:6746d5985e60781bda04b1965d980e0651c82dd30e7026344e1b30908221cd74`.
The `janus-intelligence-mart` trigger and Cloud Run Job now exist. Manual build,
immutable deployment, Direct VPC, Secret Manager, and database smoke acceptance
passed; a path-matching automatic trigger run remains pending.

Artifact Registry repositories `janusai-poc` and `janus-postgres` use the same
active cleanup policy with dry-run disabled: each image package keeps only its
most recent version, while older tagged and untagged versions are eligible for
deletion after one second. The old untagged PostgreSQL digest
`sha256:8dfe6976ca822f87a6ba42743bb0f841d4bee3352a66816d663f2bc0961f7c4e`
was permanently deleted; `postgres:16.15` remains at
`sha256:6fe7049c87c07429ab4eb8563a704ff9d54951dbe28338e1ac657b2ae50ebd51`.
Artifact Analysis and Container Scanning remain disabled and were not called.

## P0 Admin follow-up (2026-08-28)

Admin now has persisted settings and immutable audit metadata in SQLite and
PostgreSQL migration `006_admin_settings_audit.sql`, with optimistic version
checks. The source catalog API/UI exposes cadence, coverage tier, retention,
authorization status, and max-symbol quota; candidate/blocked enabled configs
are rejected. Stock status details expose the aggregate Core summary,
including latest date, row count, DQ warnings, and quarantine count when the
read-only Core runtime is connected. The existing Direct VPC Web Cloud Run
service has access to the control/catalog Secret Manager containers; no secret
values are committed or invented.

Frontend Vitest and Playwright configurations/tests were added. Dependencies
were not installed in this restricted environment because the npm registry
request stalled; browser discovery returned no available in-app browser.
Local HTTP smoke returned 200 for `/health`, `/admin/stocks`, and the Admin JS
asset. Python discovery ran 63 tests successfully; Python compileall,
JavaScript syntax, and git diff checks passed. Terraform is no longer part of
the repository or validation path.

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
- gcloud bootstrap guard：PostgreSQL `e2-micro`、30 GB、固定 zone 驗證通過。
- GCP Developer Connect triggers：三個 component trigger 已建立；新的 path-matching push acceptance 尚待驗證。
- Artifact Registry：兩個 repositories 均啟用 keep-latest-1 cleanup policy，dry-run disabled。
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
已完成。

## 2026-08-31 — P0 schedule／backfill／retention dev 驗收

GCP Cloud Build 驗證通過：Python 101 tests；Web Vitest 2、Playwright 5、typecheck、
ESLint 與 production build；PostgreSQL transaction／migration targeted build
`af628b6f-354d-4d68-93df-8c616976f11a`。全程未啟動 WSL。

dev migration `010_execution_runtime_options`、`011_control_settings_ownership` 與
`012_first_batch_source_ids` 已套用。`janus_control` 擁有 `admin_settings`、
`admin_audit` 與其 identity sequence，仍為 bounded non-superuser role；
`first-batch.source_ids` 使用 canonical provenance IDs。

scheduled execution `janus-ingestion-core-jmh8d` 成功，control execution
`dd8ad090-1daf-4522-94a9-6fc5bb8c9862` 為 `succeeded`，正式來源 items 保存
`Core committed`。指定 `2026-08-28`、`2330`、`twse` 的 queue backfill execution
`7362712f-5acf-4c5e-afd8-45fa33268c9e` 經 `janus-ingestion-core-kt9mq` 完成；
valuation 1 row、institutional 3 rows、market-activity 3 rows 已 commit，events 為
合法 empty。ingestion image digest 為
`sha256:ad00a77389beb4a636088e0b6ec9e0ba4fc2b371216d547865b97a599fd9342a`。

實機 smoke 同時發現並修正 PostgreSQL read transaction 在 upstream I/O 期間觸發
10 秒 idle-in-transaction timeout 的問題；repository 現以 autocommit 處理 reads，
write paths 仍使用 explicit transaction。Web dev `/admin/stocks` 未登入回 303 並導向
`/login`。Cloud Scheduler 維持 `30 7 * * *`、`Asia/Taipei`、enabled；Admin 變更
排程時間的自動 Scheduler reconciliation 仍列為後續工作。
