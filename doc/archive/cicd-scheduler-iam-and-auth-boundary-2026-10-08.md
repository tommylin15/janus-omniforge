# 2026-10-08 Janus GHCR cutover：Scheduler IAM 與候選安全邊界實測

本紀錄只說明已觀測到的最小權限阻擋及不需認證憑證的 API 測試結果，不等於四元件 Release 完成。

## Scheduler WIF 唯讀權限：BLOCKED

證據：[GitHub Actions #37772721748](https://github.com/tommylin15/janus-omniforge/actions/runs/37772721748)、[身分確認 #37773290430](https://github.com/tommylin15/janus-omniforge/actions/runs/37773290430)。

- GH Actions WIF 已確認使用 `janus-ci@gen-lang-client-0593591102.iam.gserviceaccount.com`，非憑猜測。
- `gcloud projects describe` PASS，GCP WIF 可以讀到專案。
- `gcloud scheduler jobs list --location=us-central1`、單一已知 `janus-ingestion-daily` 的 `describe`、`scheduler locations list` 全部 **IAM_DENIED**。因此不能判斷排程內容、計時區或是否有其他 writer；不是零個排程。
- `gcloud projects get-iam-policy` **IAM_DENIED**。現有 ChatGPT GCP IAM connector 只提供 deny policies／custom roles API，沒有一般專案 allow IAM binding 寫入能力；此次未授權或嘗試高權限自我賦權。
- `gcloud services describe` 失敗標記 `UNKNOWN_COMMAND`，此檢查不能推論 Cloud Scheduler API 是啟用或關閉。需要另外確認 API 狀態。
- 建議的最小讀取權限：在 GCP 專案 `gen-lang-client-0593591102` 對上述 `janus-ci` 服務帳號授予 Google 預定義 `roles/cloudscheduler.viewer`；包含 `cloudscheduler.jobs.get`、`cloudscheduler.jobs.list`、`cloudscheduler.locations.*`。**不需要 Scheduler Admin／Owner**。
- 權限新增後，必須重新執行 GitHub Actions Scheduler diagnosis、Jobs preflight；全域清單與具名排程都應有實際 readback，才能允許後續 Jobs image 變更。

## 公開 GHCR 候選 API OAuth／MCP 負向驗收：PASS

證據：[GitHub Actions #37773049093](https://github.com/tommylin15/janus-omniforge/actions/runs/37773049093)。

- 既有服務 `janus-api` GHCR candidate tag `ghcr-0b93d99d42aa` 仍為 0% 正式流量，原本 `janus-api-g53d655ccb108-config` 為 100%。
- `/.well-known/oauth-protected-resource` 與 `/.well-known/oauth-authorization-server` 均 HTTP 200，必要欄位、S256 和 refresh-token grant metadata 契約 PASS。
- 六個未認證 API path：`/api/v1/me/profile`、`/api/v1/me/journal/positions`、`/api/v1/me/journal/pnl`、`/api/v1/me/portfolio/summary`、`/api/v1/me/portfolio/performance`、`/api/v1/admin/data-governance` 均回 HTTP 401。
- MCP `janus_private_context`（`positions`）未登入 tools/call 回 HTTP 401、Bearer WWW-Authenticate challenge 和 `isError=true`。
- 候選 Flutter build identity 對應已發布 GHCR Git SHA。
- **尚未通過：**真實 owner Google OAuth 登入、使用者 A／B 資料隔離、PnL 數字校驗、MCP 帶授權上下文讀取、refresh-token rotation。不得將 metadata/401 負向 PASS 說成完整 authenticated acceptance。

## 安全下一步

1. 對已確認的 `janus-ci` 添加僅 `roles/cloudscheduler.viewer`（使用者 GCP Console／具有 IAM 管理權的既有管理身分）。
2. 重跑 Scheduler readback，核對排程 enabled／paused、timezone、目標 Job、前次嘗試、重試與可設定的 fence。
3. 另用真實 allowlisted owner（或已授權驗收工具）完成 GHCR candidate OAuth／MCP／PnL E2E。
4. 全部條件 PASS 後才啟動 Jobs digest migration、rollback、Service promotion 與 10+protected Revisions 清理。舊 `janus-dev-v2` Trigger、AR、GCS 在完整 cutover 前都保留。

**本輪沒有變更 IAM policy、現役 Jobs、Scheduler、正式 Cloud Run 流量、AR、GCS 或資料庫／備份／應用資料。**
