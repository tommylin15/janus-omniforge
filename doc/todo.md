# Janus × OmniForge — TODO

版本：1.1
用途：由 AI／開發者依順序執行；完成時勾選並附 PR、Cloud Build、execution 或測試證據。

## P0 — 開工前阻擋項目

- [x] 取得 GitHub repo 或建立 `janus-omniforge` monorepo。
- [x] 確認 GCP Project ID、Billing account、region=`us-central1`。
- [x] 確認 PostgreSQL：GCE Compute Engine `e2-micro` Free Tier 模式（dev／MVP，`us-central1`、≤30 GB Standard Persistent Disk、無 external IP、outbound ≤1 GB/月；production HA 另行評估）。
- [ ] 部署前人工確認 billing account 尚有 eligible `e2-micro` 時數、30 GB-month Standard Persistent Disk 與 1 GB outbound Free Tier 額度；未確認前只允許 plan，不得 apply。
- [x] 確認 AI 可建立 PR，但 production deploy 需人工批准。
- [x] 確認第一批股票：至少 `2330`。（人工確認）
- [x] 確認第一版 LLM provider 順序：Gemini → OpenRouter → GroqCloud；取消 Vertex AI。
- [x] 確認 dev bucket／resource 命名。
- [x] 建立 US$1／US$5／US$10 billing alerts。（人工處理）

## P0 — Repository 與雲端開發

- [x] 建立 `apps/web`。
- [x] 建立 `jobs/ingestion-core`。
- [x] 建立 `jobs/intelligence-mart`。
- [x] 建立 `services/trino` baseline；完成 DuckDB cutover 後已退役。
- [x] 建立 `packages/contracts`、`governance`、`provenance`、`observability`。
- [x] 建立 `infra`、`tests/contract`、`tests/e2e`。
- [x] 建立 Cloud Workstations／Cloud Shell Editor 開發設定。（`.devcontainer/devcontainer.json`）
- [x] 固定 Python、Node、Java／Trino 版本與 lockfiles。（`.tool-versions`、版本檔與根目錄 lockfile 基線）
- [x] 加入 CODEOWNERS、PR template；branch protection 由人工處理。（GitHub private repository plan 限制）

## P0 — IAM、CI/CD 與 Secret

- [x] 建立 GitHub → GCP Workload Identity Federation。（pool `github-actions`、provider `github`；限定 `tommylin15/janus-omniforge` 的 `main`，只供手動 GitHub Actions fallback）
- [x] 建立 Cloud Build service account。（`janus-ci@gen-lang-client-0593591102.iam.gserviceaccount.com`）
- [x] 建立四個 runtime service accounts。（`ingestion-core`、`intelligence-mart`、`trino-runtime`、`web-runtime`；`trino-runtime` 已隨 cutover 退役，不再授予新 runtime 權限）
- [x] 套用最小 IAM，不建立長效 JSON key。（四個 runtime SA 已授予 Log Writer／Metric Writer；資源級權限待 bucket／Pub/Sub／Secret 建立後補上）
- [x] 啟用必要 GCP APIs。（已啟用於 `gen-lang-client-0593591102`）
- [x] 新增第五個最小權限 VM identity：`postgres-vm`；不得使用 default Compute Engine service account 或 broad cloud-platform scope。（GCP 實際 SA 與 `scripts/gcp/provision-dev.sh` guard；獨立 SA、零 project-level role、明確 logging／monitoring scope allowlist）
- [x] 盤點 Compute Engine、IAP、OS Login 與 Direct VPC egress 所需 API／IAM；只啟用必要 API，禁止 Artifact Analysis／Container Scanning API。（GCP 實際狀態與 `scripts/gcp/provision-dev.sh` allowlist；2026-08-28 再驗證 scanning disabled）
- [x] 將 Direct VPC egress 所需 Cloud Run service agent／deployer `roles/compute.networkUser` 與 workload network tags 納入最小 IAM；不得建立有固定 VM 費的 Serverless VPC Access connector。（GCP subnet-scoped IAM 實際設定）
- [x] 建立 path-based GCP Cloud Build Developer Connect triggers。（`janus-ingestion-core`=`5e201f5a-c206-4006-92b9-40a53c4155ed`、`janus-intelligence-mart`=`b8215cb9-1823-401d-b293-65fbdf73ce30`、`janus-web`=`c08067dd-5c44-414f-9e8d-9d94e89b4089`；僅 `main` 且符合各自 included files 時觸發；GitHub Actions 為 manual-only fallback）
- [x] 建立 Artifact Registry cleanup policy。（`janusai-poc`、`janus-postgres`：每個 image package 僅保留最新 version，舊 tagged／untagged 版本約 1 秒後清理，dry-run disabled；舊 PostgreSQL digest `sha256:8dfe6976...` 已刪除；Artifact scanning APIs 未啟用）
- [x] 建立 Secret Manager secrets（只放名稱，不把值寫入 repo）。（12 個名稱已建立或已存在；第 4 項前導 `.` 已正規化為 `janus-fugle-api-key`）
- [x] 建立 PostgreSQL bootstrap、control、catalog、publication、audit role 的 Secret 名稱與單項 IAM；不得共用 superuser credential 或寫入 deployment metadata／startup script。（GCP 五個 Secret containers、五組單一 secret-level accessor；值由 out-of-band version 管理）
- [x] 確認 build 產出 immutable digest 與 SBOM。（歷史 Build `dc17987c-dbb9-474c-ac3b-9791c6916ef7`；Trino digest `sha256:e6376bfd8b4315fe70ebdba0d2d683881ac80e112099cbc09528388c6af10a61`；既有 SBOM occurrence `74ab98fa-5e52-4c62-a431-846620aea1ad`，不得重複執行 occurrence API）
- [x] 設定 Artifact Registry 成本限制：禁止 Artifact Analysis API、Container Scanning API、vulnerability scanning 與 occurrence API；SBOM 不作掃描結果依賴。（repository policy；未執行雲端變更）

## P0 — Contracts 與治理

- [x] 定義 source IDs、dataset IDs。（`packages/contracts/registry.json`）
- [x] 定義 `DataProvenanceV1`。（`packages/contracts/registry.json`）
- [x] 定義 `ExecutionStatusV1`。（`packages/contracts/registry.json`）
- [x] 定義 `QualityFlagV1`。（`packages/contracts/registry.json`）
- [x] 定義 `PublicationStatusV1`。（`packages/contracts/registry.json`）
- [x] 定義 `CoreDatasetReadyV1` 與 `MartReportReadyV1`。（`packages/contracts/registry.json`）
- [x] 固定 development completeness gate=30%。（`packages/governance/policy.json`）
- [x] 將 manual review、critical、high≥75 blocking 寫入測試。（`tests/contract/test_contract_registry.py`）
- [x] 盤點所有 deterministic constants 與核准狀態。（`packages/governance/policy.json`）

## P0 — Stage／Core

- [x] 建立 dev Stage／Core／Mart buckets 或隔離 prefixes。（GCP 實際 buckets；`scripts/gcp/provision-dev.sh` 可重複檢查／建立）
- [x] 設 uniform bucket-level access、public access prevention、versioning 與 lifecycle。（GCP 實際設定；bootstrap 維持 access prevention 與 versioning）
- [x] 實作原始物件 + sidecar metadata 寫入。（`jobs/ingestion-core/ingestion_core/stage.py`）
- [x] 實作 content hash 與 idempotency key。（`packages/provenance/model.py`）
- [x] 實作 quarantine 路徑。（`jobs/ingestion-core/ingestion_core/stage.py`）
- [x] 建立 Iceberg Core schemas 與 partition strategy。（`jobs/ingestion-core/schemas/core/`）
- [x] 實作 null、duplicate、date、unit、schema drift DQ。（`jobs/ingestion-core/ingestion_core/dq.py`）
- [x] 禁止 0 一律轉 null。（欄位語意規則與測試）
- [x] 禁止 >11% 漲跌一律刪除。（保留資料並產生 `EXTREME_MOVE_REVIEW`）

## P0 — 資料控制面與 Ingestion Framework

- [x] 建立股票 master／control schema：symbol、name、market、enabled、關聯保護。（`SQLiteControlPlane`、FK RESTRICT、`StockMasterV1`）
- [x] 建立 dataset collection config，分離 collection 與 analysis 觸發。（`CollectionConfig`、獨立 queue enqueue）
- [x] 建立 persisted execution model：queued／running／succeeded／partial／failed／retrying。（SQLite `executions`／`execution_items`）
- [x] 建立統一 source adapter 介面與安全錯誤分類。（`SourceAdapter`、`ErrorCode`、safe message）
- [x] 實作 bounded timeout、retry、rate-limit 與 schema drift 處理。（`IngestionFramework`）
- [x] 保存 empty、partial、fallback、stale、unavailable 狀態與 execution／trace ID。（item state + execution correlation）
- [x] 建立全市場回應同批快取與增量抓取規則。（market batch cache、overlap cursor、full refresh window）
- [x] 完成 timeout、retry、rate-limit、empty／partial 測試。（`tests/ingestion/`；23 tests passed）

本段的 `SQLiteControlPlane` 是 schema／transition 的測試 reference；接上
Compute Engine PostgreSQL VM 後，仍需完成下列 production persistence integration。

## P0 — PostgreSQL Free Tier VM 與 Control DB 基礎

- [x] 建立 Compute Engine `e2-micro` VM：固定 eligible `us-central1` zone、無 external IP、private IP；gcloud bootstrap guard 對 machine type／disk／zone fail closed。（`janus-postgres-dev`，`us-central1-a`，private `10.42.0.5`）
- [x] VM 全部 boot／data Standard Persistent Disk 配置量合計 ≤30 GB；禁止 snapshot／backup／replica／HA 預設資源。（單一 30 GB `pd-standard` boot disk，無其他 disk／snapshot／backup／replica／HA）
- [x] 設定專用 subnet、Private Google Access、IAP／OS Login、`postgres-vm` identity 與 network tags；IAP SSH 僅允許 `35.235.240.0/20`，不得公開 `22`／`5432`。（IAP/OS Login 實測成功；private 5432 僅允許四個 workload tags）
- [x] 規劃無 Cloud NAT 的 PostgreSQL bootstrap／更新來源：使用預建 image 或可經 Private Google Access 取得的核准 Google-hosted artifact；不得假設 Private Google Access 可存取一般 apt internet repository，也不得為安裝套件新增固定費用 NAT。（固定 Google COS boot image；PostgreSQL image 必須先發佈到核准 Google-hosted registry）
- [x] 安裝並固定 PostgreSQL 版本，設定 1 GiB RAM 適用的 shared buffers、work memory、max connections、WAL、statement／idle timeout 與自動啟動。（PostgreSQL 16.15；image digest `sha256:e81c2f294e85fbb0c1ff2d19263a169d987a881c54e21ca8339df4501a7fa636`；restart smoke passed）
- [x] 建立 control、catalog、publication、audit schema／role，credential 僅由 Secret Manager 提供。（五組獨立 version 2；role 均為 non-superuser／non-createdb／non-createrole／non-replication）
- [x] 設定 schema migration runner 與 PostgreSQL readiness check；migration 不得隨 Web deployment 自動執行。（`infra/postgres/bootstrap-vm.sh` 與 migrations；五項 readiness passed）
- [x] 為 Cloud Run／Jobs／DuckDB runtime 設 Direct VPC egress=`private-ranges-only` 與最小 firewall；PostgreSQL ingress 只允許 private subnet `10.42.0.0/24` 連 target tag `janus-postgres-db:5432`。（Cloud Run Direct VPC tag 不支援作為 ingress source selector；2026-08-26 ingestion smoke 驗證）
- [ ] 從 ingestion、Web、Mart Job 與 read-only DuckDB query runtime 驗證 private PostgreSQL 連線與 catalog 基礎查詢；不得使用 Serverless VPC Access connector。（ingestion／DuckDB writer、Web 與 read-only query runtime 已驗證；僅 Mart Job 待驗收）
- [x] 驗證 Free Tier 邊界：單一 eligible `e2-micro` 時數、全部 Standard Persistent Disk ≤30 GB、outbound ≤1 GB/月、無 external IP／NAT／snapshot／replica；未取得 deployment 授權前不得 apply。（2026-08-26 人工確認 eligibility 並授權；實際資源為單一 `e2-micro`、30 GB `pd-standard`、無 external IP／NAT／snapshot／replica；outbound 需持續維持 ≤1 GB/月）
- [x] 記錄 Free Tier dev 無自動備份／HA 的資料遺失風險；正式資料與 raw/cache payload 仍以 GCS 為持久層。（`infra/postgres/README.md`）

## P0 — PostgreSQL Control DB Integration

- [x] 將 control schema 轉為 PostgreSQL migration，保留 FK、CHECK、index 與 transition invariants。（`infra/postgres/migrations/002_control_plane.sql`，可重複執行）
- [x] 實作 PostgreSQL `ControlPlane` adapter；SQLite 僅保留給 unit tests。（`PostgreSQLControlPlane`）
- [x] 以 transaction／row lock／安全 claim 實作 queued execution worker，避免重複執行與遺失 execution。（`FOR UPDATE SKIP LOCKED` + lease）
- [x] 將 response cache 的 payload／raw response 放 GCS Stage；PostgreSQL 只保存 cache key、URI、hash、TTL、observed time 與狀態。（`CacheMetadata`；adapter 禁止 raw payload API）
- [x] 設定低連線數 pool、statement／idle timeout、retry-safe transaction 與 migration lock，適配 `e2-micro` 的 1 GiB RAM。（每 repository 一個注入 connection；pool budget 由 caller 限制）
- [x] 定義 ingestion／DuckDB writer、read-only query、Web/Admin、Mart 與 migration 的 aggregate connection budget，總和不得超過 PostgreSQL `max_connections` 的安全餘額。（server baseline 30；各 workload 使用 bounded factory）
- [x] 設定 execution、telemetry、audit、idempotency 與 cache metadata retention／pruning，避免 30 GB disk 無界成長。（`prune`、expiry indexes、FK cascade）
- [ ] 由 Secret Manager 提供各 workload 獨立 credential，透過 Direct VPC egress/private IP 驗證 ingestion、DuckDB、Web、Mart Job 連線。（2026-08-30：ingestion、DuckDB、Web 專用 credential 與 private path 已驗證；Mart Job 尚未建立）
- [x] 完成 PostgreSQL migration、queue claim、reconnect、idempotency 與 control-plane smoke tests。（程式與 unit tests 完成；實機 workload smoke 待 runtime 部署）

## P0 — DuckDB／Iceberg Core 與查詢基礎

### P0 優先替換計畫：Trino → DuckDB（已完成）

目標：將原 Cloud Run Trino 查詢／merge 路徑改為 Cloud Run 內嵌
DuckDB，直接讀取 GCS Iceberg；PostgreSQL Control DB 暫時保留，繼續保存
collection symbols、ingestion 設定、execution／lock、audit 與必要 catalog
metadata。DuckDB 本機 state 不作持久資料，PostgreSQL 與既有 Iceberg metadata 必須保留。

- [x] 盤點現有 Trino query／merge client、Iceberg connector、catalog DB 與所有呼叫端，定義 DuckDB replacement boundary。
- [x] 確認 DuckDB Cloud Run runtime image、Iceberg extension、GCS authentication 與讀取／寫入相容性。
- [x] 實作 DuckDB Core incremental merge：自然鍵、content hash、idempotent upsert、benchmark／個股獨立 cursor。
- [x] 將 ingestion／Core smoke 改為 DuckDB，驗證 Stage → Core、同日回跑去重與資料涵蓋範圍。
- [x] 建立 DuckDB concurrency／memory／timeout／cold-start 限制；確認不會把 control DB 設定資料當成分析資料處理。
- [x] 完成 Cloud Run canary 與 failure-safe Stage cleanup；未 commit 的 Stage 暫存不被刪除。
- [x] 驗收後停用 Trino；PostgreSQL Control DB／Iceberg JDBC catalog 仍保留。

- [x] 前置條件：PostgreSQL Free Tier VM、PostgreSQL Control DB Integration、Direct VPC egress、control DB 與 catalog DB 已完成並通過連線驗證。
- [x] 固定 Trino baseline 並建立 image；該 baseline 已於 DuckDB 驗收後退役。
- [x] 設定 GCS Iceberg connector；現由 DuckDB／PyIceberg runtime 直接使用 GCS warehouse。
- [x] 設定 JDBC catalog PostgreSQL。（catalog role、private host、Secret Manager env refs）
- [x] 限制 DuckDB memory／query concurrency，避免壓垮 `e2-micro` PostgreSQL。（1 thread、384MB memory、bounded timeout）
- [x] 部署 Cloud Run Job runtime 定義與 Direct VPC egress。（1GiB memory、private catalog connection）
- [x] 設定 GCS Iceberg read／write 與 PostgreSQL SQL catalog 權限。
- [x] 設 DuckDB query memory、concurrency、timeout。（`packages/duckdb_query`）
- [x] 以 Cloud Run Job 內嵌 DuckDB 取代 Trino query／merge client。
- [x] 驗證 DuckDB cold start、GCS Iceberg metadata/data 讀寫及 PostgreSQL catalog reconnect。
- [x] 驗證 failure-safe Stage lifecycle、同日 replay 與 bounded memory／timeout 設定。

## P0 — 2330 Stage → Core 閉環

- [x] 實作 TWSE／TPEx OHLCV adapter。（`jobs/ingestion-core/ingestion_core/sources.py`）
- [x] 觸發 2330 ingestion execution。（`ingestion_core/pipeline.py`）
- [x] 驗證 Stage raw objects 與 sidecar metadata。
- [x] 驗證 Core row count、hash、date coverage、null profile。（`ingestion_core/core.py`）
- [x] 驗證 provenance 三種時間、fallback 與 source／dataset ID。
- [x] 重跑並驗證冪等與有效值不被新 null 覆蓋。
- [x] 驗證 partial／failed／retry 狀態與 quarantine。（framework persisted-state tests）
- [x] 驗證 VM／Job 重啟後 persisted execution、claim lease、idempotency 與 incremental cursor 可恢復。（reference/adaptor tests；實機 workload smoke 仍待 runtime deployment）
- [x] 發出並驗證 `core.dataset.ready.v1`。

## P0 — Core 第一批資料源擴充

- [x] TAIEX／TPEx benchmark。（`first_batch.py` benchmark normalizers）
- [x] PE／PB 與法人。（valuation／institutional normalizers）
- [x] MOPS／FinMind 三類財報。（financials normalizer 保留 statement type／metric／unit）
- [x] 公司事件。（events normalizer，保留更正／effective／published 欄位）
- [x] 融資融券、借券、當沖、注意／處置。（market-activity metric normalizer；不推算缺值）
- [x] issued shares 與 turnover ratio。（market-activity metric／unit-preserving normalizer）
- [x] 休市／盤前最近有效交易日回看。（`effective_trading_day`）
- [x] 驗證 benchmark 在個股行情存在時仍會更新。（獨立 benchmark adapter／測試）
- [x] 驗證新增資料源只把 raw/cache payload 寫 GCS，PostgreSQL metadata retention 與 disk usage 維持有界。（raw payload in `SourceResponse`、control `prune` bounded tests）

## P0 — 資料源雙軌契約與控制面重整

- [x] 在 source／dataset registry 增加 `coverage_tier`、market、cadence、scope、authorization status、retention class、PII 與可再發布欄位；狀態至少包含 `official`、`approved_fallback`、`candidate`、`blocked`。（`packages/contracts/registry.json`、`control_plane.v1.json`）
- [x] 股票 master 支援上市／上櫃狀態與 effective time；全市場完整性依當日 enabled master 計算，不以固定 1,700／2,000 檔判斷。（契約欄位與 market-wide config fallback）
- [x] control DB 建立不可改寫歷史的 coverage membership：`market_wide` 與 `core_focus`；核心名單上限 50 檔，保存 effective time、理由、owner 與 cadence。（SQLite／PostgreSQL migration `004_source_coverage` 與 repository API）
- [x] collection config 分離全市場日頻、核心 50 深度、market-level macro 三種 scope；提高頻率或擴大 scope 必須經驗證與 audit。（`CoverageTier`、cadence、scope、max_symbols）
- [x] 未完成 license／API terms、rate limit、retention、PII、引用、再發布與成本審查的新聞、券商研究、Podcast、社群、分 K／Tick provider 一律保持 disabled／blocked。（source catalog candidate gate；enqueue 會拒絕）
- [ ] 定義文本 entity-to-symbol Core schema；保留規則／模型版本、confidence、evidence 與人工覆核狀態，但 sentiment、buzz、AI alert 與投資判讀只寫 versioned Mart。（契約／WBS／todo 邊界已固定；schema 實作待 P1）
- [ ] source health telemetry 按 coverage tier 保存 expected／received symbols、success count、latency、freshness、cache age、fallback、schema drift 與合法 empty／unavailable。（契約欄位與 P1 telemetry work item 已建立；runtime 聚合待實作）
- [x] 契約測試：核心名單不得超過 50、candidate／blocked 不得排程、核心深度來源不得因全市場 collection 自動 fan-out、membership PIT 不得回填未來狀態。（`tests/contract`、`tests/ingestion/test_control_plane.py`）

## P0 — 排程 Stage → Core、回跑與暫存生命週期

現況：Cloud Run Job 與 07:30 Scheduler 已建立。修正官方 API request／parser
與 Core commit 後，execution `janus-ingestion-core-n88jc` 已完成 8／8 Stage →
Core（0 failure、8 個 Core partition）；同日回跑 `janus-ingestion-core-nxmwc`
為 `core_created=0`、`core_reused=79,262`，Core object 維持 8 個。DB-backed
五檔設定與 private connection smoke `janus-ingestion-core-nbql7` 已通過，Scheduler
已恢復為 ENABLED；DuckDB 替換與完整 Core merge 已完成，Admin 設定維護介面仍待後續。

- [x] 修正第一批 8 個正式來源的 request／解析並完成雲端 Stage → Core smoke 與同日冪等回跑。（Cloud Build `7622adf8-3d62-4202-b1d9-694542db04af`；executions `janus-ingestion-core-n88jc`、`janus-ingestion-core-nxmwc`）

- [x] 每日 08:00 前的 ingestion 排程必須在收集進 Stage 後，於同一 execution 完成 Stage → DQ → Core；任一必要步驟失敗時 execution 不得標示成功。（Cloud Run entrypoint 以同一 execution ID 串接，Core 失敗或任一來源失敗即以 non-zero 結束）
- [x] 排程型 Stage payload 採 execution-scoped 一次性暫存；清理 API 只有在 immutable Core commit marker 存在時，才刪除該 execution 的 payload、sidecar 與 manifest；失敗／重試中或未 commit 的 execution 保留。（`StageWriter.mark_core_committed`／`cleanup_committed_execution`）
- [x] 提供指定單日、起訖日期區間與指定資料源的 backfill／replay；回跑使用獨立 execution，不受每日排程的「前一次 Stage 清理」誤刪。（`INGESTION_DATE`／`BACKFILL_START_DATE`+`BACKFILL_END_DATE`／`INGESTION_DATASETS`；每次 job run 產生獨立 execution ID）
- [x] Core 採 append／incremental merge；以各 dataset 的自然鍵與 content hash 做 idempotent upsert，重跑同日期或相同資料不得產生 duplicate key 或重複 row。（Cloud Run clean canary：`core_created=420`；同日 replay：`core_created=0`、`core_reused=420`、`failed=0`）
- [x] benchmark 與個股資料保持獨立 cursor／commit，個股資料已存在時 benchmark 仍可增量更新。（5 個 Core Iceberg tables 均完成 snapshot／metadata 驗收）
- [ ] Admin UI 可調整啟用資料源、排程時間、交易日／holiday override、單日或區間回跑參數、Stage retention／cleanup 開關；所有設定須驗證、稽核並以 control database 持久化。
- [ ] Admin UI 提供 execution 狀態、Stage／Core commit、清理結果、資料源失敗與 backfill 進度；敏感錯誤只顯示 safe message。
- [ ] 增加整合測試：排程閉環、前次 Stage 安全清理、失敗保留、日期區間回跑、指定來源回跑、Core 重跑去重、benchmark 獨立更新與 Admin 設定驗證。
- [x] 雲端驗收：Cloud Scheduler 為 `ENABLED`；private DB／五檔 Stage → Core smoke `janus-ingestion-core-nbql7` 成功（8 sources、10 Stage objects、0 failure、Core reused 419、合法 empty 2），並沿用已驗收的 Core commit／GCS cleanup fence。

## P0 — Core 資料服務與可觀測性

- [x] 建立 Core query API／BFF，禁止前端直接讀 Stage raw objects。（`packages/web_api` + `/api/v1/core`；僅讀 Iceberg Core）
- [x] 提供股票資料日期、涵蓋範圍、row count、null profile、quality flags 摘要。（`CoreQueryService.summary`）
- [x] 提供 source／dataset、provenance、execution 與 Core snapshot 關聯。（摘要 `associations`；row metadata 保留於 Core）
- [x] 建立 persisted source health telemetry：success rate、latency、last fetched、latest observation。（SQLite／PostgreSQL aggregate fields 與 Admin read surface）
- [x] Core query API／BFF 使用 bounded PostgreSQL pool、statement timeout 與 indexed pagination；不得每 request 建立新 DB connection。（單 repository connection、catalog pool size=1/max_overflow=0、DuckDB bounds）
- [x] 建立 PostgreSQL VM health、connection count、disk usage、deadlock、slow query 與 retention telemetry；控制 log／metric volume 避免額外費用。（`PostgresHealthCollector` fixed aggregate queries）
- [x] 安全輸出不得包含 raw payload、secret、敏感 URL、完整 upstream error 或 traceback。（redaction／safe boundary tests）
- [x] Query API 的 DuckDB instance 必須 read-only、使用獨立 memory／timeout／row limit 與 catalog reader role，不得取得 Core commit 權限或共用 ingestion 本機 DuckDB 檔案。（2026-08-30：Cloud Run 專用 credential、Core 200 smoke、catalog `default_transaction_read_only=on` 且 0 張 table 具寫入權限）

2026-08-30 實機驗證證據：`janus-web-00023-ccj` 使用 Direct VPC `private-ranges-only`／`janus-web` tag；公開 `/health`、`/login` 回 200，未登入 Admin／Core 分別回 303／401，短效簽章 session 下 Admin 與 Core 皆回 200。Cloud Run Jobs 仍無 `janus-intelligence-mart`，故 Mart private DB smoke 尚未執行。

本機驗收證據（2026-08-30）：`python -m unittest discover -s tests -v`，77 tests passed；`python -m compileall -q apps packages jobs`、`node --check apps/web/static/admin.js`、`python -m pip check`、Git Bash `bash -n infra/postgres/bootstrap-vm.sh` 與 `git diff --check` 通過。

## P0 — Admin Data Operations MVP

- [x] 股票搜尋、分頁、enabled、關聯刪除保護。（`AdminService`、`/api/v1/admin/stocks`；63 tests passed）
- [x] 跨頁選取與 collection／analysis 分開觸發。（`apps/web/static/admin.js`、queue routes）
- [x] collection 只寫 control DB／queue，不在 request 中執行長任務。（control-plane enqueue contract）
- [x] Admin 寫入使用 transaction、optimistic concurrency 與 workload-specific PostgreSQL role；不得取得 bootstrap／catalog owner 權限。（2026-08-30：Web control role 實機驗證指定 control tables 的 DML 權限完整，且不是 superuser／owner；authenticated audit actor 測試通過）
- [x] 最近 50 次 persisted execution。（bounded API/UI）
- [x] execution details 按需讀取。（row action only）
- [ ] 股票資料狀態頁：Core 最新日期、資料集覆蓋、row count、DQ／quarantine 摘要。
- [x] Data-source health 只讀 persisted telemetry。
- [ ] Admin 查詢使用 bounded pool、statement timeout、indexed cursor pagination 與按需 details，避免耗盡 `e2-micro` connections／RAM。
- [x] Admin UI 正確呈現 queued／running／partial／failed／retrying／unavailable。（state badges／safe fallback）
- [ ] Admin UI 管理全市場／核心 50 membership、effective date、cadence 與來源 authorization status；超過 50 檔或啟用 blocked source 時必須拒絕並留下 audit。

2026-08-28 WBS 6 Admin UI 切片：已建立 `/admin/stocks` responsive 操作介面與
同源 API，涵蓋每頁 10 筆搜尋、enabled toggle、跨頁選取、collection／analysis
分流 queue、最近 50 次 execution／按需明細、persisted source health，以及核心
50 membership effective-time edit。另已補股票新增／編輯／關聯刪除保護 UI、排程與
 retention 設定表單、設定 optimistic version、Admin audit API、Core 狀態查詢 route；
Admin 專項 12 tests（全套 63 tests）passed，JavaScript syntax、Python compileall
與 diff check passed；尚待 cadence／authorization／quota 管理 UI、scheduler／source
catalog 實際 wiring、股票狀態頁完整 DQ／quarantine 聚合、PostgreSQL runtime secret
配置，以及 Vitest／Playwright／實機瀏覽器驗收。
2026-08-28 P0 execution update：已補上 Web 的可選 PostgreSQL／Iceberg
read-only runtime wiring、Admin stock upsert API，並部署 dev Cloud Run
`janus-web-00001-dvz`（immutable image digest 已保存）。目前 service 未配置
Web 專用 control/catalog credential，因此 runtime 保持 safe fallback；專用
credential、Mart Job runtime 與 authenticated HTTP／DB smoke 仍待完成。

2026-08-28 HTTP authenticated smoke：已安裝 Cloud SDK `cloud-run-proxy`，並在
`janus-web` 加入 dev user token 的 custom audience。revision
`janus-web-00002-472` 通過 direct URL 與 localhost proxy 驗證：`/health`、
`/admin/stocks`、`/assets/admin.css` 均 HTTP 200；service 只授予
`user:tommylin15@gmail.com` `roles/run.invoker`，未開放 `allUsers`。Token Creator
未保留。DB-connected Web/Admin 與 Mart runtime 仍待專用 credential／Job。

2026-08-30 Web runtime 驗收：公開入口改採 `allUsers` invoker，application layer
只公開 `/health`、`/login`、`/auth/google`，其餘要求 Google allowlist session。
revision `janus-web-00023-ccj` 的 Admin／Core 登入態 smoke 均回 200；catalog role
為 transaction read-only 且無 table write privilege，control role 對指定 control
tables 使用一致 DML 權限。Secret rotation 已依 raw-byte/BOM 與 runtime smoke
驗證，舊版本 disabled。真人 Google 登入與 OAuth Console redirect URI 保留一次性
人工驗收；下一個獨立 WBS 為 `janus-intelligence-mart` runtime。

## P0 — Stage／Core 與 Admin MVP 驗證

- [ ] 2330 Source → Stage → Core → Admin 查詢整合測試。
- [ ] Backend pytest 與 contract tests。
- [ ] Iceberg schema evolution tests。
- [ ] Failure／retry／idempotency tests。
- [ ] PostgreSQL migration、role isolation、queue claim、connection exhaustion、VM restart/reconnect、retention/pruning tests。
- [ ] Direct VPC egress／firewall tests：指定 workload 可連 `5432`，public internet、未授權 identity 與其他 network tag 不可連線。
- [ ] Free Tier gcloud guard tests：只允許一台 `e2-micro`、eligible `us-central1` zone、全部 Standard Persistent Disk ≤30 GB、無 external IP／NAT／snapshot／replica／Serverless VPC connector。
- [ ] 安全輸出與 log redaction tests。
- [ ] TypeScript／ESLint／production build。
- [ ] Admin UI Vitest 與 Playwright interaction tests。
- [ ] UI 驗收可使用本地瀏覽器／Playwright，或按需啟動既有 GCP dev Cloud Run
  service，以實際 dev URL 驗證 responsive、interaction、API/runtime connectivity
  與安全輸出；既有 dev service 通過人工 billing gate 後可直接啟動，不需逐次
  另行授權。驗收證據須記錄 revision、immutable image digest、測試 URL／時間與
  scale-to-zero 狀態；不得部署 production、提高既有限額或建立新付費資源。

2026-08-28 本機驗證紀錄：Python unittest 全套 63/63 通過，涵蓋 contract、2330
Stage → Core closed loop、DQ、Stage cleanup fence、retry／fallback／idempotency、
DuckDB／Iceberg、Admin API、safe output 與 Web routes；compileall、git diff --check、
gcloud bootstrap guard、Bash syntax、JSON（含 BOM）解析及 JavaScript syntax 亦通過。Vitest 2/2
與 Playwright 1/1 通過。pytest 未安裝；專案目前沒有 TypeScript／ESLint／production
build script。PostgreSQL 真實連線／角色隔離／VM restart、Direct VPC firewall、
Cloud Run DB-connected query、完整 2330 → Admin 整合及 scale-to-zero 仍未在本機或
本次執行中驗證；未部署 production 或建立新付費 GCP 資源。

## P1 — 全市場量化網

- [ ] 以當日 enabled 股票 master 收集全市場日 OHLCV、PE/PB、法人、融資券／借券／當沖、基本面摘要與官方 benchmark。
- [ ] 對 market-scope endpoint 採單次抓取、批次快取與 symbol fan-out；不得逐檔重複請求。
- [ ] 產製每日 market coverage report：expected／received／missing symbols、來源成功數、freshness、合法 empty／unavailable 與 DQ 摘要。
- [ ] 建立 `mart_screening_signals`：技術面突破、量能、流動性與異動候選；結果不得在 collection request 內即時計算。
- [ ] 驗證全市場同日 replay 冪等、bounded memory／runtime、GCS 成本與缺檔不被誤標成功。

## P1 — 核心 50 放大鏡

- [ ] 以 control DB 核心 membership 收集深度財報、公司事件／重大訊息、公司行動與 PIT publication time。
- [ ] 對已核准行情來源建立分 K／Tick 獨立排程、quota、retention、failure policy 與成本量測；未核准前保持 blocked。
- [ ] 新聞／券商研究／目標價逐一完成來源授權與 provenance 審查後，才可建立 adapter 與 retention policy。
- [ ] Podcast／PTT／Dcard／股市爆料同學會等另類文本先完成平台條款、PII、刪除、引用與再發布政策；未核准不得收集。
- [ ] 建立文本正規化、dedup、language、published time、entity-to-symbol 與 source authority Core tables。
- [ ] 驗證核心名單變更不改寫歷史 membership，移出名單後停止深度收集但保留依法可保存的歷史 provenance。

## P1 — Mart／Agents

- [ ] Mart Job 只透過 Direct VPC egress 與專用 read/write role 存取 PostgreSQL metadata；feature／evidence payload 留在 GCS／Iceberg。
- [ ] `mart_screening_signals`、`mart_core_alpha`、`mart_risk_portfolio`、`mart_alternative_sentiment` 與 `mart_master_investment_memo` versioned schemas。
- [ ] Fundamental features／Agent。
- [ ] Valuation features／Agent。
- [ ] Positioning features／Agent。
- [ ] Quant features／Agent。
- [ ] Event Risk features／Agent。
- [ ] Evidence Validator。
- [ ] Devil's Advocate 反證階段只引用合格 evidence，不得自行補資料或產生無來源數字。
- [ ] Aggregator bull／bear／contradictions／contributions。
- [ ] 30% insufficient-data gate。
- [ ] blocked／publishable view。
- [ ] immutable governance snapshot version。
- [ ] deterministic rerun tests。
- [ ] RAG 只檢索 analysis-as-of 可見的 Core／Mart snapshot，並以測試阻擋 future leakage。

## P1 — LLM

- [ ] 建立 evidence-only structured prompt。
- [ ] 禁止模型產生未在 evidence 出現的數字。
- [ ] 禁止模型修改 score、confidence、quality、publication。
- [ ] 接 Gemini，並固定 provider 優先順序為 Gemini → OpenRouter → GroqCloud。
- [ ] 實作 Gemini → OpenRouter → GroqCloud 的 429／`RESOURCE_EXHAUSTED`／provider unavailable fallback。
- [ ] 非 429 結構化失敗。
- [ ] LLM 失敗不得寫 placeholder report。
- [ ] LLM 關閉時 deterministic outputs 完全一致。

## P1 — Mart 閉環

- [ ] 產製 versioned Mart tables。
- [ ] 寫 report／model／governance metadata。
- [ ] 寫 PostgreSQL publication service index。
- [ ] publication index 使用 migration、唯一鍵、bounded pool、retention 與 workload-specific role；不得把完整 report payload 寫入 PostgreSQL。
- [ ] 發出 `mart.report.ready.v1`。
- [ ] 驗證 blocked 不進 publishable view。
- [ ] 驗證 2330 Core → Mart 可重現。

## P1 — Admin Governance／Reports

- [ ] Governance／audit metadata 使用 PostgreSQL migration、optimistic lock、retention 與專用 role；大 payload／diff artifact 放 GCS。
- [ ] Governance typed editing、validation、diff、history、optimistic lock。
- [ ] Report block／unblock 保存理由與 audit。

## P1 — Public API／UI

- [ ] Health、topics、summary。
- [ ] Latest report、history、Kline、events。
- [ ] 未知／停用股票 404。
- [ ] 已啟用無資料顯示等待批次。
- [ ] 查無資料不觸發 scraper／Agent／LLM。
- [ ] blocked、raw payload、secret、traceback 不公開。
- [ ] Public API 只讀 PostgreSQL service index／publishable metadata，使用 bounded read-only pool 與 statement timeout；不得直連 catalog owner 或觸發即時抓取。
- [ ] 完成 `ui.md` 所有 P0 元件。
- [ ] 全市場 screening 與核心標的深度頁分流；顯示 coverage、freshness、來源健康與資料不足。
- [ ] 情緒溫度計、多空雷達圖與風險紅綠燈只顯示後端 versioned Mart，前端不得自行計分。

## P1 — 全系統自動化測試

- [ ] Backend pytest、contract tests、Frontend Vitest。
- [ ] Playwright responsive／interaction。
- [ ] TypeScript／ESLint／production build。
- [ ] Iceberg schema evolution tests。
- [ ] Failure／retry／idempotency tests。
- [ ] PostgreSQL role isolation、pool exhaustion、restart/reconnect、migration rollback 與 publication index tests。
- [ ] 安全輸出與 log redaction tests。

## P2 — PIT 與治理校準

- [ ] PIT outcome／sample payload 寫 GCS／Iceberg；PostgreSQL 只保存有 retention 的索引、排除原因與 audit metadata，避免 Free Tier disk 無界成長。
- [ ] 5／20／60 交易日 outcome pipeline。
- [ ] relative benchmark、MFE／MAE、coverage。
- [ ] 缺 publication time／provenance 樣本排除。
- [ ] 每個排除保留原因與 ID。
- [ ] 對 30% gate 做 coverage／錯誤率分析。
- [ ] 對 weights／40-60 thresholds 做 walk-forward。
- [ ] 建立正式治理 revision 提案。

## P2 — 實機、A11y 與發布

- [ ] iOS Safari。
- [ ] Android Chrome。
- [ ] iPad Safari。
- [ ] VoiceOver／TalkBack。
- [ ] WCAG AA contrast。
- [ ] 所有主要控制 ≥44×44。
- [ ] K 線 pan／zoom／tooltip／替代表格。
- [ ] Dialog focus trap、Escape、restore、scroll lock。
- [ ] canary／rollback。
- [ ] production 發布前重新決定 PostgreSQL topology、HA、backup、retention 與成本；Free Tier `e2-micro` dev VM 不得直接 promote 為 production。
- [ ] 取得付費儲存／backup 明確授權後，執行 production backup／restore 演練；Free Tier dev 模式不宣稱具備備份保障。
- [ ] incident runbook。
- [ ] production 人工批准。

## P3 — OmniForge／PodBrief

- [ ] 只從 publishable Mart／service index 匯出 report 的 Markdown exporter；不得掃描 PostgreSQL control/catalog 或將大 payload 複製回 Free Tier VM。
- [ ] YAML schema validator。
- [ ] 小白／一般／分析師／Auditor 四階視圖。
- [ ] 雙鏈與標籤。
- [ ] Podcast 授權與保存政策。
- [ ] 逐字稿、時間碼與摘要 provenance。

## 每張 TODO 的完成證據

完成項目至少附一種：PR URL、commit SHA、Cloud Build ID、image digest、Cloud Run revision／execution ID、GCS snapshot ID、test report、實機錄影／截圖、治理 revision ID 或 runbook link。
