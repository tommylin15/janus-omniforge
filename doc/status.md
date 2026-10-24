# Janus 目前狀態

更新：2026-10-24。**研究稽核精簡已 CLOSED／PASS（有界 Dev 驗收）**。已完成離線測試、GHCR Release、四個既有 Dev Jobs Rollout、API 100% 切流，以及一次獨立唯讀 Runtime 讀回。正式 API source：`cf69def50209ec590e464fcc7298ca4ece44bc6f`；Scheduler ENABLED，退役 `data-quality` 不在新版批次定義。

驗收：[完整 Release #40084702607](https://github.com/tommylin15/janus-omniforge/actions/runs/40084702607)／[Jobs #40085601337](https://github.com/tommylin15/janus-omniforge/actions/runs/40085601337)／[API #40087061995](https://github.com/tommylin15/janus-omniforge/actions/runs/40087061995)／[Runtime #40087520948](https://github.com/tommylin15/janus-omniforge/actions/runs/40087520948)。完整界限見 [結案 WI](runbook-research-simplification-wi.md)，不可冒稱真人登入、舊 pending DB 終態或備份復原已驗證。

下一步只依 [唯一 Active TODO](todo.md) 與 [WBS](wbs.md) 排序，分線執行：

- **P0：OPS-P0-1**：新備份真實可用與清理安全，有具體故障才修，不再開自然排程探針；保留 36h 刪除保護。
- **P1：RV-01～06、VAL-MIN30**：04 Valuation 的 EPS/BVPS/PE/PB 可重算參考區間、Mart/API/唯一 UI 卡；研究採現有資料加入 revenue_yoy 與五因子比較。
- **P1/P2：DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY → D07 X/Y → Quant、Risk、Fundamental、Valuation 四模型研究**；Risk ACTIVE 不因精簡而自動啟用。
- **P3：D08**：沿用 Fact Pack 與 Gateway 做報告／Owner history／UI，可先開發，不等所有模型；共用模型快取待三模型可部署後處理。

已結案不重開：P0-2、C1-A、A-CHANGE、D01～D06、研究精簡。逐來源稽核、全歷史 PIT、週月模型稽核、長期自然觀察已 CANCELLED（不是 PASS）。C1-B 真實資料刪除未授權。

**本次未核實的備份內容可復原**仍只屬 OPS-P0-1；A-CHANGE 的使用者驗收是其獨立結案證據。完整證據索引：[Operations](spec/operations-and-testing.md)。
