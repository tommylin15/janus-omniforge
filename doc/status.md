# Janus 目前狀態

更新：2026-10-24。**研究稽核精簡已 CLOSED／PASS（有界 Dev 驗收）**。已完成離線測試、GHCR Release、四個既有 Dev Jobs Rollout、API 100% 切流，以及一次獨立唯讀 Runtime 讀回。正式 API source：`cf69def50209ec590e464fcc7298ca4ece44bc6f`；Scheduler ENABLED，退役 `data-quality` 不在新版批次定義。

驗收：[完整 Release #40084702607](https://github.com/tommylin15/janus-omniforge/actions/runs/40084702607)／[Jobs #40085601337](https://github.com/tommylin15/janus-omniforge/actions/runs/40085601337)／[API #40087061995](https://github.com/tommylin15/janus-omniforge/actions/runs/40087061995)／[Runtime #40087520948](https://github.com/tommylin15/janus-omniforge/actions/runs/40087520948)。完整界限見 [結案 WI](runbook-research-simplification-wi.md)，不可冒稱真人登入、舊 pending DB 終態或備份復原已驗證。

下一步只依 [唯一 Active TODO](todo.md) 與 [WBS](wbs.md) 排序，分線執行：

- **P0：OPS-P0-1 已結案**：2026-10-24 Daily 40,587,735 bytes 由既有 Controller/VM executor 成功產生；[即時唯讀 #40095061967](https://github.com/tommylin15/janus-omniforge/actions/runs/40095061967) 及 [GCS 安全 dry-run #40095324398](https://github.com/tommylin15/janus-omniforge/actions/runs/40095324398) PASS：最新備份 4.25h、36h gate 通過、7 Daily/2 Monthly 受保護、刪除 0。之前獨立還原 PASS 沿用，不宣稱已對 10/24 新檔重新 restore。取消自然 GitHub 排程追查。
- **P1：RV-01～06、VAL-MIN30**：已建 [RV-01 現役 reader 清冊](research/valuation-rv01-serving-readers-2026-10-24.md)（靜態對應 PASS／真實代表股票覆蓋待驗）；已新增 `packages/valuation_range.py` 的 RV-02 估值分位與純函式，16 項 targeted tests [最新 CI #40096160077](https://github.com/tommylin15/janus-omniforge/actions/runs/40096160077) PASS。下一步真實樣本與 RV-03 reader 接線，再 RV-04 API/Mart、RV-05 單一 UI、RV-06 Dev 驗收；尚未部署 Valuation。VAL-MIN30 研究可獨立持續。
- **P1/P2：DATA-RELEASE-PREFLIGHT／FACTOR-FACTORY → D07 X/Y → Quant、Risk、Fundamental、Valuation 四模型研究**；Risk ACTIVE 不因精簡而自動啟用。
- **P3：D08**：沿用 Fact Pack 與 Gateway 做報告／Owner history／UI，可先開發，不等所有模型；共用模型快取待三模型可部署後處理。

已結案不重開：P0-2、C1-A、A-CHANGE、D01～D06、研究精簡。逐來源稽核、全歷史 PIT、週月模型稽核、長期自然觀察已 CANCELLED（不是 PASS）。C1-B 真實資料刪除未授權。

**備份結案界限**：最新 GCS generation/size 與保護計畫已驗收，歷史隔離還原 PASS；本次沒有對 10/24 新版執行逐 byte checksum/獨立 restore，不冒稱該項實測。A-CHANGE 使用者驗收為其獨立結案證據。完整證據索引：[Operations](spec/operations-and-testing.md)。
