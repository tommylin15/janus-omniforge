# Janus｜接手 AI 的唯一工程路由

更新：2026-10-19。本檔只定義 **如何接手與跨元件協作**；**做什麼／何時做／哪些未完成**一律看 [唯一 TODO](todo.md)，不在這裡開第二份 queue。舊 D01～D06／DRL-01 操作命令完整存 [歷史指令](archive/codex-execution-plan-before-consolidation-2026-10-19.md)，不再向其他 AI 發出「恢復舊任務」指令。

## 1. 啟動與責任

依序讀 [AGENTS](../AGENTS.md) → [PROJECT_RULES](PROJECT_RULES.md) → [專案管理](project-management.md) → [status](status.md) → [TODO](todo.md) → **當次唯一任務卡**。其他 SPEC/UI/WBS 只在直接影響時讀；任何舊截面或 Drive 文件不得覆蓋目前 main／runtime。未有當次權限不能推進新付費 API、大幅 IAM 或破壞性操作。

| 現行工作包 | AI 必讀操作卡 | 必要契約／成果 |
|---|---|---|
| **STAGE-48H** | [Stage retention Runbook](runbook-batch-controller-dev.md) | 48h Stage TTL、每日 stage-only Controller、已證實合法引用、generation readback；後續 source 去重與 Admin GCS 唯讀盤點 |
| **D07-PRE** | [新研究採集契約](spec/research-collection-gas-drive-colab.md) | [D07 五角色任務卡](execution-cards/d07-specialist-b9-oos.md)、[資料治理](spec/data-governance.md)；先完成公開欄位可得性與缺值盤點、GAS 月檔／manifest／品質讀回，再做 Colab OOS |
| **D07** | [D07 五角色卡](execution-cards/d07-specialist-b9-oos.md) | [Specialist SPEC](spec/specialist-engines.md)、[WBS-5](wbs/wbs-5-specialist-engines.md)；Colab 模型 fit/OOS、Janus Registry／推論及各角色 Promotion Gate 獨立驗證 |
| **D08** | [D08 CEO 卡](execution-cards/d08-ceo-admin-owner-report.md) | [AI/Mart SPEC](spec/intelligence-and-governance.md)、[Admin UI](ui/admin.md)；Validated Fact Pack/Owner/報告 |
| **已結案 D01～D06／DRL-01／Admin v2** | [歷史任務卡索引](execution-cards/README.md)＋[結案](wbs/completed-index.md) | **不重啟**歷史 gate；若新缺陷實際影響正在開發的 D07/D08，按該工項修復 |

## 2. D07-PRE／D07：舊研究退役已結案，新研究路線分離

- **舊研究執行器退役已 CLOSED（2026-10-20）**：Controller `specialist-retrain`、手動舊 workflow/request、Mart fit、獨立研究 Job/Scheduler 與 B5～B8 中介 BQ 實體依原定範圍已完成程式退役、部署及實機查核；詳見 [結案收據](archive/d07-gcp-bq-retirement-live-2026-10-20.md)。不再分派清理工項，不為假設性未知資源新增追查。
- 新研究唯一輸入：[GAS 第三方 API → 私有 Drive 每月 ZIP → Colab 人工建模](spec/research-collection-gas-drive-colab.md)，普通股母體排除 ETF，TWSE／TPEx 各 dataset 最低 70%。先盤點現有公開欄位可得性與缺值，不用舊 Core frozen Parquet、BQ SQL 或完整歷史 PIT census 才能開始抓資料。研究時點欄位仍保留供後續標籤，正式 OOS/promotion 要防 future leakage。
- 五分析師 Quant／Risk 優先、Valuation/Fundamental 依欄位、Event 真人標註及來源權利未核准時保留 Rules。Colab 模型與確定性 baseline 同一 OOS、模型 version/hash、費用/安全/rollback；Janus Mart 不再訓練新模型。
- **保留正式服務**：Core/EOD／Screening、Private Owner、持股 ETF 行情、API、週 Iceberg 清理、Stage 48h 及備份。正式 Core 90%/70% 品質規範不被研究 70% 改掉。現役共用 BQ/Job 只有在確認其他服務不使用後才能刪。
- 已結案的舊研究僅保留必要 audit 收據；不得重新成為 D07-PRE／D07 的前置工作。**Colab 資料讀取驗收歸 D07-PRE；五角色模型 fit／OOS／promotion 歸 D07**，不得重複派工。

## 3. 最小工程閉環與合併驗收

一次指定工作包內：核對 `main` 最新 SHA／相同部署 lease／真實 runtime → 讀最少必要 code/schema/SPEC → 修改並補 tests → targeted tests/CI → 必要 migration、候選、0%/正式 dev、自然／手動 Job → Core/Mart/PG/API/Owner 資料／安全／UI readback → 若失敗修正或可逆 rollback → 保存完整 SHA、test/run ID、image digest、期限、來源與失敗原因於 [Operations](spec/operations-and-testing.md)，只在 [TODO](todo.md) 更動該工項狀態。**文件-only 僅可報 DOC_UPDATED**，無證據維持 PARTIAL/BLOCKED。

每日業務批次只走 [唯一 Controller](runbook-batch-controller-dev.md)；Cloud Scheduler、storage 保護／GCS generation／Owner 私有資料沿原治理。使用 GHCR Release → Cloud Run 候選 → 正式發佈/回滾，不因文件整理新增 scheduler、另一套 Core、model publisher、CI workflow 或免費額度未知的計費資源。

## 4. 本輪報告格式

每次回報列：`work_package`、`main/commit SHA`、變動檔案與安全界線、targeted tests／CI、deploy digest／migration、自然/手動 occurrence 和資料期間、canonical/Owner/模型品質 readback、實測 vs 缺失、rollback、`PASS/PARTIAL/NOT_VERIFIED/BLOCKED` 和下一個唯一入口。對被合併／豁免工作只能連到 archive，不用不同 WBS 重新排出第二張 TODO。
