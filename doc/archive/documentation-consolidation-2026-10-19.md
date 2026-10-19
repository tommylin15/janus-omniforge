# 2026-10-19｜Janus 文件整理與治理稽核紀錄

狀態：**DOC_UPDATED / NOT_A_RUNTIME_ACCEPTANCE**。範圍只限 GitHub `tommylin15/janus-omniforge` `main`，未讀寫 Drive、未修改 GCP 資源、程式／schema／CI Job，也未執行 Colab。此份是**歷史稽核**；唯一 active 待辦在 [TODO](../todo.md)。

## 文件全面盤點

- 整理前從 GitHub recursive tree 實查 **251 個 doc files**（含大量原已封存檔案），按 `doc/` 根、`spec/`、`wbs/`、`ui/`、`execution-cards/`、`archive/` 分組。
- 截至本次中途 SHA `619b996ea141e6ea37a270e6a65ff55f96e13988`：**256 doc files；84 個位於現行區（其中部分為圖片）、172 個在 Archive**。本次新建了 project-management／原版快照等文件，所以總數可能增加，不以檔案數量下降代表整理品質。
- **搬入 Archive 的14份舊根文件**：`active-branch-d01-d04-advanced.md`、`batch-inventory-2026-10-13.md`、`data-supplement-s0-evidence.md`、`decision-2026-10-03-admin-ui-scope-and-governance.md`、`documentation-review-2026-10-13.md`、`documentation-review-2026-10-15.md`、`ceo-omniagent-p0v-integration.md`、`data-coverage-inventory.md`、`deployment-controller-consolidation-2026-09-26.md`、`janus-web-legacy-trigger-incident-2026-09-26.md`、`janus-web-root-acceptance-2026-09-26.md`、`omniagent-split-status.md`、`p0-holdings-recalc-pause-handoff-2026-10-13.md`、`admin-stocks-user-guide.md`。
- **原版完整快照新增**：`todo-before-consolidation-2026-10-19.md`、`status-before-consolidation-2026-10-19.md`、`codex-execution-plan-before-consolidation-2026-10-19.md`、`wbs-milestones-before-consolidation-2026-10-19.md`；原 CI／Owner／source／歷史失敗證據仍保存。
- **管理入口收斂**：[專案管理](../project-management.md)、[TODO](../todo.md)、[status](../status.md)、[AI 指令](../codex-execution-plan.md)、[里程碑](../wbs/milestones.md)，以及 PROJECT_RULES、SPEC/UI／Runbook 的最小相容更新。D01-D06、DRL-01/FINOPS-AB/Admin v2/背景補收不再佔 Active TODO；D07-PRE → D07 → D08 是唯一 active 新工程序列。這不改原已接受的範圍／功能或 historical PASS/FAIL。
- **明確保留現行**：Canonical/retention、Ingestion、Owner 控制、S/M/L WBS、PIT、模型／CEO SPEC、現行 Runbooks、事件標記契約、UI 基準圖、Pilot 長期收據、BigQuery 歷史 reader／fallback 決策、現有 Secret inventory（未因文件整理讀出 payload）。經使用者特別保留的 Deferred Market Alert 仍在 Parking Lot 與獨立構想文件。

## 新規格與實作差異

- Admin 六頁敘述已從 active overview/UI 索引移除，目標四頁；既有 Admin v2 完成範圍以最新 CI/runtime evidence 而非舊草圖判斷。
- Current-only snapshot 與週六維護以最新治理和 code/runtime 判定，Archive 內 10/13 的 daily23:30／reference fence 只是歷史；不因文件搬移修改 row retention。
- D07/PRE 原 FINOPS-C 與 Colab 資料/建模評估整併為一項任務；**Colab 唯一研究資料整理/fit/OOS**，BigQuery 只在大資料有實測效益時作資料前處理。現行 Mart fit **尚未遷移**，免費 Colab unattended 尚未證實。
- R1 Colab unattended、R2 24m Core coverage、R3 strict PIT、R4 external training-use、R5 FinOps 實刪成效是 [風險登錄](../project-management.md#4-重大風險及選項) 的決策項；文件更動**不等於使用者已批准付費／擴權／無界補抓**。

## 連結與品質核查

以 GitHub main recursive tree 作目標清單，逐批讀取 **79 份現行 Markdown**，檢查 Markdown 相對連結對應的檔案是否存在；歷史搬檔之受影響 active 引用已修訂。掃描發現既已退休的 `b7-derived-cache-freshness.yml` 指向不存在的 workflow 和 Parallel Live Runbook 指向舊 split path，已更正為歷史結案／Archive 路由。**這是文件內部 path existence 的靜態檢查，非 URL 爬取、anchor 逐段、所有既有 archive Markdown 連結的逐檔完整測試或 runtime 驗收**。Archive 原文是歷史證據；可能存在舊外部網址／已退役服務的時間點限定。

## 完成判定

文件治理／路由 `DOC_UPDATED`；沒有本輪重新執行 Cloud Run／Scheduler、B5訓練、Colab、BQ 費用、模型品質、業務 Owner API 等行為，不能宣稱已完成 D07-PRE／D07／D08 或全面 live 驗收。後續單一入口 [TODO](../todo.md)。
