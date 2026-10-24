# D03｜四頁 UI／通用圖表／視覺收斂 — AI 任務執行卡

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](../spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-16；v2 文件指示，非工程驗收。

> **本文件是獨立 AI 開發指令卡，不是第二份 TODO。** 唯一狀態、先後順序及執行授權以 [TODO](../todo.md) 為準；現況以 GitHub `main`、CI、實際 GCP dev runtime 為準。製卡不自動啟動工程／Job／部署／訓練／刪除。不得以歷史 archive 或舊 PASS 覆蓋最新結果。

**WBS 責任：**WBS-6-USER-FINAL-VISUAL-CONVERGENCE（非 AI）

**相依與順序：**產品第3項，依 D01/D02；圖表和頁面合併交 D05；VF-09 留 D07。

**執行宣告：**只在使用者明確授權本工作包、TODO 為可執行時，依下列程序完成「分析→修改→適用測試→commit→dev 發布→真實驗收／修復」的整個工作包，不因內部 checkpoint 自行停止；外部安全／授權 blocker 保持 BLOCKED 並記錄。

## 1. 最小必讀文件與工程入口

- [user-app.md](../ui/user-app.md)
- [visual-first-four-pages.md](../ui/visual-first-four-pages.md)
- [visual-first-delivery.md](../ui/visual-first-delivery.md)
- [README.md](../ui/reference/user-app-final/README.md)
- [accessibility-and-release.md](../ui/accessibility-and-release.md)
- [system-development-contract.md](../spec/system-development-contract.md)

**實作入口：**`apps/user_app/lib/final_today_v2.dart`、`final_watchlist.dart`、`final_ledger.dart`、`final_stock_detail.dart`；visual series API 與 Core/serving/Mart。

## 2. 開工前證據與前置條件

- 實際檢視 `doc/ui/reference/user-app-final/` 的四張原始 PNG binary；新 visual-first 順序優先於舊圖中的 AI 區塊。
- 先建立 VF-00～08 的 source→Core→serving→API→UI coverage matrix，標註 source authorization、財報 available-at、事件時間、typed owner path。

## 3. 連續執行步驟與交付物

**範圍：**既有D03收尾按TODO；本次首頁／個股增補等DRL-01恢復後併入，不加重當前D05。AI總入口見[指令路由](../codex-execution-plan.md)，長相唯一依[A第5節](../ui/visual-first-four-pages.md)。

1. 讀A第5節手機／桌面逐區表格，列既有widget與差距；核對main/API，已有則重用。舊PNG作基線，最新文字順序優先，不自行另做版型。
2. 首頁接owner資產短摘要、三則可核對變化與TAIEX；去重，無異動／讀取失敗分開；CTA直達該股正確圖及期間。不建已讀／推播系統。
3. 個股做報價／持股、三行營運／估值／風險事實、單一主圖、各最多兩項支持／疑點；每句對應來源及數值，不造綜合分數，不等ML才顯事實。
4. VF-07/08與DRL-01A/B/C共用資料／公式／API；單點、短史先顯實際值，累計EPS明標，缺同比仍顯營收，不重抓第二套。
5. 既有筆記接「記下觀察」，使用者確認才保存；追蹤自動化／候選／模型後置，不擴首版。
6. 按A第5節尺寸、字級、響應式及狀態表實作；主圖一份、放大切圖重用快取、單卡慢不擋首屏；沿D02效能目標。
7. 共用source→API證據，再補手機／桌面UI、點擊路由、單卡錯誤、owner隔離；相依修改合併發布，不逐圖發版。

## 4. 驗收、禁止事項與失敗恢復

**專屬 acceptance：**
- Flutter targeted/widget/golden/screenshot regression，API source/PIT/owner/data cap，無 hard-code sample 價格／損益。
- 真實 authenticated dev 390×844 手機與 desktop 四頁截圖，對照四張 PNG 與最新資訊架構；驗 loading/empty/gap/stale/partial、文字放大、鍵盤與讀屏、觸控目標及顏色以外語意。
- 六類圖表逐類具來源／時點／正確性證據，不能「所有資料 unavailable」即宣稱整體視覺驗收。

**禁止／安全 guard：**
- 不將 PNG sample number 或 AI prose 當 canonical；不拿模擬截圖當 live acceptance。
- VF-10 高階估值視覺、VF-09 模型狀態不屬 D03 發布 gate，不加第六角色／通用 Chat。

**失敗恢復：**若圖表來源或正式 User 版面失敗，停在已驗證候選/Preview，必要時按 D05 回復；保留缺失與錯誤證據，不刪資料/權限 guard 求 PASS。

## 5. 統一執行協定與結案格式

1. 收到使用者明確「執行本卡」後，先讀 [AGENTS](../../AGENTS.md)、[PROJECT_RULES](../PROJECT_RULES.md)、[README](../README.md)、[TODO](../todo.md)、[status](../status.md)，再最小化讀本卡直接引用的 WBS／SPEC／UI、目前實作與適用 tests。若工作涉及四頁／記帳，另需實際檢視 Final Visual PNG。不可預載全 repository 或 archive。
2. 確認本次授權、最新 `main` SHA、現有工作區 diff（有工作區才檢）、live execution/版本與既有 evidence；不覆寫他人修改，不盲重送 unknown/terminal request。於授權 WBS 內一次完成相依 code→migration→tests→docs→受控 dev 發布→live acceptance→失敗修復，不在內部 dataset／頁面 checkpoint 反覆停等。
3. Commit 前用 `/ponytail-review`；不可用時採實際 diff／連結／契約／適用測試等價 review，並明示替代，不能冒稱執行。直接使用 `main`，不自建 branch/PR；遵守完整 SHA、GHCR immutable digest、共用部署鎖／lease、Job fence、Preview／回復 runbook。
4. **完成 gate**：依適用範圍逐一列 implementation、tests/CI、schema/migration、deployed SHA/digest、真實 request/workload terminal、業務／owner／data readback、failure／rollback。無證據維持 `NOT_VERIFIED`／`PARTIAL`／`BLOCKED`；僅提交或 build PASS 不算完整交付。部分不適用須說明。
5. 僅沿既有授權 dev 成本／IAM／備份；新付費資源、重大擴權、production 首建、大量不可逆資料刪除及不可回復破壞性操作須額外授權。MFA／OAuth consent 由本人完成。secret 不進 Git/log/UI；保留 owner isolation、PIT/provenance、來源使用授權、research/canonical 分離、LLM 不持有 canonical/publication 權限。
6. **固定交接報告**：工作包與輸入/輸出完整 SHA、已修改路徑、targeted test/CI run ID、migration、API/Job digest/Preview、live workload+業務 readback、PASS/PARTIAL/BLOCKED 明細、未知／依賴、失敗恢復及下一入口。最新證據更新既有 [operations](../spec/operations-and-testing.md)／[status](../status.md)，唯一 queue／狀態只回寫 TODO，不在卡片保存短期 runtime 快照。
