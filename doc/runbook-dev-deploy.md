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

不要把 bootstrap 當成一般部署指令；若 runtime 已存在，只執行本次 WBS 真正需要的最小操作。

## 3. Dev deployment

### 3.1 GitHub Actions

`.github/workflows/deploy-dev.yml` 目前是 `workflow_dispatch` 手動 workflow，且只在 `main` 執行；可選 component 為：

- `ingestion-core`
- `intelligence-mart`
- `api`

它使用 GitHub OIDC／Workload Identity，最後呼叫 `scripts/gcp/deploy-dev.sh` 與 `scripts/gcp/verify-dev.sh`。使用前先確認 repository Variables／OAuth public client IDs 仍符合目前 workflow 定義。

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

每次 deployment／migration／Job／Secret 變更，依本次 WBS 只保存必要 evidence：

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
