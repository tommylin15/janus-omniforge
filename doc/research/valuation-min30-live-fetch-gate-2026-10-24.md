# Valuation 04｜FinMind 全量定向補收 GO／NO-GO 實機驗收

日期：2026-10-24（Asia/Taipei）。結論：**NO-GO — 不放大為全部排定請求**。這不否定 FinMind API 可用性，只停止低效的批次擴張；研究資料 `publication_allowed=false`。

## 本輪實際讀回來源

Drive 位於白名單 `janusChatGPT/模型研究/valuation/backfill_candidates/FINMIND_MIN30_REAL_20261024`：
- `official_master_readback.json`：TWSE 普通股候選1,086、TPEx894，**今日名冊，不等於歷史 PIT**。
- `frozen_plan.json`／`plan_tasks.csv`：共702個任務，700個 `TaiwanStockPER`、兩個股票1589的 `TaiwanStockFinancialStatements` 和 `TaiwanStockBalanceSheet`；`blocked_source_checks.csv` 另有312個PE/PB分支被排除。
- `receipts/` 及 `raw/` 各35個物件，實際有 FinMind 回應；`last_progress.json` 最後讀回本輪第10次HTTP、`SUCCESS`、`quota_paused=false`。本次讀回時根資料夾**尚未看到 `00_run_summary.json` 或完整 postfetch 覆蓋報告**。因可能尚有在途 Colab，不把此當作程式崩潰證明。
- 已抽取按計畫順序前10個 `TaiwanStockPER` 原始回應並重算：API 回應均有日資料，但與第20版 `NULL_MULTIPLE/MISSING_MONTH_ROW` 的 *原缺月集合* 逐月交集、取月內最後觀測並只認正PE/PB後，**新增研究候選的有效正倍數月數=0**。例如1101研究快照PE25/PB36、取得221行；1451研究快照PE23/PB36、取得262行，回應的PER皆為0。以上為局部抽樣，不推論所有702都無效。
- 致命規劃缺口：702個請求中估值最早 `start_date=2023-10-01`，**沒有一筆回補到研究release既有首月之前**。第20版短缺 CSV 所有1,018股票分支的 `may_need_pre_existing_history_before` 均是空字串；v21規劃器依這個欄位進行回溯，故設定 `MAX_LOOKBACK_MONTHS=60` 不會真正產生更早月份任務。

## 改正與放大條件

1. **來源校正優先而非全盲抓**：區分資料實缺（無來源回應、完整月份缺檔）、`PE` 會計負值/零/不適用、現有Parquet空值但FinMind回0、不同月末觀測日。這些不能當「重抓會變成正倍數」。
2. **回溯規劃器修正**：對目前不滿30個互異合法PE／PB月末、且IPO／歷史普通股適用日期與來源允許的候選，按月向2023-10前回溯必要的少數月份（受60月及來源可用日期上限）；既有有效月末避免重抓。不能用 forward-fill、IPO前或非正倍數灌出30。
3. **補收任務重排並重測**：先查可追回真實正值月末的股票，優先歷史PB與合法PE；財報等價讀回只有真正缺報表且與入選研究樣本相關才補。確認同一組檔有真正 `candidate_positive_months_added >0` 或已核實的 genuinely absent statement 季期，作新的有界試抓及 SHA /續跑驗證；仍缺 30者標 `PROBE/INSUFFICIENT_HISTORY`。
4. **執行保障**：不可對同一個現有 frozen_plan 在 Colab 在途時覆寫/同時寫入；修正後使用版本化新plan與輸出目錄保留原35份收據，按免費API額度分批，不一次在免費Colab中等待整個700單。

以上 NO-GO 是**目前v21凍結計畫**的批次擴大判斷，非永久禁止經修正的限定研究補收，亦非模型/發布認證。
