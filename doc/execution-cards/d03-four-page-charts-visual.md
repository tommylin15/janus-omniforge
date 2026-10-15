# D03｜四頁 UI／通用圖表／視覺收斂 — AI 任務執行卡

更新：2026-10-15；v1 文件指示，非工程驗收。

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

1. 今日只有一個個人相關變化 Hero，缺資料退化到可信市場／TAIEX；關注顯示最新合法股價/日期、變化及50額度，缺值項目不消失。
2. 持股以單一市值 Hero、同時間 checkpoint 的總損益與當日變化分列；個股先短價量，再價格折線/K線與可展開圖表入口，不讓 AI 區塊占先。
3. 逐一接上價格／量、官方營收、單季 EPS、PE/PB、法人、事件及允許的 Private Mart 歷史（VF-02～08）；每一類可讀真實資料，或列具體不適用／缺源，不用假點畫線。
4. 圖表期間、單位、gap、as-of/source 可見；只有一個點不能畫趨勢，分頁有界 loading/error/partial/stale，避免全屏無限 spinner。

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
