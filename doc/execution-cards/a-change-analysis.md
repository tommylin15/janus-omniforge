# A-CHANGE｜方案 A 變化判讀 — AI 執行卡
更新：2026-10-24。**本卡是已完成 A-CHANGE A1–A4 的歷史執行指示，不再代表尚待開工。** 完整 GHCR／dev 100%／獨立 API live PASS，使用者於 2026-10-24 回覆「核對完成」，按 [Operations](../spec/operations-and-testing.md) 記 USER_ACCEPTED／CLOSED；無額外已登入 OAuth 200 或截圖機器 artifact。新的 04 Valuation RV-01…06 是獨立工項，優先順序以 [TODO](../todo.md) 為準。

## 複製給 AI 的指令
> 執行 A-CHANGE 整包。先讀 AGENTS.md、doc/PROJECT_RULES.md、doc/todo.md、本卡及 doc/spec/change-analysis.md。依當前main讀現有程式，直接main、不建branch/PR。完成A1事實解讀→A2變化狀態→A3盤前盤後→A4首頁/個股集中驗收。基本事實不等模型validated；未驗證機率仍禁止。共用既有Core/Mart/PG/API與Controller，不新增服務、供應商、推播或日常LLM；不重開已結案工程。完成適用tests/CI、既有dev發佈、真實資料/API/UI驗收與失敗修復，再回寫唯一TODO及Operations。遇新付費/擴權/不可逆刪除才依PROJECT_RULES處理。

## 必讀與入口
[變化SPEC](../spec/change-analysis.md)、[四頁UI](../ui/visual-first-four-pages.md)、[User UI](../ui/user-app.md)、[參考圖契約](../ui/reference/user-app-final/README.md)、[WBS](../wbs.md)。
程式：jobs/intelligence-mart/intelligence_mart/specialists.py、market_screening.py、product_runtime.py；packages/analysis_product.py；apps/user_app/lib/final_stock_detail.dart、final_today_v2.dart；tests/test_analysis_product.py、test_specialist_engines.py及對應Flutter tests。先確認實際路由，不改未使用舊頁。

## 步驟與有界驗收
1. 讀main與live能力，列本卡已存在/需補的最小差異；A1先解除事實與模型gate混用，整合有效角色，不取第一角色冒充完整摘要。
2. 建結構化observation與版本化模板，若需schema依既有migration；保存前後狀態、截止與證據，缺資料不轉解除，重跑冪等。
3. 現有批次產出同源盤前/盤後view；價量與公告分別按cutoff，休市/晚到/修訂測試。GET只讀serving，公開結果共用、owner只篩清單。
4. 調整首頁和個股資訊層級；維持持股金額、單一主圖與來源下鑽；未驗證ML欄位不出現在一般文案。
5. targeted測試覆蓋數字/時點/狀態/冪等/owner/無模型仍有事實；集中CI/既有dev候選→readback→release，按runbook可回退；390px/桌面真實畫面與30秒理解驗收。
6. 原定範圍通過即結案，無異常不追加假設性檢查。若某來源缺失，驗證合法降級，不要求全市場全欄位100%才交付。

## 回報
完整SHA、檔案、targeted/CI與dev證據、代表symbol/cutoff/資料對值、UI結果、已知具體剩餘項；文件/實作/部署/資料/產品狀態分開。
