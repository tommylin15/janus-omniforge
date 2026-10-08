# 2026-10-08 GHCR Jobs 上線保護與即時 WIF 驗收（PARTIAL / BLOCKED）

## 已完成：程式、回歸測試與 live readback

- 修正既有 `.github/workflows/inspect-dev-runtime.yml` 的 `private-schedulers` 驗收：以現行 `janus-ingestion-daily` → `janus-batch-controller:run`（`30 * * * *`、Asia/Taipei）為準，要求已退役的四個 private direct schedulers 不存在；raw scheduler json 暫存在 runner 的 `/tmp`，artifacts 僅包含 bounded safe fields。[真實 runtime #37776046528](https://github.com/tommylin15/janus-omniforge/actions/runs/37776046528) **SUCCESS**。
- `scripts/gcp/ghcr_job_cutover_guard.py` 是 pure fail-closed predicate；`tests/test_ghcr_job_cutover_guard.py` 測試完整輸入、負向案例、缺值、執行中狀態與無敏感欄位輸出。連同既有 `tests/test_private_pipeline_scheduler.py`，在 [GitHub Actions #37777055023](https://github.com/tommylin15/janus-omniforge/actions/runs/37777055023) 的 guard-tests **19 passed**。
- 新 `.github/workflows/ghcr-jobs-cutover-gate.yml` 採 GitHub Actions WIF、公開 GHCR digest、Cloud Scheduler、Cloud Run Jobs executions、既有 AR pinned image metadata **唯讀** readback。只有經 live API 確認既有原始 AR pinned digest 存在的 Job，才標記 `rollback_image_readable=true`；這**不是**實際 rollback rehearsal。
- [最新 guard #37777330780](https://github.com/tommylin15/janus-omniforge/actions/runs/37777330780) **特意以 exit 78 FAIL-CLOSED（BLOCKED）**，保護真實 parallel-live；`resource_writes=0`。五個 Job 的回滾 image digest 均可由 AR readback，因此最新 blockers 中已沒有任何 `rollback_..._unverified`。
- 同次完整 bounded executions 掃描：
  - `janus-batch-controller`：201 筆；200 有 completionTime，1 筆在讀取時沒有終態、runningCount 合計 0（可能是本小時 `:30` 剛觸發，需再次讀回，不宣稱歷史卡死）。
  - `janus-ingestion-core`：243 筆；243 有 completionTime，無 pending。
  - `janus-intelligence-mart`：216 筆；216 有 completionTime，無 pending。
  - `janus-private-pipeline`：91 筆；82 有 completionTime，9 筆沒有，runningCount 均為 0。
  - `janus-research-big-move-500`：24 筆；24 有 completionTime，無 pending。
- 9 筆 Private Pipeline 非終態 execution 在 2026-09-18～2026-09-24 建立；`startTime=null`、`completionTime=null`、`runningCount=0`、`Completed=False`，無 reason。這是歷史未啟動／沒有明確終態的異常，**不能當正在跑，也不能當已完成**；保留並阻擋更改，沒有取消／清理它們。明細僅在 #37777055023 中以非秘密狀態欄位唯讀檢查。

## 仍阻擋正式切換

1. 唯一的 `janus-ingestion-daily` scheduler 仍 `ENABLED`，每小時 `:30` 真實觸發 `janus-batch-controller`。viewer 不能 pause/resume。不得只憑在兩個 tick 中間修改 image，沒有可驗證的 Scheduler fence 不變更 Jobs。
2. Cloud Run Job 執行／狀態 fencing 必須重新讀回，包括 9 筆歷史未終態的原因與新的 controller tick；未知不視為 PASS。
3. GCP 與 GitHub release **跨 run durable mutex／last-success baseline／rollback drill** 尚無 PASS evidence；existing controller PostgreSQL advisory lock 只保護批次派送，不自動保護 Job image deployment。
4. 候選 API 的真實 owner OAuth／MCP／PnL E2E 尚未 PASS；現只有 OAuth metadata 和私有未授權 401 負向 PASS。

### 補充

- `ghcr-jobs-cutover-gate.yml` 在任何 BLOCKED 時主動 exit 78，**workflow failure 是正確保護行為，不是 GHCR image 建置失敗**。不做所有 live Job image update、execute、Scheduler pause、GCS／AR image delete、Cloud Build Trigger 停用、Service traffic promote。
- `roles/cloudscheduler.viewer` 已能 readback 所需資源；尚未要求／新增更高權限。
- 回滾 pinned AR image **目前可查得**；依舊不得在任何 Cloud Run Revisions／Jobs／Execution／rollback 引用仍存在時刪除它。
- 參考 [CI/CD spec](../spec/cicd-v2.md)、[Scheduler viewer readback](cicd-scheduler-post-grant-2026-10-08.md)。
