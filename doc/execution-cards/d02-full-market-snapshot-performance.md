# D02｜全市場／首屏快照／效能 — AI 任務執行卡

更新：2026-10-16；v2 文件指示，非工程驗收。

> **本文件是獨立 AI 開發指令卡，不是第二份 TODO。** 唯一狀態、先後順序及執行授權以 [TODO](../todo.md) 為準；現況以 GitHub `main`、CI、實際 GCP dev runtime 為準。製卡不自動啟動工程／Job／部署／訓練／刪除。不得以歷史 archive 或舊 PASS 覆蓋最新結果。

**WBS 責任：**WBS 3／6

**相依與順序：**產品第2項；依 D01 報價及持股契約，資料支援 D03；經 D05 發布。

**執行宣告：**只在使用者明確授權本工作包、TODO 為可執行時，依下列程序完成「分析→修改→適用測試→commit→dev 發布→真實驗收／修復」的整個工作包，不因內部 checkpoint 自行停止；外部安全／授權 blocker 保持 BLOCKED 並記錄。

## 1. 最小必讀文件與工程入口

- [full-market-batch-policy.md](../spec/full-market-batch-policy.md)
- [holdings-first.md](../spec/holdings-first.md)
- [system-development-contract.md](../spec/system-development-contract.md)
- [batch-inventory-2026-10-13.md](../batch-inventory-2026-10-13.md)
- [wbs-3-ingestion-admin.md](../wbs/wbs-3-ingestion-admin.md)
- [wbs-6-api-and-apps.md](../wbs/wbs-6-api-and-apps.md)

**實作入口：**`jobs/ingestion-core/ingestion_core/__main__.py`、`full_market.py`、`batch_controller.py`；snapshot/serializer、`services/api/public_runtime.py` 與今日／持股 Flutter；migration057。

## 2. 開工前證據與前置條件

- 讀官方當日全上市櫃有效名冊／版本、各必要 dataset expected/valid/missing/not_applicable；舊日 1988 是歷史數字，不是固定分母。
- Bootstrap、同日 Cached、migration057 的既有成功證據不重跑；最新 snapshot 實際生成及 API 讀回仍未因 migration PASS 而成立。

## 3. 連續執行步驟與交付物

首頁增補恢復後依[AI路由](../codex-execution-plan.md)，[A第5節](../ui/visual-first-four-pages.md)定義長相，[D03卡](d03-four-page-charts-visual.md)負責UI；D02只處理共用快照／效能，不重做圖表公式。[三層交付](../ui/visual-first-delivery.md)共用驗收。


1. 打通所有上市櫃市場資料、screening、搜尋與新增關注、歷史研究入口；依資料集及期間分別判 TWSE 缺值率≤10%、TPEx≤30%（含邊界），50關注quota不變，缺值不補造。
2. 建立／核實真實快照 batch caller、057 初始補建、serializer、freshness、last-success、owner-scoped DB-first 快照；不可用舊 500 產物重標全市場。
3. 首屏從 PostgreSQL bounded read；消除 N+1、同步 Iceberg 掃描與無上限外部請求；owner/cache/quote 版本區隔，次要研究卡延遲載入。
4. 市場定時資料與盤中個人操作分離：持股保存、新股數成本／報價按需可更新，不等夜批。

5. 首頁摘要重用owner持股snapshot，異動重用持久化行情／財報／事件與既有批次，GET不掃全庫／呼叫LLM；只補現有serializer安全欄位，公共cache不得含owner資產。
6. 異動沿現有型別承載symbol、metric/event ID、period、value/comparison、source/as_of、reason及目標圖表；先查契約，不另建服務。穩定去重與排序，無異動／來源失敗分開。
7. 與D03共享數值證據；owner失敗不擋TAIEX，次圖不擋摘要。增補等TODO恢復，既有收尾不重開。

## 4. 驗收、禁止事項與失敗恢復

**專屬 acceptance：**
- 資料層測試分市場／期間／來源版本／缺值／stale／owner/cache，證實 batch→DB snapshot→API→auth UI 的真實 readback。
- 暖首屏 P95≤2秒、冷主資訊 P95≤5秒、暖試算≤500ms、保存至新股數成本可見≤2秒；各暖場景≥30筆，冷樣本不足明示，分記 P50/P95／timeout／失敗率／quote age。
- 前端完整載入與 backend API 分開量測，避免拿公開 API 暖延遲當 authenticated 手機冷啟動證據。

**禁止／安全 guard：**
- 不固定股票總數、不以當日有效名冊抹去歷史退場股；全市場容忍率不能拿來放行個別持股完整估值。
- 不以延長 timeout／緩存錯帳本版本作效能修復。

**失敗恢復：**快照產製失敗保留 last-success 並顯示 stale/partial；rebuild 需 migration/版本與 bounded 校驗；已存在 request 先核對終態後才決定是否重跑。

## 5. 統一執行協定與結案格式

1. 收到使用者明確「執行本卡」後，先讀 [AGENTS](../../AGENTS.md)、[PROJECT_RULES](../PROJECT_RULES.md)、[README](../README.md)、[TODO](../todo.md)、[status](../status.md)，再最小化讀本卡直接引用的 WBS／SPEC／UI、目前實作與適用 tests。若工作涉及四頁／記帳，另需實際檢視 Final Visual PNG。不可預載全 repository 或 archive。
2. 確認本次授權、最新 `main` SHA、現有工作區 diff（有工作區才檢）、live execution/版本與既有 evidence；不覆寫他人修改，不盲重送 unknown/terminal request。於授權 WBS 內一次完成相依 code→migration→tests→docs→受控 dev 發布→live acceptance→失敗修復，不在內部 dataset／頁面 checkpoint 反覆停等。
3. Commit 前用 `/ponytail-review`；不可用時採實際 diff／連結／契約／適用測試等價 review，並明示替代，不能冒稱執行。直接使用 `main`，不自建 branch/PR；遵守完整 SHA、GHCR immutable digest、共用部署鎖／lease、Job fence、Preview／回復 runbook。
4. **完成 gate**：依適用範圍逐一列 implementation、tests/CI、schema/migration、deployed SHA/digest、真實 request/workload terminal、業務／owner／data readback、failure／rollback。無證據維持 `NOT_VERIFIED`／`PARTIAL`／`BLOCKED`；僅提交或 build PASS 不算完整交付。部分不適用須說明。
5. 僅沿既有授權 dev 成本／IAM／備份；新付費資源、重大擴權、production 首建、大量不可逆資料刪除及不可回復破壞性操作須額外授權。MFA／OAuth consent 由本人完成。secret 不進 Git/log/UI；保留 owner isolation、PIT/provenance、來源使用授權、research/canonical 分離、LLM 不持有 canonical/publication 權限。
6. **固定交接報告**：工作包與輸入/輸出完整 SHA、已修改路徑、targeted test/CI run ID、migration、API/Job digest/Preview、live workload+業務 readback、PASS/PARTIAL/BLOCKED 明細、未知／依賴、失敗恢復及下一入口。最新證據更新既有 [operations](../spec/operations-and-testing.md)／[status](../status.md)，唯一 queue／狀態只回寫 TODO，不在卡片保存短期 runtime 快照。
