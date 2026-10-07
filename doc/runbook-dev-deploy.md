# Dev 部署與 PostgreSQL Migration Runbook

本文件只記錄**目前可重複執行的 dev 操作程序**。一次性的 build ID、revision、image digest、歷史 split checkpoint 與舊 topology 不固定在本 runbook；需要目前實際狀態時，先查 GitHub `main`、GCP runtime，再對照 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

目前 `dev` 是 Janus 個人使用階段的真實平行上線環境。部署、migration、Secret rotation、Job execution 都可能影響真實個人資料；執行前必須遵守 [`PROJECT_RULES.md`](PROJECT_RULES.md) 的費用、安全與不可逆操作授權規則。

## 1. 固定環境與工具

目前 GCP dev 使用：

```powershell
$gcloud = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
$project = "gen-lang-client-0593591102"
$region = "us-central1"
$zone = "us-central1-a"
```

Windows PowerShell 優先使用 `gcloud.cmd`；不要為解決 shell 問題放寬 ExecutionPolicy。

執行前至少確認：

- GitHub ref 是預期的 `main` commit；
- 目標是既有 dev resource，而不是新建 production／付費 topology；
- 需要的人工費用／安全授權已取得；
- 目前 Cloud Run／Job image、Secret references、revision／execution 狀態已先唯讀查證。

## 2. Dev bootstrap

目前 bootstrap entrypoint 為 `scripts/gcp/provision-dev.sh`。它應只用於既有 dev topology，並由腳本 guard 檢查 PostgreSQL Free Tier shape。

```powershell
$env:GCP_PROJECT_ID = $project
$env:GCP_REGION = $region
$env:GCP_ZONE = $zone
$env:GITHUB_REPOSITORY = "tommylin15/janus-omniforge"
$env:GCP_CI_SERVICE_ACCOUNT = "janus-ci@${project}.iam.gserviceaccount.com"
$env:ALLOW_DEV_PROVISION = "true"
& "C:\Program Files\Git\bin\bash.exe" scripts/gcp/provision-dev.sh
```

不要把 bootstrap 當成一般部署指令；若 runtime 已存在，只執行本次工作真正需要的最小操作。

## 3. Dev deployment

### 3.1 GitHub Actions 自動部署

`.github/workflows/deploy-dev.yml` 是 dev 的主要 deployment controller。

對 `main` 的 push 若修改到對應 runtime source、shared packages、`cloudbuild.yaml` 或 `scripts/gcp/**`，workflow 會以 path detection 自動判斷需要部署的 component：

- `ingestion-core`
- `intelligence-mart`
- `api`

純文件變更不觸發 application deployment。workflow 自身變更可以觸發 `detect` 驗證，但若沒有 runtime path 命中，deployment jobs 必須保持 skipped。

同一時間只允許一條 `deploy-dev-main` deployment chain 執行，既有 deployment 不因後續 push 被取消，以避免 runtime 落在不明中間狀態。

workflow 使用 GitHub OIDC／Workload Identity，最後呼叫 `scripts/gcp/deploy-dev.sh` 與 `scripts/gcp/verify-dev.sh`。使用前仍須確認 repository Variables／OAuth public client IDs 符合目前 workflow 定義。

`workflow_dispatch` 保留作為指定 component 的人工重跑／修復入口；一般 main code change 不需要人工按 deploy。

### 3.2 本機／受控執行入口

底層 deployment entrypoint 為：

```bash
bash scripts/gcp/deploy-dev.sh <component>
```

必須以目前腳本實際支援的 component 與 guard 為準，不從歷史 runbook 複製舊 substitution／resource 名稱。

API 需要候選驗收時，沿用目前 script 支援的 no-traffic／revision tag 流程；只有候選 health、public API、User／Admin、MCP／OAuth 等本次受影響路徑通過後，才切換 canonical traffic。不得因 image build 成功就宣稱 live acceptance 成功。

## 4. PostgreSQL migration

Migration 必須使用 repository 內版本化 SQL／migration tooling，不直接在正式資料表手改 schema。

若本機沒有 `psql`，可沿用 IAP 將已審核 migration 傳到 `janus-postgres-dev`，再在 PostgreSQL container 內執行；檔名與 database 必須依該 migration 的實際 contract 決定，不從舊範例猜測。

通用安全原則：

1. 先確認 migration 檔、dependency、target database 與 rollback／rebuild 路徑。
2. Secret／password 不放 argv、terminal output、Cloud Build substitution 或一般檔案；需要暫存時使用 ACL-restricted file 並確實清除。
3. 以 `ON_ERROR_STOP=1` 或等價 fail-closed 模式執行。
4. 完成後唯讀確認 migration marker、預期 schema／constraint／role，以及 service readiness。
5. 對真實資料有影響的 migration，SQL 成功不是完整驗收；還需要適用的 runtime／owner isolation／integration evidence。

版本化 dev migration 屬既有 dev 工程閉環，可在 rollback／rebuild 路徑明確時直接執行；若涉及大量不可逆資料刪除、無可靠復原路徑或新增付費資源，仍需人工授權。

## 5. Cloud Run Jobs

目前主要 Janus Jobs 包括 ingestion、intelligence mart 與 private pipeline；實際存在的 Job、image、env、Secret reference 與 Scheduler 必須在執行前唯讀確認。

部署既有 workflow 支援的 Job 時，優先走 `scripts/gcp/deploy-dev.sh`；部署後至少確認：

- Job `Ready=True`；
- runtime image 解析到預期 immutable digest；
- env／Secret refs 沒有意外漂移；
- 若本次 acceptance 要求 execution，使用既有 Job 執行一次 bounded run，並追蹤同一個 execution 到終態，不因等待過久重複觸發。

常用唯讀查詢：

```powershell
& $gcloud run jobs describe JOB_NAME `
  --region=$region --project=$project --format="yaml"

& $gcloud run jobs executions list `
  --job=JOB_NAME --region=$region --project=$project --limit=3

& $gcloud run jobs executions describe EXECUTION_NAME `
  --region=$region --project=$project --format="yaml(status)"
```

### 5.1 Dev 總控與資料清理

既有 Scheduler `janus-ingestion-daily` 每小時台北時間 `:30` 呼叫 Cloud Run Job `janus-batch-controller`。原 `janus-mart-daily`、`janus-private-pipeline-2130` 暫停保留供回復；自然排程與依賴、防重複驗收通過後才移除。三支資料工作 Job 保留，由總控呼叫。GitHub `iceberg-maintenance-dev.yml` 只保留手動 financials 維護入口。

總控規則在 `ingestion_core/batch_controller.py`：ingestion 每日 07:30、Mart 工作日 09:00 依賴 ingestion／data-supplement、private 工作日 21:30 依賴 ingestion；Mart 清理每日 23:30 依賴 ingestion，Core／Stage 清理依賴 Mart 清理。尚未執行的舊 occurrence 在 dispatch 前依目前契約更新 dependency，避免舊清理順序繼續生效。初期每小時輪詢，未到時間、依賴未成功或 Job 尚未結束時保留待辦，不等待或取消子 Job。PostgreSQL 總控 session lock 防止同時調度，持久化 occurrence 防止重複；不確定的 dispatch 必須人工核對 Cloud execution，不能自動重送。資料寫入／清理共用另一把資料鎖。事件先寫 PostgreSQL outbox，再冪等寫入 `ops.batch_events_v1`，讀回確認後才 acknowledge；Admin UI 查詢尚待串接。

完整清理先確認三支資料 Job 無 active execution。先執行 Mart `MART_OPERATION=retention,MART_RETENTION_MODE=dry-run,MART_AI_ENABLED=false`，核對計畫後改 `apply`；每股保留最新三代五分析師成果物，另暫時保護 queued／running／retrying execution，OOS 只留最新仍使用結果。依 Mart 保留索引、其他仍有效的 public artifact／publication 引用產生新鮮 Core reference fence，再對 ingestion 執行 `ICEBERG_MAINTENANCE_MODE=retention-dry-run`（`QUEUE_CONSUMER=false,MART_JOB=`），核對計畫後改 `retention-apply`。`CORE_RETENTION_FENCE_URI` 只能指向既有 dev Core `maintenance/retention-fences/` 下的一小時內清單，含 `created_at`、`core_snapshot_ids`；worker 另合併 active 作業引用。未提供清單時 Core execution manifest 保持受保護，回報 `reference_fence_required`；目前總控不自動產生此跨 bucket 清單。

Stage／quarantine 七日到期，不以是否已提交 Core 決定保留；active execution 及共用 raw 引用暫時保護。Mart 表保留 90 日、Core 一般行情 365 日、active Deep Coverage 行情與 benchmark 1096 日、財報每組 12 季；缺少資料不造假補齊。當前快照、最近 24 小時快照、最近 90 日每日最後快照與有效引用保護；孤兒檔與舊 metadata 至少七日且使用 generation precondition。報告保存在各 bucket `maintenance/retention/` 並讀回，另獨立盤點 live／全部版本／soft delete。使用者核准 Core／Stage／Mart／Private／research-big-move-500 的非當前版本 lifecycle 改為三日、關閉 soft delete；不立即刪除 live 檔案。research bucket 原本未啟用 versioning，三日規則只約束既有非當前版本，不新增版本副本。既有 soft-deleted 物件仍按刪除時期限到期；GCS lifecycle 非同步執行，live bytes 減少不等於當天計費 bytes 同幅減少。

總控 manifest 由 `scripts/gcp/prepare-batch-controller-dev.py` 依目前 ingestion immutable image、既有網路與 Secret refs 產生，預設 `observe`。更新 image 時須保留既有 `BATCH_CONTROLLER_MODE`、`BATCH_CONTROLLER_NOT_BEFORE`，不能直接套用預設 manifest 後忘記恢復 active。首次啟用先以 seed 採認當天原 Scheduler executions，驗證建立時間符合排程，設定有 timezone 的啟用時間後才 active。限定 IAM 清單見 `infra/gcp/dev-batch-controller-iam.json`；不得自行擴大至 production 或取消／刪除 execution。實際切換與清理證據見 operations ledger。

## 6. Secret rotation

目前 Janus runtime 採用整合後的 Secret bundle；實際 Secret 名稱、enabled versions 與 consumer references 必須先用目前 runtime／[`secret_list.md`](secret_list.md) 查證，不從歷史 split 文件推測。

Secret 值不得出現在 command argv、shell trace、process listing、Cloud Build substitution、deployment metadata 或 log。Windows 文字 pipeline 可能加入 BOM／CRLF，credential/session material 必須做 raw-byte 驗證。

安全切換順序：

1. 建立新 Secret version，保留上一個可用 version。
2. 驗證 raw bytes／格式，不輸出 payload 或 hash。
3. 讓候選 revision／Job 明確解析新 version 或依目前 bundle contract 取得新值。
4. 驗證 health、登入／DB／受影響功能與 ERROR logs。
5. 確認新 runtime ready 且實際承接預期 traffic／execution 後，才停用舊 version。
6. 失敗時回復上一個已驗證 runtime／version，不建立第二套臨時 secret path。

不要啟用 Artifact Analysis、Container Scanning 或 vulnerability occurrence API。

## 7. 驗收與紀錄

每次 deployment／migration／Job／Secret 變更，依本次工作只保存必要 evidence：

- Git commit SHA；
- Cloud Build／workflow run ID（若適用）；
- immutable image digest；
- Cloud Run revision 或 Job execution；
- UTC 驗收時間；
- targeted tests／acceptance 實際結果；
- partial／failed／blocked 項目；
- rollback／rebuild evidence（若本次風險需要）。

最新 evidence 摘要更新 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)；完成或被取代的 checkpoint 移入 `archive/`。README、SPEC 索引與本 runbook 不重複保存一次性 build 資訊。

## 8. 歷史資料

2026-09-23 Janus／omniAgent hard split、舊 Phase 5 deployment、舊 Agent Gateway／fixture、舊 Secret bundle 遷移等內容都是歷史 checkpoint，不再作為目前操作步驟。入口見 [`omniagent-split-status.md`](omniagent-split-status.md) 與 `archive/`。


## Owner-scoped Private Mart recalculation queue

Canonical design: `doc/decision-2026-10-07-owner-scoped-parallel-private-recalculation.md`.

- schema migration: `048_private_recalculation_queue`
- User API mutation/manual recalc only enqueue authenticated owner.
- normal scheduled `janus-private-pipeline` remains `taskCount=1`; job parallelism ceiling is 8.
- owner queue execution overrides `taskCount` from Admin setting `private_recalc_workers` (2–8, default 2).
- do not put owner UUID/symbols/trades into Cloud Run execution overrides.
- worker claims use PostgreSQL `FOR UPDATE SKIP LOCKED`; same owner has one active request.
- calculation may run concurrently, but shared Private Iceberg commit uses advisory lock `(1835102836,3)`.
- User-visible terminal failure must be persisted before the worker exits。QUEUED 在 dispatch active 但 5 分鐘無任何 worker claim 時轉為 `DISPATCH_TIMEOUT`；RUNNING/CANCEL_REQUESTED 超過 35 分鐘無 heartbeat 由 reaper 轉為 FAILED/CANCELLED；不得讓 UI indefinitely pending.
- Admin cancel is owner-scoped cooperative cancellation. Do not kill the whole shared execution for a single owner.
- Admin force-fail immediately writes a terminal FAILED state and User-visible safe reason; stale worker completion must not overwrite it.

Dev acceptance must verify migration 048, job default/task parallelism, API → job `roles/run.invoker`, one live owner request transition, duplicate-active suppression, and final Private Mart ledger-version catch-up.
