# 本次明確指令：新版 GitHub Actions → GHCR → Cloud Run 驗收（PARTIAL）

## 2026-10-09 當前執行清單（優先以本節判定）

使用者最新範圍：只驗收新版發布流程；舊 Revision／映像與 GCS／AR 清理不列待辦或結案條件。歷次清理預覽只保留為歷史事實，不再接續執行。

- [x] **Codex MCP 登入阻塞修復：**[完整 Release #37872497498](https://github.com/tommylin15/janus-omniforge/actions/runs/37872497498)、[0% candidate #37873561843](https://github.com/tommylin15/janus-omniforge/actions/runs/37873561843)、[兩個 MCP tag repair #37873731034](https://github.com/tommylin15/janus-omniforge/actions/runs/37873731034) SUCCESS；兩 tag 指向 GHCR 修正版 `janus-api-00449-dij`，canonical 流量不變。A 實際重登後 Private MCP 損益／持股 available；這不等於跨 owner／Jobs／100% promotion 整體結案。

- [x] **最新 GitHub CI：**[Selective CI #37861956147](https://github.com/tommylin15/janus-omniforge/actions/runs/37861956147) SUCCESS（被驗證 SHA `84eba9ad09a4090c1f91f3ff598554764e97fefc`）；[Jobs guard #37861956130](https://github.com/tommylin15/janus-omniforge/actions/runs/37861956130) **86 tests PASS**。
- [x] **9 筆 Private Pipeline 歷史 execution「可能仍在執行」的 blocker 已排除：**同輪 V1 list＋task list（包含 succeeded）＋Cloud Run v2 讀回一致，`Completed=CONDITION_FAILED`／`reconciling=false`／每筆 0 tasks，`historical_failed_pretask_terminal_count=9`、`historical_success_claimed=false`、diagnostics 空；仍保留失敗紀錄，**未取消／重送／刪除，絕不認作成功執行**。證據：[稽核 #37860818817](https://github.com/tommylin15/janus-omniforge/actions/runs/37860818817)、[最新 Jobs gate #37861956130](https://github.com/tommylin15/janus-omniforge/actions/runs/37861956130)。
- [x] **Jobs 切換唯讀保護維持生效：**`apply=false` 強制檢查，`change_count=4` image-only dry-run，live **exit 78 / BLOCKED**，`automatic_apply=false`、`resource_writes=0`；未改 Jobs、正式 traffic 或 Scheduler。
- [ ] **真實 owner authenticated acceptance：**在指定 GHCR 0% API candidate 完成 Google OAuth callback、MCP tool、PnL parity、Private API／跨 owner 隔離驗收，保留 sanitized live 證據；僅 OAuth metadata／未登入 401 PASS 不得代替。
- [ ] **Jobs 全域發布 mutex＋Scheduler fence：**先證明所有現役 writer（包含 legacy Cloud Build）不可競跑，再安全取得 lease、將唯一 `janus-ingestion-daily` 暫停並確認 `PAUSED`、同輪重新檢查所有 execution（含新到的）且具自動恢復／失敗回復；單獨 3 秒演練不算完成。
- [ ] **Jobs 完整 rollback 與 GHCR rollout：**完整 config／pinned digest snapshot、實際 rollback rehearsal、依 GHCR digest 更新四個目標 Job、canary／真實資料與 migration 安全驗收，最後恢復 Scheduler `ENABLED` 並讀回；Research Job 不改。
- [ ] **API 100% 切流／回滾：**上次已驗證現役 AR Revision 100%、GHCR 候選 0%；先通過 owner live acceptance，再完成固定 digest 正式流量／回滾 E2E 與來源 SHA 驗證，未完成前不得宣稱新 CI/CD 已全面接管。
- [ ] **發布入口安全：**只確認舊 writer 不與新版競跑；2026-10-09 本機唯讀 GCP readback：`janus-dev-v2` disabled=true、regional ongoing builds=0。完整 mutex／Jobs rollback 驗收仍未完成。

**實際剩餘四個 Jobs 阻塞：**`authenticated_acceptance_unverified`、`durable_deployment_mutex_unverified`、`rollback_procedure_unverified`、`scheduler_still_enabled`。請勿再將已釐清的 9 筆歷史失敗列為第五個阻塞。**整體 PARTIAL。**

## 歷次 CI/CD 實作與驗收紀錄（依發生時的快照，最新判定見上方）

- [x] GitHub Actions full Python／Flutter gate：[#37769572546](https://github.com/tommylin15/janus-omniforge/actions/runs/37769572546) **623 PASS／2 deselected**，另明確忽略五個 orphaned Web module tests。
- [x] 四個 Docker build／GHCR push／公開 anonymous pull／immutable digest：相同 workflow PASS，源 SHA `0b93d99d42aaff662a3408d749d70aa9d04b1042`。
- [x] GitHub Actions OIDC／WIF → Cloud Run API 固定 digest 0% 候選：[#37771247779](https://github.com/tommylin15/janus-omniforge/actions/runs/37771247779) PASS，`janus-api-00446-luq`，正式流量原版 100% 保持不變，僅 health／401 負向／Flutter identity gate。
- [x] Jobs 現役 images／最近執行／GHCR digests 唯讀盤點：[#37771560144](https://github.com/tommylin15/janus-omniforge/actions/runs/37771560144) PASS。
- [x] Scheduler viewer IAM＋`us-central1` 排程唯讀驗證：[#37774488086](https://github.com/tommylin15/janus-omniforge/actions/runs/37774488086)、[#37774702422](https://github.com/tommylin15/janus-omniforge/actions/runs/37774702422) PASS；唯一 `ENABLED` Scheduler `janus-ingestion-daily` 每小時 :30（Asia/Taipei）觸發 `janus-batch-controller`。
- [x] 修正 `private-schedulers` CI 對 10/02 已退役 private direct schedulers 的過時預期；用真實 controller topology 驗收 [#37776046528](https://github.com/tommylin15/janus-omniforge/actions/runs/37776046528) PASS；private direct 排程不重建。
- [x] 建立 GHCR Jobs fail-closed gate（19 個 guard＋private Scheduler 靜態 tests PASS）；[#37777330780](https://github.com/tommylin15/janus-omniforge/actions/runs/37777330780) 對真實 dev blocked 以 exit 78 顯示，`resource_writes=0`，五個原始 AR pinned digests 皆可讀回。
- [ ] Scheduler／Jobs 真正執行防護、跨 run durable mutex、rollback drill、snapshot、隔離 canary：Scheduler pause/resume IAM 與短時間可逆 drill 已 PASS（#37780249969、#37780525220），但不等於 Jobs rollout recovery。`janus-private-pipeline` 9 筆 9/18～9/24 舊未終態 executions 已由唯讀 #37787678921 全量重驗（92 筆掃描、9 筆逐一可讀、start/completion=null、runningCount=0、Completed=False、resource_writes=0）；當時只由 V1 無 completionTime 無法證明終態；2026-10-09 v2 正式 `CONDITION_FAILED` 和 Tasks 0 已更新為 terminal FAILED，見 #37861586747；始終沒有取消、略過或重送。
- [x] GitHub-only durable Git-ref deployment lease 原子搶鎖／owner fencing／解鎖／獨立恢復演練 [#37796079169](https://github.com/tommylin15/janus-omniforge/actions/runs/37796079169)：12 tests PASS、三個 live Jobs SUCCESS、最終 tag 不存在、無 GCP 修改。**這是 primitive／drill 完成，不是跨 legacy Cloud Build + Actions 所有 writer 的互斥完成**；需要與各入口整合、真實 workload snapshot／recovery／rollback readback，原上層 TODO 仍未完成。
- [x] `janus-api` GHCR 候選部署真正接入 Git-ref 原子 lease／鎖內 baseline、固定 digest 0% Candidate／readback／安全釋放：[Actions #37799529212](https://github.com/tommylin15/janus-omniforge/actions/runs/37799529212) SUCCESS；29 tests PASS，現役 `janus-api-g53d655ccb108-config` 仍 100%，candidate 0%，解鎖 readback 404；另外 `deploy-dev.yml` 與 GHCR candidate 共用 GitHub concurrency，[#37799911001](https://github.com/tommylin15/janus-omniforge/actions/runs/37799911001) 30 tests PASS。**不代表** Cloud Build 等其他 writer 已被互斥，也不代表 100% promotion／OAuth owner／Jobs rollout／rollback E2E 已完成。
- [x] 完整新 SHA GHCR 發布 [#37800085219](https://github.com/tommylin15/janus-omniforge/actions/runs/37800085219) Python 680 PASS／2 deselected、Flutter 70 PASS、四映像匿名 digest PASS；新 API GHCR 0% Revision `janus-api-00448-vir` [#37800990316](https://github.com/tommylin15/janus-omniforge/actions/runs/37800990316) PASS，同 SHA/cache digest 重試修復後 [#37803140112](https://github.com/tommylin15/janus-omniforge/actions/runs/37803140112) **32 tests、live no-traffic、global lease、安全釋放 PASS**；正式 100% 舊版未更動。
- [x] Scheduler 操作亦接入候選相同的 global Git ref，保留 owner-only／獨立復原防護；[真實 #37803931556](https://github.com/tommylin15/janus-omniforge/actions/runs/37803931556) 三個 Jobs PASS，3 秒 `PAUSED → ENABLED`、全域及本地 lock 都已清理，無新 Job execution、無映像改變。**尚未涵蓋 Cloud Build／所有部署 writer，不是 Job 長時間 rollout 或 rollback 完成。**
- [x] 用新 GHCR source SHA `8f6e7891…` 重跑五個 Job read-only cutover gate [#37804347835](https://github.com/tommylin15/janus-omniforge/actions/runs/37804347835)：guard-tests PASS，四個 image-only rollback mappings，五項 live blockers（Scheduler ENABLED、Private Pipeline 9 筆未終態、Jobs rollback 未驗收、Jobs 全域鎖未驗證、owner OAuth／資料 acceptance 未驗證），exit 78 **預期安全封鎖**、resource_writes=0。**Jobs 發布仍不得執行。**
- [x] Private Pipeline 9 筆歷史未終態 execution 額外 Task-level 唯讀稽核 [#37807381826](https://github.com/tommylin15/janus-omniforge/actions/runs/37807381826)：11 tests PASS、9/9 tasks list 完整可讀、每筆 **0 tasks／0 started／0 completed**，仍 `Completed=False`／無明確 terminal；未取消／重送／刪除。**當時僅有 V1 證據而維持 block；2026-10-09 以 V2＋tasks 同輪讀回已確認 terminal FAILED，見最新清單。**
- [x] Private Pipeline 9 筆 task inspection 追加成功 task 枚舉 `--succeeded` 復核 [#37807948695](https://github.com/tommylin15/janus-omniforge/actions/runs/37807948695) PASS；9 筆各為 0 tasks、0 started、0 completed，**當時 V1 無法證明 terminal**，不能自動處理；其後 v2 已證實 terminal FAILED，仍不能自動放行 Jobs。
- [x] GHCR API 0% 當前 request SHA `8f6e7891…` 重驗 OAuth metadata／私有 owner PnL、Positions、Admin 與 MCP 未登入 Bearer challenge [#37807741908](https://github.com/tommylin15/janus-omniforge/actions/runs/37807741908) PASS，2 tests；真實登入 owner OAuth／PnL parity／MCP tool 和 owner isolation 仍未驗收。
- [x] `janus-api` 413 Revisions 只讀最新 10 版保留預覽 [#37808487569](https://github.com/tommylin15/janus-omniforge/actions/runs/37808487569) PASS，12 tests；latest ten 10、traffic/tag/latest refs 19（tags 18）、**388 provisional unreferenced**，`revisions_to_delete_now=0`、`apply_authorized=false`。仍需正式驗收、完整互斥、已驗證上一成功版與 rollback digest、重新 live 盤點後才可執行實際 10 版 retention；不可視為已清理。
- [x] **9 筆 Private Pipeline 歷史 execution 已確定為 terminal FAILED，不是未終態／成功執行：**[Cloud Run v2 live #37860818817](https://github.com/tommylin15/janus-omniforge/actions/runs/37860818817) 28 tests、9/9 `Completed=CONDITION_FAILED`、`reconciling=false`、0 tasks、無 completionTime；未取消／刪除／重送。
- [x] **Jobs 歷史執行安全閘門已實際解除這一項誤判：**[GHCR Jobs #37861586747](https://github.com/tommylin15/janus-omniforge/actions/runs/37861586747) 85 guard-tests PASS（該次歷史驗收；最新 [#37861956130](https://github.com/tommylin15/janus-omniforge/actions/runs/37861956130) 86 PASS），V1 list＋tasks（含 succeeded）＋V2 同輪驗證 `historical_failed_pretask_terminal_count=9`、`historical_success_claimed=false`，`execution_janus-private-pipeline_unfenced` **不再是 blocker**。Live workflow 仍**故意 exit 78 / BLOCKED**，剩 4 項：Scheduler ENABLED、Jobs durable mutex、owner authenticated acceptance、實際 rollback；`resource_writes=0`，切換權限並未打開。
- [ ] 候選環境用真實授權 owner 執行 Google OAuth、PnL、MCP、Private API／資料隔離；沒有 token／授權證據不能以 401 替代。
- [ ] 四元件完整 Jobs config snapshot／Scheduler／active execution fence／GHCR digest update／canary／rollback，與 live E2E acceptance。
- [x] 新增 `ghcr_job_cutover_plan.py` 可逆 image-only 更新／回滾 dry-run：4 個 runtime Job pinned digest mapping、Research Job 不動；[28 tests PASS、live gate BLOCKED #37778770806](https://github.com/tommylin15/janus-omniforge/actions/runs/37778770806)。
- [x] 既有 `janusWebSchedulerOperator` 已由使用者綁定 `janus-ci`，實際暫停／恢復 3 秒及獨立 Job／後驗收 [#37780249969](https://github.com/tommylin15/janus-omniforge/actions/runs/37780249969)、[#37780525220](https://github.com/tommylin15/janus-omniforge/actions/runs/37780525220) PASS（含 26 guard tests）；未建立／刪除／執行 Scheduler 工作。
- [ ] Jobs 真正的長時間發布與可靠 recovery／cross-system durable mutex、GHCR candidate 真實 owner authenticated acceptance、controlled Scheduler PAUSED fence 與 rollback drill 仍待完成；歷史 9 筆已確認 terminal FAILED 且 execution fence 已消除假性 active blocker（#37861586747），仍不能把失敗等同資料成功；不要用短時間 Scheduler drill 冒充 rollout PASS。
- [ ] Service 新 revision 100% promotion、active service readback／rollback drill、上次成功 digest／mutex／idempotency 驗收。
- [ ] 發布鎖內重新確認 Janus 舊 Trigger 不會競跑；不以本次 disabled 快照取代發布時讀回。
- [ ] Cloud Build 的可選唯讀 status／failed-step 遮罩摘要不得觸發任何新 Build。
- [ ] 所有變更追溯同一 SHA／run／image digest／revision／acceptance；不碰 GCS／PostgreSQL 備份與 Iceberg、交易、筆記／其他應用資料。

詳細：[CI/CD 契約](spec/cicd-v2.md)、[GHCR live acceptance evidence](archive/cicd-ghcr-acceptance-2026-10-08.md)、[舊資產盤點](archive/cicd-cutover-cleanup-inventory-2026-10-08.md)。

# Janus — TODO

版本：3.22（2026-10-08：B7 ACTIVE，待 live acceptance；B8/B9 順序不變）
用途：**只保留確定要做的 active work 與未完成 acceptance**。Deferred、Candidate、Observation、Production-only、已接受缺口與研究構想統一放 [`parking-lot.md`](parking-lot.md)；已完成／被取代內容放 `archive/`。

## 規則

- 在本文件：**做**。必須有 implementation／acceptance，依下列順序執行。
- 不在本文件而在 `parking-lot.md`：目前**不做**，不得自行開工或計入未完成度。
- active work 可因外部核准或 runtime evidence 呈 `partial`／`blocked`；partial 不等於完成。
- 完成證據移至 `archive/` 或 `spec/operations-and-testing.md`，TODO 不保存歷史流水帳。

## 現行架構決策

### Token-first specialists + On-demand CEO

權威文件：

- [`decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md`](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)

目前產品契約：

- 五 specialist production 主路徑為 Python／SQL／ML，正常 path 不使用生成式 LLM。
- 約 500 檔在每個交易日 EOD canonical data ready 後做低成本 market screening／cross-sectional discovery；BigQuery 通過 fidelity gate 後優先承接這條全市場計算，不做 500×5 深度 specialist。
- 完整五 specialist 只做 `active watchlist ∪ effective holdings`，依 dirty dependency／input change 更新；無變更 reuse，不固定每日全重算。
- retraining／calibration／OOS evaluation／cache reconciliation 第一版固定 **每月第一個週六 10:30（Asia/Taipei）** 執行；不另設每週六 500×5 全量深算排程。
- plain-language output 由 structured output + SHAP／rules／templates 產生，正常 0 API token。
- Codex CLI／OpenRouter／Gemini 只用於 authorized manual On-demand CEO／approved rare escalation。
- CEO report immutable；重新分析建立新 execution/report，不覆寫舊報告。
- Admin 管 specialist model/evaluation、CEO provider/profile、DB-backed user capability、quota/cooldown、usage/cost/audit。

### Iceberg canonical + BigQuery analytics hybrid

權威文件：

- [`decision-2026-10-06-bigquery-analytics-over-iceberg.md`](decision-2026-10-06-bigquery-analytics-over-iceberg.md)
- [`spec/specialist-engines.md`](spec/specialist-engines.md)
- [`wbs/wbs-5-specialist-engines.md`](wbs/wbs-5-specialist-engines.md)

目前 B 組資料／運算契約：

- Core Iceberg V2／GCS 繼續是 canonical／PIT／provenance/history；BigQuery 不取代 canonical store。
- PostgreSQL serving projection 與 User／Admin request-time hot path 保持不變。
- BigQuery 只作 B 組 analytics compute；通過 cutover gate 後，優先承接 **每日盤後 liquid-500 screening**、cross-sectional features、OOS/evaluation 前處理與 ML training dataset preparation。
- 禁止 BigQuery Storage Read API；小結果走一般 query/result API，大型 training data 走 versioned GCS Parquet export artifact。
- 不預設複製整套 Core 到 BigQuery native storage；temporary/TTL derived data 可用但不可升格 canonical。
- 資料角色固定：Iceberg/GCS 保存 canonical/PIT/history；BigQuery intermediate 是可重建 compute；大型 training/evaluation dataset 以 versioned GCS Parquet 保存；model/evaluation/specialist 成果依 Mart contract 保存。BigQuery 中間結果不要求再回寫一份 Iceberg。
- 先抽出 exact-snapshot analytics reader，再做 BigQuery compatibility/canary；無法證明與固定 Core snapshot 一致時保留 PyIceberg path。
- 本架構方向已核准；若 implementation 需啟用新付費 API／建立 BigLake/Lakehouse/BigQuery 計費資源或擴大 IAM，仍需另有明確授權。

### Admin UI scope

權威文件：

- [`decision-2026-10-03-admin-ui-scope-and-governance.md`](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [`ui/admin.md`](ui/admin.md)

Admin operational convergence **不重做整個 Admin**。保留 `總覽 / 批次 / 個股 / 市場資訊 / AI 分析`，原 placeholder 收斂為 `資料治理`。第一版優先使用 Flutter Material，不導入第二套 metadata／orchestration control plane，也不要求大型 DAG／lineage graph／dashboard。

## 模型確認規則

- 每次只取下列順序中的一個可執行 WBS／工作組。
- 正式執行前依該項標示的【Sol】／【Luna】完成模型 gate；開始後以整體 acceptance scope 結案，不在內部 dataset／adapter／單一畫面反覆停等。
- 新付費 API／model／subscription、新付費 GCP 資源、重大權限擴張、不可逆大量刪除、MFA／OAuth consent／付款仍需使用者明確授權。

# 執行順序：A（CLOSED）→ B → C

依使用者 2026-10-05 指示，先完成上班族操作體驗／效能／Admin，再整合原 specialist 與 CEO 工作。執行細節與可貼給 Codex 的指令見 [Codex 執行指令](codex-execution-plan.md)。以下三組是唯一執行順序；後面的 1～8 是原 WBS acceptance 索引，不再代表先後順序，也不重複計工。

| 工作組 | 範圍與原待辦對應 | 主要模型 | 集中驗收 |
|---|---|---|---|
| A：操作體驗／效能／資料營運 | §6 Admin；§7 非 CEO 功能；§8 非 AI 相依版型；下列新增補強 | Sol | 一組 API／Flutter／資料營運回歸與一輪 dev browser/readback |
| B：specialist／增量快取／BigQuery analytics | §1 specialist + §2 rerun cache；BigQuery analytics hybrid；Admin 對應狀態接線 | Sol | 一組 reader/fidelity／引擎／cache 測試與 bounded dev 執行／reuse／OOS／FinOps readback |
| C：CEO／權限／最終整合 | §3 provider + §4 CEO + §5 Admin profile；§7 AI 整合；§8 剩餘驗收 | Sol | 一組端到端安全／UI 測試與最少已授權 provider live calls |

同組先完成相關程式、migration、UI、tests、文件再集中驗收，不逐檔／逐 API／逐股票獨立部署。失敗僅補跑受影響範圍；原 acceptance、必要安全檢查及真實 dev 證據保留。A 不因尚無 CEO 而延後基本 UI；§8 整體結案仍須所有條件成立。跨組連續執行須使用者明確指定全部組，依 PROJECT_RULES 的本次例外處理。

預警／推播／警訊 outcome 增補已移至 [Parking Lot](parking-lot.md) 與其獨立未來文件，不是本次 active scope；既有 Event specialist 與 OOS 照原契約。

## A 組結案

A 組 implementation／CI／dev runtime 與兩項人工 gate 已於 2026-10-06 全部驗收完成。完成證據已移至：

- [非佇列結案紀錄](archive/group-a-nonqueue-live-closure-2026-10-06.md)
- [latest-price／Ledger UI 驗收紀錄](archive/latest-price-ledger-ui-acceptance-2026-10-06.md)

A 組不再列 active TODO；下一個 active work 為 B 組。
## 2026-10-08 持股頁 UX／首屏加速（獨立於已結案 A 組及進行中的 B7）

- [ ] 「持股／紀錄／報表／筆記」固定頁首、四格只顯示持股、字體放大，台股漲紅跌綠。
- [ ] 官方昨收／當日每股漲跌／幅度與現持股價格變動有缺值、stale／日期與 owner-scoped guard；migration 050 真實驗收。
- [ ] 首屏不等待年度交易歷史、PnL、重算狀態；版本、報價日期與狀態一致；量測 API latency P50／P95。
- [ ] Flutter／Python targeted CI、dev deployment/migration、真實 User UI／Owner 一致性驗收。未通過維持 ACTIVE，不更動原 A 組 CLOSED 判定。

## B 組優先架構調整 acceptance

> **B0～B6 均已 CLOSED / PASS。** B5 [data path](archive/group-b-b5-ml-oos-data-closure-2026-10-08.md) 與 B6 [derived cache](archive/group-b-b6-ml-oos-cache-closure-2026-10-08.md) 各有獨立 live evidence。**恢復原訂 B7 → B8 → B9**：B7 月度 retrain/calibration/OOS/reconciliation 已啟動（未驗收完）；B8 再集中比較 BigQuery/PyIceberg 的效能／成本與 fallback；B9 模型品質及整體驗收。不重做 B4 cache，不因文件回寫把 B7 標為完成。

B 組開始五 specialist／cache 收斂前，先完成 [BigQuery analytics 架構決策](decision-2026-10-06-bigquery-analytics-over-iceberg.md) 的資料讀取邊界；此優先序不代表 BigQuery resource 已建立或啟用。

- [x] 抽出 exact-snapshot analytics reader；既有 PyIceberg path 先包成 reference／fallback，不改 canonical write path。完成證據見 [B1 reader](archive/group-b-b1-reader-acceptance-2026-10-07.md)。
- [x] 建立 BigQuery analytics adapter／compatibility probe，證明固定 Core snapshot 的資料／schema／null／時間／provenance fidelity。B2 CLOSED：沿用 20 contract tests、106 Mart regression、320-row fidelity；本次 shared catalog exact-snapshot mapping、native DECIMAL(20,4)/schema evolution、真實 ohlcv partition pruning 全 PASS，9 jobs 共 60 MiB billed bytes，immutable GCS evidence readback PASS。本輪無 IAM/canonical mutation，PyIceberg 仍為 default；workload canary/cutover 屬後續範圍。見 [B2 結案](archive/group-b-b2-closure-2026-10-07.md)。
- [x] B3 canary 禁止 Storage Read API 與 `bigquery.readsessions.*` 需求；未加入 `google-cloud-bigquery-storage`。大型 ML input 的 versioned GCS Parquet export 仍屬後續 training scope。
- [x] 建立每日盤後 liquid-500 screening：B3 已以真實 controller occurrence `market-screening/2026-10-07/16` 與 Mart execution `janus-intelligence-mart-7f8jl` 驗收；500 檔低成本 screening／cross-sectional ranking 完成，未擴成 500×5 深度 specialist。
- [x] B3 已加入 bounded query／column／partition guards 與 processed bytes／elapsed／peak RSS／artifact growth telemetry；未知 GCS I/O 維持 null，不補 0。
- [x] 同 fixed snapshot 已完成 PyIceberg／BigQuery deterministic canary compare；fidelity／budget PASS。未完成 default cutover gate，因此 **PyIceberg 維持 default**，不把 B3 PASS 誤寫成 BigQuery cutover。
- [x] B5 ML/OOS data path：shared catalog 的 bounded SQL reduction → BigQuery TEMP table → versioned immutable GCS Parquet，Mart live readback。驗收 [#37706568819](https://github.com/tommylin15/janus-omniforge/actions/runs/37706568819) SUCCESS；10,978 rows／499 symbols／533,945 bytes；首次 BigQuery billed 30 MiB，最終 immutable reuse billed 0；storage_read_api=false、CEO=false、LLM tokens=0。詳見 [B5 結案](archive/group-b-b5-ml-oos-data-closure-2026-10-08.md)。
- [x] B6：BigQuery-derived ML/OOS artifact dependency key／pre-query immutable verified reuse／selective invalidation／failure audit 已 CLOSED。CI #37708769385 137 PASS，live #37708769182 0 BigQuery jobs／billed 0、Mart readback PASS，來源異動 scenario 以 targeted tests 證實；見 [B6 結案](archive/group-b-b6-ml-oos-cache-closure-2026-10-08.md)。
- [ ] **B7 月度批次（ACTIVE；已推 main，等待 CI／dev runtime 與 artifact readback）**：將 `specialist-retrain`／calibration／OOS evaluation／cache reconciliation 的 effective schedule 統一為 **每月第一個週六 10:30（Asia/Taipei）**；實作時需修改實際 Scheduler／controller definition、協調依賴與工作流，並以 live runtime readback 驗證；文件本身不算完成。
- [ ] **B8 效能／成本／fallback 集中驗收（B7 後）**：B3 一次真實 canary 已記錄 PyIceberg 30.2256s / BigQuery hybrid 36.0608s（BigQuery 慢約 19.3%，valuation 部分未計入 BigQuery hybrid read）；B5 同 workload PyIceberg ML/OOS baseline 仍欠缺。於 B8 補相同 fixed snapshot、同 symbol/date/feature/output/PIT 的 PyIceberg vs BigQuery real-path，量測 cold/warm elapsed、RSS、BQ processed/billed bytes、GCS bytes（未知 null），並驗證安全 fallback 及 FinOps。不可拿 B5 SQL script 5.84s 與 B0/B1 完整 Mart 725.726/800.966s 直接比較；無證據不切換 BigQuery default。
- [ ] PostgreSQL serving projection 與 A 組既有 read path 不回歸；BigQuery failure 必須可 audit fallback，不影響 canonical ingestion/write。
- [ ] 若需啟用新付費 API、建立 BigLake/Lakehouse/BigQuery 資源或擴大 IAM，依 PROJECT_RULES 取得明確授權；未授權部分標 blocked，不以文件決策冒充 resource approval。

# 原 WBS acceptance（依上方工作組整合執行）

## 1. `WBS-5-MART-SPECIALIST-ENGINES` — 【Sol】

目前進度：`partial`。

先核對 [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 已記錄的公開資料清理 apply/readback 與最新 runtime；依 [`spec/retention-governance.md`](spec/retention-governance.md) 只補尚缺的整合／排程證據，不為舊待辦重跑已完成刪除。其他治理／成本收斂併 A；不以文件過期阻擋 B。

- [x] 約 500 檔**每日盤後**低成本 market screening 已由 B3 CLOSED；Deep Coverage universe／selective execution／no-change reuse 已由 B4 CLOSED。兩者未混成 500×5 全量深算。
- [ ] Fundamental：deterministic financial features + LightGBM baseline。
- [ ] Valuation：deterministic DCF／reverse-DCF／relative valuation + LightGBM／CatBoost benchmark。
- [ ] Quant：LightGBM baseline + Qlib DoubleEnsemble challenger；以 Taiwan PIT walk-forward OOS 決定 champion。
- [ ] Risk／Regime：Riskfolio-Lib + statsmodels／ML。
- [ ] Event／Catalyst：parser／rules + local multilingual Transformers classifier。
- [ ] 五 specialist 產出 structured artifact、SHAP／feature contribution、deterministic plain-language report；正常 path 0 LLM API token。
- [x] Deep Coverage 使用 `active watchlist ∪ effective holdings`；持股離開 500 仍保留，清倉且不在 watchlist 才退出。B4 live acceptance 已驗 5 symbols × 5 roles。
- [ ] 完成 PIT／provenance／missing-data／public-private isolation、tests、dev deployment、live execution、artifact persist/readback 與 OOS benchmark acceptance。

目前 500 檔缺失 ≤10% 為使用者接受範圍；超過先討論，不直接判整體失敗或自行擴張補資料。Mart 資源維持使用者指定 1 CPU／1 GiB；需要提高時先提出 evidence，不自行升級。

使用者最新核准：歷史財報有資料就做 OOS，不再要求原始數值版次／當時公開時間已證明。採最新官方數值版本、優先官方公開／上傳時間，缺少時明示期末後 90 天假設；正式模型作法及結果標示見 specialist SPEC。價格標籤成熟與來源／品質／隔離檢查保留。

## 2. `WBS-5-MART-RERUN-CACHE` — 【Sol】

- [x] 建立 dirty dependency graph：依 accepted/rejected PIT dependency state、feature/engine/model version 只 invalidate 受影響 symbol/specialist；B4 已有 regression + live evidence。
- [x] monthly revenue／financials、EOD price、event 依 specialist dependency mapping 選擇性 invalidation；event-only regression 已驗 1 computed / 4 reused。
- [x] 無 input change 直接 reuse，保留可稽核 cache identity；B4 live 第二輪 0 computed / 25 reused。
- [ ] 每月第一個週六 10:30（Asia/Taipei）執行 retrain／calibration／OOS evaluation／reconciliation，檢查 missed invalidation、orphan artifact、cache identity、model version。
- [ ] specialist change 只標記 CEO report freshness／material delta，**不得自動觸發 CEO LLM**。

## 3. `WBS-5-MART-AI-PROVIDERS` — 【Sol】

有效產品範圍只有 On-demand CEO／approved rare escalation provider runtime。

- [ ] 重用既有 Codex CLI／OpenRouter／Gemini adapter、routing、auth、free/billing gate、fallback/audit 能力。
- [ ] default approved route 為 `Codex CLI → OpenRouter → Gemini`；只有 approved／authorized／free-or-explicitly-approved-paid profile 可執行。
- [ ] 完成 manual CEO request 的 headless dispatch、cold-start auth／續期、timeout／cancel／retry、route snapshot/version/hash、attempt/fallback、usage/cost audit、zero-secret-leakage。
- [ ] 不新增未核准付費 provider／model／resource。

## 4. `WBS-5-MART-CIO-SYNTHESIS`（legacy tracking ID）— CEO Analysis — 【Sol】

產品名稱與語意一律使用 **CEO Analysis**；上述舊 ID 只為既有 WBS／artifact traceability 保留。

- [ ] CEO 只讀最新 validated specialist outputs／Fact Pack／provenance；不得計算或覆寫 canonical numbers，無 publication authority。
- [ ] 只由具 capability 的使用者明確 request；Scheduler、行情或 specialist dirty event 不自動觸發。
- [ ] 產出 thesis、cross-specialist conflict resolution、bull/base/bear、risks、invalidation conditions、unknowns；validator failure 保持 structured partial／blocked。
- [ ] 每次分析／重新分析建立新 immutable execution/report；保存 requester／trigger audit metadata。

## 5. `WBS-6-ADMIN-ANALYSIS-PROFILE` — 【Sol】

- [ ] 管 specialist champion／model／version／evaluation 與 CEO provider／model／profile；保留 immutable version history、rollback、audit、test symbols／compare。
- [ ] 加入 DB-backed Google user capability 管理，例如 `ceo_analysis.request`；backend enforce，Flutter visibility 不可代替 authorization。
- [ ] Admin 顯示 CEO provider approval／auth／health、model list、quota/cooldown、usage/cost；不得接收或顯示 raw token。
- [ ] `Codex CLI → OpenRouter → Gemini` 只適用 On-demand CEO／approved escalation。

## 6. Admin operational convergence — 已完成 A 組範圍

已移入 [A 組結案證據](archive/group-a-nonqueue-live-closure-2026-10-06.md)；B／C 的模型與 CEO 接線保留於其對應待辦。

## 7. User operational convergence — 【Sol／Luna】

- [ ] 【Sol】Stock Detail backend 增加 bounded CEO command/status/history API；驗證 authenticated user、`ceo_analysis.request` capability、symbol/profile、in-flight、quota/cooldown。
- [ ] 【Luna】Stock Detail 顯示五 specialist persisted plain-language outputs、最新 CEO report、analysis/data as-of、dirty/freshness/material-change、immutable history，以及有權限帳號的 `分析／重新分析`。

非 AI Journal／Watchlist／Stock Detail UX、typed formatter 與四頁 390px browser gate 已完成 A 組驗證；交易驗收交接見上文。

## 8. `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — 【Luna／Sol】

四頁非 AI presentation／PNG references／Flutter regression／authenticated dev browser 已完成 A 組驗證；本 WBS 整體仍保留 B／C 的 AI 整合驗收。

- [ ] Stock Detail persisted-first、manual CEO only、permission-aware、history immutable、freshness/material-change visible。
- [ ] specialist／CEO 接線後再驗四頁 AI-dependent state；不得把 A 組非 AI 結案當作此 WBS 全部完成。

## 完成證據

每個 TODO 至少需有與範圍相稱的 implementation、tests／CI、deployment、migration（如適用）、live runtime／integration acceptance。文件勾選、commit、build、upstream benchmark 或單次 bounded success 本身都不等於完成。

## 歷史／決策入口

- [2026-10-03 Token-first 五 specialist 與 On-demand CEO](decision-2026-10-03-token-first-specialist-and-on-demand-ceo.md)
- [2026-10-03 Admin UI 範圍與資料治理呈現](decision-2026-10-03-admin-ui-scope-and-governance.md)
- [WBS-3 補資料第一版完成（2026-10-03）](archive/wbs-3-data-supplement-v1-completed-2026-10-03.md)
- [2026-10-02 Admin／User／Routing／Provider 歷史決策](archive/decision-2026-10-02-admin-user-routing-and-provider-plan.md)
- [Parking Lot／暫不做](parking-lot.md)

其他已完成／被取代證據保留於 `archive/`；完整 runtime／deployment evidence 見 `spec/operations-and-testing.md`。
