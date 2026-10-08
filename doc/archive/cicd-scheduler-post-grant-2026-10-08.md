# 2026-10-08 Cloud Scheduler Viewer 授權後實測與 GHCR Jobs 切換依賴

## 實際驗收來源

- [WIF IAM 重新驗證 #37774488086](https://github.com/tommylin15/janus-omniforge/actions/runs/37774488086)：SUCCESS，principal 為 `janus-ci@gen-lang-client-0593591102.iam.gserviceaccount.com`。Scheduler locations、jobs list 及具名 describe 全部 PASS，service usage 顯示 Scheduler API ENABLED。只讀取 IAM policy 仍 IAM_DENIED；此項不妨礙 Scheduler viewer。
- [Jobs／Scheduler／GHCR readback #37774702422](https://github.com/tommylin15/janus-omniforge/actions/runs/37774702422)：SUCCESS。固定四個 GHCR immutable digests 同 Git SHA `0b93d99d42aaff662a3408d749d70aa9d04b1042`，匿名檢查 PASS。五個既有 Janus Job 都保留 AR 固定 digest，最近各 20 筆 execution 的 `potentiallyActive=0`，**不是全歷史與所有實際活躍執行 fence**。GHCR Jobs 還未切換。
- `gcloud scheduler jobs list --location=us-central1` 的完整當下讀回：
  - `jobCount=1`，`fullRegionEnumeration=true`。
  - 唯一 Job `janus-ingestion-daily`：`ENABLED`、cron `30 * * * *`（Asia/Taipei **每小時第 30 分**；名稱含 daily 但不是每日一次）、`POST` `janus-batch-controller:run`。
  - OAuth runtime identity `janus-ingestion-scheduler@gen-lang-client-0593591102.iam.gserviceaccount.com`，retry count `1`。
  - `janus-private-pipeline-0740`、`-1100`、`-1400`、`-2130` **在此 region 完整 readback 中不存在**；舊 `.github/workflows/inspect-dev-runtime.yml` 的 `private-schedulers` 驗收項仍假設這四個排程存在。這是「先前規格／CI 假設 vs live runtime」差異，不能當 live 已部署功能。其他 region、其他專案不在本輪清單涵蓋範圍。

## 切換安全阻擋

1. 每小時 `:30` 的真實 batch controller 會啟動既有 Job，因此在修改其 image 前必須具體取得可驗證的排程暫停／恢復、active execution fence、mutex、原始 Job config／digest snapshot 與 rollback／readback 方案。現有 `roles/cloudscheduler.viewer` **不能變更／暫停排程**，不得用超權限跳過。可設計「不影響既有排程的隔離 canary」，但不得偽稱已切換。
2. 需要確定四個 private direct Scheduler 是刻意撤除／合併到 controller，或是尚未部署的待辦；不要為了讓舊 CI PASS 而未授權建立新排程。
3. 既有候選版 owner Google OAuth／MCP／PnL authenticated E2E、Job integration、Service 正式 promotion／rollback、Revisions 10+protected 和舊 Trigger／AR／GCS cleanup 仍待驗收。
4. 所有既有 backups／business data／GCS、Cloud Run Job 與 Scheduler 設定不變。本輪僅作唯讀 readback、GitHub 工作流程與文件更新。

## GitHub 與 Runtime 契約校正

以目前 `us-central1` Scheduler readback 為 runtime 權威；`inspect-dev-runtime.yml` 中的四個 private-schedulers assert 在排程不在該 region 時不能當作已通過驗收，也不能臆測排程存在。未取得資料先標記 UNKNOWN／PARTIAL。
