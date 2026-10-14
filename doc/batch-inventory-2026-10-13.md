# 批次、即時路徑及快照盤點

**2026-10-14 新 coverage 決策：**本清冊執行目標中的舊統一 10% 門檻改為「TWSE ≤10%、TPEx ≤30%」，均含邊界，仍分市場、資料集、期間固定分母驗證；歷史記錄及已失敗的 bootstrap 不追溯改寫。部署／批次暫停狀態不變。

**最新執行狀態：**使用者已恢復 P0-1 至 P1-2 合併開發；下方「只更新文件停止」為前次盤點邊界，不再是開發禁令。新版程式／migration 未通過整合驗收前維持 PARTIAL。

盤點：2026-10-13；本輪依使用者要求 **只更新文件後停止**。下列「目標」尚未實作／切換。以 [全市場與總控契約](spec/full-market-batch-policy.md) 為後續開發依據。

## 已查證範圍與實際狀態

- 本機 `.github/workflows` 共 117 份 workflow，GitHub API 查到同數且皆 `active`；**active 是可觸發，不表示正在執行**。只有兩份有 `schedule`：研究延伸、私人備份清理。逐份入口清冊見文末。
- 既有 project `gen-lang-client-0593591102`／`us-central1` Cloud Scheduler 唯一讀到 `janus-ingestion-daily`，`ENABLED`、`30 * * * *`、`Asia/Taipei`，目標 `janus-batch-controller:run`；本次讀到最近 attempt `2026-10-13T03:30:02Z`。已讀執行記錄不等於所有子批次業務成功。
- 該區有 6 支 Janus Cloud Run Jobs：controller、ingestion-core、intelligence-mart、private-pipeline、ceo-analysis、research-big-move-500。另有 4 支 `life-assistant-*`，屬其他產品，不納入修改範圍。
- 本機 controller registry 共 **10 類批次**；ingestion 有兩個日內時段，mobile-ledger 每小時可評估，實際是否執行取決於依賴／pending／互斥。不能把 10 類說成只跑 10 次。
- 研究延伸 Actions 最近一次 [38303884784](https://github.com/tommylin15/janus-omniforge/actions/runs/38303884784) 為 scheduled **FAILURE**（2026-10-12 UTC）；前兩次 sampled runs success。本次不讀 raw log，不推斷失敗根因。
- 備份清理最近一次 [38330719708](https://github.com/tommylin15/janus-omniforge/actions/runs/38330719708) scheduled **SUCCESS**；不能由清理成功反推備份產生或還原成功。
- 程式另設 `janus-ledger-backup.timer`：18:00 UTC＝翌日 02:00 台北，加最多 10 分鐘隨機延遲；**本次未登入 VM readback，因此啟用／成功狀態 UNKNOWN**。
- `us-central1` Cloud Build trigger 唯讀查詢未回傳項目；未查其他區域／global，不能宣稱所有舊 trigger 均不存在。legacy script／workflow 中仍有 Cloud Build 與直派 Job 路徑。
- 來源是工作區與 bounded live metadata。既有未提交程式修改不等於 GitHub／live 已採用；例如 controller EOD 的 TPEx 新增仍在工作區。

## 10 類總控工作：現況與收斂目標

時間皆為 Asia/Taipei；表列為程式 due slot，總控每小時 :30 喚醒可造成延遲，不保證該刻完成。

| 現有操作／Job | 現有時段、依賴及用途 | 收斂／新增目標 |
|---|---|---|
| ingestion／ingestion-core | 每日 07:30、14:30；上午完整收集、下午價格／TAIEX；目前 registry 未限平日 | 保留早間增量與交易日 EOD，兩者共享市場批次及水位；全上市櫃名冊／行情一次來源讀取、多資料集拆分。休市依交易日曆跳過不需更新項目 |
| data-supplement／ingestion-core | 每日 08:30，依 ingestion；補資料／增量 | 和 morning ingestion 以 dataset/date/source/input hash 去重；保留獨立可重跑 step，禁止同資料再全抓。補漏有上限、失敗原因與恢復游標 |
| mart／intelligence-mart | 週一至五 09:00，依上午 ingestion＋supplement；`MART_OPERATION=queue` | 以 Core-ready／dirty queue 決定，不把固定上午時段當唯一入口；需核對每個 queue processor 與正式產物，不將 generic queue 稱為五模型完成 |
| market-screening／intelligence-mart | 平日 16:30，依最新 ingestion＋supplement，與公開 ingestion／Mart 互斥 | 改全上市櫃分片；EOD snapshot ready 才算，重跑相同輸入 reuse。與深度模型分開，不把資料不足股默默移出分母 |
| specialist-retrain／intelligence-mart | 每月第一個週六 10:30，依 ingestion＋supplement，互斥 | 保留月度節奏與 no-new-data skip；資料母體全市場，逐角色成熟資料／OOS gate。研究仍在產品後，不新設全市場每日重訓 |
| data-quality／ingestion-core | 每週六 12:30，與公開 ingestion／Mart 互斥 | 每次 ingestion 已驗的 key／型別／來源不重複做全歷史掃描；週品質集中上市 coverage≤10%、上櫃≤30%、缺口、schema drift，bounded 補漏 |
| private／private-pipeline | 平日 21:30，依當日最近 ingestion | 改成 EOD-ready 估值＋異動 owner queue；晚間僅補償。與即時手動重算去重，不重複全 owner 全帳本掃描 |
| mobile-ledger／private-pipeline | 每小時 :30，僅 pending 才啟動；與 private 同 slot 去重 | 正常 User App 入帳同步投影；此路僅離線 queue 恢復。現 entrypoint drain 後會進入一般 pipeline，需拆明 operation，避免每次 drain 都重估所有 owner；MCP 維持唯讀 |
| mart-cleanup／intelligence-mart | 每日 23:30，依 ingestion，三 worker 互斥 | 保留先 Mart 再 Core 的 retention dependency；同一 maintenance window，先 inventory／reference fence 再 apply，沒有可刪除項就 skip |
| core-cleanup／ingestion-core | 每日 23:30，依 mart-cleanup，三 worker 互斥 | 保留相依串行，不合成同時清除；含 Stage/Core retention 與受控維護，遇未知執行不刪、不盲目重送 |

現有 hourly reconcile 會讓同 slot 的相依清理跨小時才被放行；mart 的 09:00 slot 最早由 09:30 tick 處理。**是否縮短總控間隔或增加完成後喚醒，依 dispatch-lag 實測決定；不能用多設直派 Scheduler 解決。**

## 總控外入口與處置

| 入口 | 查得現況 | 文件確定的處置 |
|---|---|---|
| 研究 prospective extension Actions cron | `30 11 * * 1-5` UTC＝平日 19:30 台北；固定 TWSE／500 歷史 request，有獨立 research concurrency | **移除 Actions schedule**；若仍需前瞻留存，遷入總控、明確期限與唯一水位，不重訓／不改舊 OOS。新研究改全市場；尚未切換，不能聲稱已停止 |
| private-ledger-backup-retention Actions cron | `0 19 * * *` UTC＝每日 03:00 台北；保留三份 daily dump | **唯一保留的 Actions 定時工作**；補最新備份 age／成功依賴，GitHub schedule 有延遲，不能以時鐘順序推定 backup 完成 |
| VM backup timer | 本機腳本 02:00 台北建 dump；live UNKNOWN | 備份產生由總控追蹤派送並沿用既有 VM 執行工具；先證明新路徑／還原／權限後停舊 timer，避免無備份窗口。新增權限需依規則處理 |
| API transaction／manual private recalc | API 可 enqueue 並直派 Private Job；另有 nightly private | 同步交易投影保留；非同步重算改共用 request／dispatcher／fence，立即喚醒，不等小時 tick；失敗有補償且不重複寫入 |
| API CEO request | capability／quota 下手動觸發 dedicated CEO Job | 後置報告階段保留；納入共同 execution registry，仍必須使用者主動要求，禁止 cron／page-load 自動 CEO |
| Admin collection／analysis request | API queue＋manual／push-triggered workflows | 單一 request、allowlist、版本與總控記錄；UI 顯示 queued/running/failed／缺失，不另藏定時器 |
| 週日 liquid-500 rotation | ingestion `__main__.py` 內部有週日／once 選 500 邏輯 | 移除 active 前 500 選股／換榜；改官方名冊每日有效版本。舊排名／版本保留歷史，不只是改 UI 標籤 |
| 一次性修復／驗收／migration／rollout workflows | 大量 push 指定 request 路徑或 workflow_dispatch；皆 active | 收斂為既有受控工具入口；已完成修復轉 archive／不可自動再觸發，必要診斷保留唯讀。不是把 117 份一口氣刪除；每份附用途／觸發／owner／退場判定 |
| apply-*-schedulers-dev.sh／legacy deploy | repo 留有直接 worker Scheduler／舊 build 命令 | 標明 retired 路徑並防止重建第二控制面；不把腳本存在誤認為 live schedule 已啟用 |

本次只更新文件，研究 workflow 的試改已還原。所有停用、合併、遷移均為後續工作，保留 runtime 現況供切換前 readback。

## 即時及快照最小調整

1. **交易與試算優先**：同 transaction 更新 ledger／positions／成本／該筆已實現；版本衝突及冪等保障不省略。不要等待 Cloud Run 或夜間 Private Mart 才顯示成交結果。
2. **報價快照**：沿用 PostgreSQL operational_last_quotes＋EOD serving，批量讀本人 symbols；60 秒 TTL／10 秒手動節流。過期仍顯示日期，provider 失敗不清空最後成功值。
3. **首頁／圖表快照**：Core commit 後一次生成 latest/recent projection，API bounded 查詢；禁止每次首屏開多條 Iceberg 掃描。股價來源與市場快照日各自可辨。
4. **私有報表快照**：owner、ledger version、valuation date、source snapshot 綁定並原子發布；dirty owner 合併重算、舊快照標 pending。不得跨 owner／版本共用私人 cache。
5. **分片與優先序**：全市場資料量增加時，限制每片 rows／bytes／時間，固定 input snapshot＋游標可續跑，不能 `LIMIT` 截掉後宣稱全部。互斥鎖與低優先清理／研究不得阻塞交易；沿既有資源，不自行升級費用。

## 全市場改動範圍（程式仍有待辦）

| 位置 | 本次查到的限制／需同步變更 |
|---|---|
| `liquid_500.py`／`postgres_control.py` | exactly 500、TWSE-only validation、前 500 排名／發布 |
| migration 032／039 與 dependent SQL | rank 1..500、market membership function 指向 liquid_500；需新 migration，舊版本不改寫 |
| ingestion `__main__.py` | `_market_universe` exact 500／TWSE-only、members_by_market、週日 rotation、coverage labels |
| `specialist_runtime.py`／`market_screening.py` | membership >500 拒絕、150,000 rows 上限需分片；不是簡單移除上限後一次載入全市場 |
| `services/api/repository.py` | 搜尋 JOIN liquid_500、watchlist 新增拒絕非500；50 quota 與500分頁／change-log另行區別保留 |
| API models／Flutter／Admin | in_market_500 相容退場、市場名冊／搜尋／全市場文案、缺失率／日期顯示、測試 fixtures |
| 舊 research workflows／requests | 固定 cohort_size=500、market=TWSE、歷史 cutoffs／hash；不能直接覆寫歷史，另建全市場新版本並交總控 |

## 完成門檻與尚未查證

盤點文件完成不等於 runtime 收斂完成。後續需同版本測試、migration、總控與 worker readback、所有定時入口唯一性、無雙重派送、關鍵快照新鮮度、全市場上市≤10%／上櫃≤30% coverage、交易／試算與首屏 P50/P95，最後才結案。

本次未逐一讀 117 份完整程式，也未讀 VM timer live、其他 project／region Scheduler、DB 所有 occurrence、每支 worker 原始 log 或歷史研究資料；清冊涵蓋 repo workflow 觸發面與既有 dev 主區 metadata，這些未知項不能標成已停用／已安全。上述缺口在正式切換前以最小唯讀查核補齊，不新增另一套自動巡檢服務。

## Workflow 逐份入口清冊

以下由本機 YAML 解析產生，GitHub API 本次均回 `active`。觸發型態只代表入口；`push` 仍受 paths／條件限制，不能推斷每次 push 都跑。CI／Release／手動維運不因本規則一律停用；每一業務入口均須回到同一總控權威。

| Workflow | 入口 | 後續歸類 |
|---|---|---|
| `analysis-product-ci.yml` | push, workflow_dispatch | CI／測試保留 |
| `analysis-product-runtime-dev.yml` | workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `api-serving-projection-acceptance-dev.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `b2-bigquery-job-permission.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-catalog-acl-probe.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-catalog-bootstrap.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-catalog-existence-diagnostic.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-catalog-restricted-location.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-cloudbuild-error-diagnostic.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-cloudbuild-metadata-preflight.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-core-fence-readback.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-gcs-evidence-preflight.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-iam-capability-preflight.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-iam-setpolicy-fast-gate.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-iceberg-metadata-summary.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-janus-ci-permissions.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-lakehouse-preflight.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-nonregister-live-acceptance.yml` | workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b2-permission-preflight.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b3-cloudbuild-metadata-probe.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b3-controller-recovery.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b3-live-acceptance.yml` | workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b3-metadata-diagnostic.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b5-live-acceptance.yml` | workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b7-derived-cache-freshness.yml` | workflow_dispatch, push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b7-monthly-runtime-readback.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b8-existing-identity-readback.yml` | workflow_dispatch, push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b8-matched-screening.yml` | workflow_dispatch, push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b8-ml-oos-equal-run.yml` | workflow_dispatch, push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b8-ml-oos-fallback-readback.yml` | workflow_dispatch, push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b8-ml-oos-readback.yml` | workflow_dispatch, push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `b9-event-label-protocol.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `b9-fundamental-data-quality.yml` | workflow_dispatch, push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `b9-specialist-oos-quality.yml` | workflow_dispatch, push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `b9-valuation-quality.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `bigquery-compatibility.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ceo-readonly-diagnostic.yml` | workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ceo-worker-dev.yml` | workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ci-v2.yml` | push, workflow_dispatch | CI／測試保留 |
| `cicd-cutover-inventory.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `deploy-dev.yml` | workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `flutter-user-app.yml` | push, pull_request | CI／測試保留 |
| `ghcr-api-forward-finalize-dev.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-api-forward-promote-dev.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-api-promote-dev.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-api-route-reconcile-dev.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-candidate-auth-boundary.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-candidate-dev.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-candidate-lease-contract.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-ceo-worker-build.yml` | workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-jobs-cutover-gate.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-jobs-forward-resume.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-jobs-preflight.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-jobs-readonly-preflight.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-jobs-rollout-dev.yml` | workflow_dispatch, push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-mcp-route-dev.yml` | workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-preview-publish-dev.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-private-pipeline-iam-grant.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-publish-dev.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-release-lease-drill.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-reversible-baseline-dev.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-revision-retention-preview.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-scheduler-diagnostic.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-scheduler-operator-drill.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-scheduler-recover-dev.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `ghcr-stale-executions-audit.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `holdings-p0-mart-fields.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `holdings-p0-mart-logs.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `holdings-p0-owner-diagnostic.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `holdings-p0-owner-live.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `holdings-p0-runtime-gate.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `holdings-tpex-acl-migration.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `holdings-tpex-live-source.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `iceberg-compaction-ci.yml` | push, workflow_dispatch | CI／測試保留 |
| `iceberg-maintenance-dev.yml` | workflow_dispatch, push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `inspect-dev-mart-execution.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `inspect-dev-runtime.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `mart-provider-routing.yml` | push, workflow_dispatch | CI／測試保留 |
| `mobile-ledger-drain-once.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `portfolio-completeness.yml` | push, workflow_dispatch | CI／測試保留 |
| `portfolio-live-acceptance.yml` | workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `portfolio-live-debug.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `portfolio-revaluation-green.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `postgres-iap-bootstrap.yml` | workflow_dispatch, push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `postgres-serving-migrations-dev.yml` | workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `private-ab-note-cleanup-once.yml` | push, workflow_dispatch | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `private-cleanup-forensics.yml` | push, workflow_dispatch | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `private-ledger-backup-retention.yml` | push, workflow_dispatch, schedule | 保留唯一 Actions schedule；核對備份新鮮度 |
| `private-recalc-diagnostic.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `private-recalc-live-acceptance.yml` | workflow_dispatch, push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `private-recalc-queue-state.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `probe-mops-source.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `provider-credential-probe.yml` | push | 一次性／診斷入口：核對退場，必要操作走共同fence |
| `publication-owner-credential-rotation-dev.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `research-cloud-cohort-500-diag.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-diagnose.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-emerging-feature-watch.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-exec-diagnostic.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-export-matched.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-export.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-independent-validation.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-independent.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-matched-export.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-matched.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-pre-outcome-screen.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-prospective-extend.yml` | push, schedule, workflow_dispatch | 移除 schedule；業務遷總控 |
| `research-cloud-cohort-500-prospective.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500-validation.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `research-cloud-cohort-500.yml` | push | 歷史研究入口；新全市場版本遷總控 |
| `run-dev-ingestion.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `run-dev-specialist-b0-baseline.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `run-dev-specialist-b4-acceptance.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `run-dev-specialist-retrain.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `serving-schema-migration-ci.yml` | push | CI／測試保留 |
| `serving-schema-migration-dev.yml` | workflow_call, workflow_dispatch, push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `visual-first-live-baseline.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
| `visual-first-preview-readback.yml` | push | Release／維運／業務入口：保留必要能力、禁止另設業務定時 |
