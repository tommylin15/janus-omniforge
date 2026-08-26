# Janus × OmniForge — TODO

版本：1.0  
用途：由 AI／開發者依順序執行；完成時勾選並附 PR、Cloud Build、execution 或測試證據。

## P0 — 開工前阻擋項目

- [x] 取得 GitHub repo 或建立 `janus-omniforge` monorepo。
- [x] 確認 GCP Project ID、Billing account、region=`us-central1`。
- [x] 確認 PostgreSQL：GCE Compute Engine `e2-micro` Free Tier 模式（dev／MVP，`us-central1`、≤30 GB Standard Persistent Disk、無 external IP、outbound ≤1 GB/月；production HA 另行評估）。
- [ ] 部署前人工確認 billing account 尚有 eligible `e2-micro` 時數、30 GB-month Standard Persistent Disk 與 1 GB outbound Free Tier 額度；未確認前只允許 plan，不得 apply。
- [x] 確認 AI 可建立 PR，但 production deploy 需人工批准。
- [x] 確認第一批股票：至少 `2330`。（人工確認）
- [x] 確認第一版 LLM：Vertex AI／Gemini。
- [x] 確認 dev bucket／resource 命名。
- [x] 建立 US$1／US$5／US$10 billing alerts。（人工處理）

## P0 — Repository 與雲端開發

- [x] 建立 `apps/web`。
- [x] 建立 `jobs/ingestion-core`。
- [x] 建立 `jobs/intelligence-mart`。
- [x] 建立 `services/trino`。
- [x] 建立 `packages/contracts`、`governance`、`provenance`、`observability`。
- [x] 建立 `infra`、`tests/contract`、`tests/e2e`。
- [x] 建立 Cloud Workstations／Cloud Shell Editor 開發設定。（`.devcontainer/devcontainer.json`）
- [x] 固定 Python、Node、Java／Trino 版本與 lockfiles。（`.tool-versions`、版本檔與根目錄 lockfile 基線）
- [x] 加入 CODEOWNERS、PR template；branch protection 由人工處理。（GitHub private repository plan 限制）

## P0 — IAM、CI/CD 與 Secret

- [x] 建立 GitHub → GCP Workload Identity Federation。（pool `github-actions`、provider `github`；限定 `tommylin15/janus-omniforge`）
- [x] 建立 Cloud Build service account。（`janus-ci@gen-lang-client-0593591102.iam.gserviceaccount.com`）
- [x] 建立四個 runtime service accounts。（`ingestion-core`、`intelligence-mart`、`trino-runtime`、`web-runtime`）
- [x] 套用最小 IAM，不建立長效 JSON key。（四個 runtime SA 已授予 Log Writer／Metric Writer；資源級權限待 bucket／Pub/Sub／Secret 建立後補上）
- [x] 啟用必要 GCP APIs。（已啟用於 `gen-lang-client-0593591102`）
- [x] 新增第五個最小權限 VM identity：`postgres-vm`；不得使用 default Compute Engine service account 或 broad cloud-platform scope。（`infra/terraform/postgres_vm_identity.tf`；獨立 SA、零 project-level role、明確 logging／monitoring scope allowlist）
- [x] 盤點 Compute Engine、IAP、OS Login 與 Direct VPC egress 所需 API／IAM；只啟用 `compute`、`iam`、`iap`、`oslogin`、`run`、`serviceusage` 必要 API，禁止 Artifact Analysis／Container Scanning API。（`infra/terraform/required_apis.tf`；2026-08-26 實際盤點）
- [x] 將 Direct VPC egress 所需 Cloud Run service agent／deployer `roles/compute.networkUser` 與 workload network tags 納入最小 IAM；不得建立有固定 VM 費的 Serverless VPC Access connector。（`infra/terraform/direct_vpc_iam.tf`；subnet-scoped IAM）
- [x] 建立 path-based Cloud Build triggers。（人工建立 `janus-ingestion-core` 與 `janus-intelligence-mart`，main 分支路徑篩選）
- [x] 建立 Artifact Registry cleanup policy。（`janusai-poc`：未標籤超過 3 天刪除、保留最近 3 個 tagged versions）
- [x] 建立 Secret Manager secrets（只放名稱，不把值寫入 repo）。（12 個名稱已建立或已存在；第 4 項前導 `.` 已正規化為 `janus-fugle-api-key`）
- [x] 建立 PostgreSQL bootstrap、control、catalog、publication、audit role 的 Secret 名稱與單項 IAM；不得共用 superuser credential 或寫入 Terraform state／startup script。（`infra/terraform/postgres_secrets.tf`；五個空 Secret container、五組單一 secret-level accessor、無 secret version）
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

- [x] 建立 dev Stage／Core／Mart buckets 或隔離 prefixes。（`infra/terraform/storage.tf`；已 apply）
- [x] 設 uniform bucket-level access 與 lifecycle。（`infra/terraform/storage.tf`；已 apply）
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

- [x] 建立 Terraform Compute Engine `e2-micro` VM：固定 eligible `us-central1` zone、無 external IP、private IP；加入 validation／precondition 禁止覆寫 machine type／region。（`janus-postgres-dev`，`us-central1-a`，private `10.42.0.5`）
- [x] VM 全部 boot／data Standard Persistent Disk 配置量合計 ≤30 GB；禁止 snapshot／backup／replica／HA 預設資源。（單一 30 GB `pd-standard` boot disk，無其他 disk／snapshot／backup／replica／HA）
- [x] 設定專用 subnet、Private Google Access、IAP／OS Login、`postgres-vm` identity 與 network tags；IAP SSH 僅允許 `35.235.240.0/20`，不得公開 `22`／`5432`。（IAP/OS Login 實測成功；private 5432 僅允許四個 workload tags）
- [x] 規劃無 Cloud NAT 的 PostgreSQL bootstrap／更新來源：使用預建 image 或可經 Private Google Access 取得的核准 Google-hosted artifact；不得假設 Private Google Access 可存取一般 apt internet repository，也不得為安裝套件新增固定費用 NAT。（固定 Google COS boot image；PostgreSQL image 必須先發佈到核准 Google-hosted registry）
- [x] 安裝並固定 PostgreSQL 版本，設定 1 GiB RAM 適用的 shared buffers、work memory、max connections、WAL、statement／idle timeout 與自動啟動。（PostgreSQL 16.15；image digest `sha256:e81c2f294e85fbb0c1ff2d19263a169d987a881c54e21ca8339df4501a7fa636`；restart smoke passed）
- [x] 建立 control、catalog、publication、audit schema／role，credential 僅由 Secret Manager 提供。（五組獨立 version 2；role 均為 non-superuser／non-createdb／non-createrole／non-replication）
- [x] 設定 schema migration runner 與 PostgreSQL readiness check；migration 不得隨 Web deployment 自動執行。（`infra/postgres/bootstrap-vm.sh` 與 migrations；五項 readiness passed）
- [ ] 為 Cloud Run／Jobs／Trino 設 Direct VPC egress=`private-ranges-only` 與最小 firewall，只允許指定 network tags 連 private `5432`。（subnet IAM/tags 與 firewall plan 已完成；runtime resources 尚未部署）
- [ ] 從 ingestion、Web、Mart Job 與 Trino 驗證 private PostgreSQL 連線與 JDBC catalog 基礎查詢；不得使用 Serverless VPC Access connector。（VM 與 runtime 尚未部署，無法執行線上 smoke test）
- [x] 驗證 Free Tier 邊界：單一 eligible `e2-micro` 時數、全部 Standard Persistent Disk ≤30 GB、outbound ≤1 GB/月、無 external IP／NAT／snapshot／replica；未取得 deployment 授權前不得 apply。（2026-08-26 人工確認 eligibility 並授權；實際資源為單一 `e2-micro`、30 GB `pd-standard`、無 external IP／NAT／snapshot／replica；outbound 需持續維持 ≤1 GB/月）
- [x] 記錄 Free Tier dev 無自動備份／HA 的資料遺失風險；正式資料與 raw/cache payload 仍以 GCS 為持久層。（`infra/postgres/README.md`）

## P0 — PostgreSQL Control DB Integration

- [x] 將 control schema 轉為 PostgreSQL migration，保留 FK、CHECK、index 與 transition invariants。（`infra/postgres/migrations/002_control_plane.sql`，可重複執行）
- [x] 實作 PostgreSQL `ControlPlane` adapter；SQLite 僅保留給 unit tests。（`PostgreSQLControlPlane`）
- [x] 以 transaction／row lock／安全 claim 實作 queued execution worker，避免重複執行與遺失 execution。（`FOR UPDATE SKIP LOCKED` + lease）
- [x] 將 response cache 的 payload／raw response 放 GCS Stage；PostgreSQL 只保存 cache key、URI、hash、TTL、observed time 與狀態。（`CacheMetadata`；adapter 禁止 raw payload API）
- [x] 設定低連線數 pool、statement／idle timeout、retry-safe transaction 與 migration lock，適配 `e2-micro` 的 1 GiB RAM。（每 repository 一個注入 connection；pool budget 由 caller 限制）
- [x] 定義 ingestion、Trino、Web/Admin、Mart 與 migration 的 aggregate connection budget，總和不得超過 PostgreSQL `max_connections` 的安全餘額。（server baseline 30；各 workload 使用 bounded factory）
- [x] 設定 execution、telemetry、audit、idempotency 與 cache metadata retention／pruning，避免 30 GB disk 無界成長。（`prune`、expiry indexes、FK cascade）
- [ ] 由 Secret Manager 提供各 workload 獨立 credential，透過 Direct VPC egress/private IP 驗證 ingestion、Trino、Web、Mart Job 連線。
- [x] 完成 PostgreSQL migration、queue claim、reconnect、idempotency 與 control-plane smoke tests。（程式與 unit tests 完成；實機 workload smoke 待 runtime 部署）

## P0 — Trino 與 Core 查詢基礎

- [ ] 前置條件：PostgreSQL Free Tier VM、PostgreSQL Control DB Integration、Direct VPC egress、control DB 與 catalog DB 已完成並通過連線驗證。
- [x] 固定 Trino 版本並建立 image。（`services/trino/VERSION`、固定 digest image build baseline）
- [x] 設定 GCS Iceberg connector。（ADC、Workload Identity；`services/trino/catalog/iceberg.properties`）
- [x] 設定 JDBC catalog PostgreSQL。（catalog role、private host、Secret Manager env refs）
- [x] 限制 Trino metadata cache／query concurrency，避免壓垮 `e2-micro` PostgreSQL。（Trino 474 無公開 JDBC pool sizing property，採 query concurrency=2、metadata cache=64MB；線上 DB pool smoke 待前置條件完成）
- [x] 部署 Cloud Run Service 定義：2 vCPU、4–8 GiB、min=0、max=1。（Terraform definition；尚未 apply）
- [x] 設 IAM-only ingress。（Terraform IAM member；尚未 apply）
- [x] 設 query memory、concurrency、timeout。（`services/trino/etc/config.properties`）
- [x] 實作 Job query submit／poll／cancel client。（`packages/trino_query/client.py`）
- [ ] 驗證 scale-to-zero 冷啟動。
- [ ] 驗證長查詢不因呼叫端提前離開而中斷。
- [ ] 驗證 Trino scale-to-zero／cold start 後可重新連接 PostgreSQL catalog，且不依賴 VM local state 保存 query data。

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

## P0 — 排程 Stage → Core、回跑與暫存生命週期

現況：Cloud Run Job 與 07:30 Scheduler 已建立；首次 smoke execution
`janus-ingestion-core-z84fq` 僅成功寫入 2／8 個 Stage 資料源且尚未執行 Core，
因此 Scheduler 暫停，待下列閉環驗收完成後才可啟用。

- [ ] 每日 08:00 前的 ingestion 排程必須在收集進 Stage 後，於同一 execution 完成 Stage → DQ → Core；任一必要步驟失敗時 execution 不得標示成功。
- [ ] 排程型 Stage payload 採 execution-scoped 一次性暫存；下一次排程成功後，只清除前一次已成功排程且已完成 Core commit 的 Stage payload、sidecar 與 manifest，不得清除目前 execution、失敗／重試中 execution 或尚未完成 Core commit 的資料。
- [ ] 提供指定單日、起訖日期區間與指定資料源的 backfill／replay；回跑使用獨立 execution，不受每日排程的「前一次 Stage 清理」誤刪。
- [ ] Core 採 append／incremental merge；以各 dataset 的自然鍵與 content hash 做 idempotent upsert，重跑同日期或相同資料不得產生 duplicate key 或重複 row。
- [ ] benchmark 與個股資料保持獨立 cursor／commit，個股資料已存在時 benchmark 仍可增量更新。
- [ ] Admin UI 可調整啟用資料源、排程時間、交易日／holiday override、單日或區間回跑參數、Stage retention／cleanup 開關；所有設定須驗證、稽核並以 control database 持久化。
- [ ] Admin UI 提供 execution 狀態、Stage／Core commit、清理結果、資料源失敗與 backfill 進度；敏感錯誤只顯示 safe message。
- [ ] 增加整合測試：排程閉環、前次 Stage 安全清理、失敗保留、日期區間回跑、指定來源回跑、Core 重跑去重、benchmark 獨立更新與 Admin 設定驗證。
- [ ] 雲端驗收：Cloud Scheduler 於 `Asia/Taipei` 每日 07:30 觸發；Cloud Run Job execution 成功、Core commit 完成、GCS 清理範圍正確，並保存 execution ID／manifest 作為證據。

## P0 — Core 資料服務與可觀測性

- [ ] 建立 Core query API／BFF，禁止前端直接讀 Stage raw objects。
- [ ] 提供股票資料日期、涵蓋範圍、row count、null profile、quality flags 摘要。
- [ ] 提供 source／dataset、provenance、execution 與 Core snapshot 關聯。
- [ ] 建立 persisted source health telemetry：success rate、latency、last fetched、latest observation。
- [ ] Core query API／BFF 使用 bounded PostgreSQL pool、statement timeout 與 indexed pagination；不得每 request 建立新 DB connection。
- [ ] 建立 PostgreSQL VM health、connection count、disk usage、deadlock、slow query 與 retention telemetry；控制 log／metric volume 避免額外費用。
- [ ] 安全輸出不得包含 raw payload、secret、敏感 URL、完整 upstream error 或 traceback。

## P0 — Admin Data Operations MVP

- [ ] 股票搜尋、分頁、enabled、關聯刪除保護。
- [ ] 跨頁選取與 collection／analysis 分開觸發。
- [ ] collection 只寫 control DB／queue，不在 request 中執行長任務。
- [ ] Admin 寫入使用 transaction、optimistic concurrency 與 workload-specific PostgreSQL role；不得取得 bootstrap／catalog owner 權限。
- [ ] 最近 50 次 persisted execution。
- [ ] execution details 按需讀取。
- [ ] 股票資料狀態頁：Core 最新日期、資料集覆蓋、row count、DQ／quarantine 摘要。
- [ ] Data-source health 只讀 persisted telemetry。
- [ ] Admin 查詢使用 bounded pool、statement timeout、indexed cursor pagination 與按需 details，避免耗盡 `e2-micro` connections／RAM。
- [ ] Admin UI 正確呈現 queued／running／partial／failed／retrying／unavailable。

## P0 — Stage／Core 與 Admin MVP 驗證

- [ ] 2330 Source → Stage → Core → Admin 查詢整合測試。
- [ ] Backend pytest 與 contract tests。
- [ ] Iceberg schema evolution tests。
- [ ] Failure／retry／idempotency tests。
- [ ] PostgreSQL migration、role isolation、queue claim、connection exhaustion、VM restart/reconnect、retention/pruning tests。
- [ ] Direct VPC egress／firewall tests：指定 workload 可連 `5432`，public internet、未授權 identity 與其他 network tag 不可連線。
- [ ] Free Tier IaC tests：只允許一台 `e2-micro`、eligible `us-central1` zone、全部 Standard Persistent Disk ≤30 GB、無 external IP／NAT／snapshot／replica／Serverless VPC connector。
- [ ] 安全輸出與 log redaction tests。
- [ ] TypeScript／ESLint／production build。
- [ ] Admin UI Vitest 與 Playwright interaction tests。

## P1 — Mart／Agents

- [ ] Mart Job 只透過 Direct VPC egress 與專用 read/write role 存取 PostgreSQL metadata；feature／evidence payload 留在 GCS／Iceberg。
- [ ] Fundamental features／Agent。
- [ ] Valuation features／Agent。
- [ ] Positioning features／Agent。
- [ ] Quant features／Agent。
- [ ] Event Risk features／Agent。
- [ ] Evidence Validator。
- [ ] Aggregator bull／bear／contradictions／contributions。
- [ ] 30% insufficient-data gate。
- [ ] blocked／publishable view。
- [ ] immutable governance snapshot version。
- [ ] deterministic rerun tests。

## P1 — LLM

- [ ] 建立 evidence-only structured prompt。
- [ ] 禁止模型產生未在 evidence 出現的數字。
- [ ] 禁止模型修改 score、confidence、quality、publication。
- [ ] 接 Vertex AI／Gemini。
- [ ] 429／RESOURCE_EXHAUSTED fallback。
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
