# GHCR 切換：既有 Scheduler Operator 授權與暫停／恢復 live drill（2026-10-08）

**Scope：只驗證現役 `janus-ingestion-daily` 的 IAM、短暫 PAUSED／ENABLED 與獨立恢復；不是 Cloud Run Jobs 或 Service cutover。**

## 本次取得的 runtime evidence

1. IAM 自訂角色已存在：`projects/gen-lang-client-0593591102/roles/janusWebSchedulerOperator`，僅授權 `cloudscheduler.jobs.get`、`jobs.pause`、`jobs.enable`、`jobs.update`；不包括新增／刪除／強制執行。使用者以 Cloud Shell 將此角色授予 GitHub WIF `janus-ci@gen-lang-client-0593591102.iam.gserviceaccount.com`。
2. [operator drill #37780249969](https://github.com/tommylin15/janus-omniforge/actions/runs/37780249969)：**workflow SUCCESS**。先做 contract/guard tests **26 PASS**，確認目標唯一 `janus-ingestion-daily`、config 與 `Asia/Taipei` 排程、距下一個 :30 tick 至少 15 分鐘、目前 controller 近期 execution 無正在執行，並以 GitHub lightweight ref `refs/tags/janus-ghcr-scheduler-drill-lease` 取得不覆寫鎖。實際執行 `pause` → readback **PAUSED** → 等待約 3 秒 → `resume` → readback **ENABLED**；完全沒有 execute Cloud Run Job、改 image 或改正式 Service traffic。
3. 同一 Actions 的 `independent-recovery` Job：**SUCCESS**，讀回沒有殘留 lease；不是曾經執行緊急 resume 的證據。CLI 清理 trap 與獨立 job 均已實作；另外有 [`.github/workflows/ghcr-scheduler-recover-dev.yml`](../../.github/workflows/ghcr-scheduler-recover-dev.yml) 可針對仍存續的 drill lease 執行外部補救，不會恢復無 lease 的刻意停用排程。
4. [獨立 live runtime 驗證 #37780525220](https://github.com/tommylin15/janus-omniforge/actions/runs/37780525220)：**SUCCESS**；`janus-ingestion-daily` 再次 **ENABLED**、`30 * * * *`、`Asia/Taipei`、Cloud Run `janus-batch-controller:run`、retryCount=1；四個退役的 private direct schedulers 仍不存在。該 workflow 在本輪沒有進行 Scheduler mutation。

## 完成與未完成邊界

- **完成：**WIF `pause`／`enable` 的最低操作權限、3 秒排程暫停／恢復 real readback、同 run 的獨立恢復 job 安全執行，以及獨立 readback 驗證。
- **尚未完成：**跨 GitHub Actions／舊 Cloud Build／GCP runtime 的 durable release mutex（此次 tag 僅防重入此 drill）、長時間 Job rollout 的失敗恢復與 rollback drill；`janus-private-pipeline` 9 筆歷史非終態 execution；新 GHCR 0% API candidate 的實際 owner OAuth／PnL／MCP canonical parity、四個 Jobs GHCR 實際部署／資料整合、Service 100% promotion／rollback、10+protected Revision 清理、Trigger／GCS／AR cleanup。
- **原配置保留：**所有原 Cloud Run Jobs image／service account／env／Secret refs、100% 舊 `janus-api` traffic、Cloud Build Trigger、AR pinned digests、GCS 業務／研究／備份與 PostgreSQL canonical data。此 drill 未建立付費資源，也未操作業務資料。

詳細實作：[`ghcr-scheduler-operator-drill.yml`](../../.github/workflows/ghcr-scheduler-operator-drill.yml)、[`ghcr-scheduler-recover-dev.yml`](../../.github/workflows/ghcr-scheduler-recover-dev.yml)，及 [Jobs dry-run](ghcr-jobs-image-rollback-plan-2026-10-08.md)。
