> **2026-10-24 政策更新**：研究數字與歷史結論保留；本文舊有逐來源／全歷史 PIT 補證、精確時間校準及新前瞻成熟等待不再是工作或發布前置。取消例行稽核，依 [研究精簡政策](../../doc/spec/research-simplification.md) 按需評估；不把取消視為 PASS。

# Janus／OmniForge Valuation PE／PB 研究補收 v1

狀態：**研究資料工程部分完成；publication_allowed=false**。本套只建立候選研究資料；不覆寫 `canonical/CURRENT.json`、不修改 Registry/Risk ACTIVE、不啟動模型訓練、GCP 部署或全市場補收。

## 位置與現行系統的關係

唯一白名單 Drive 根目錄：`/content/drive/MyDrive/給ai專用/janusChatGPT`。既有上游是 `資料源/JanusDataset_v3_202610/canonical/CURRENT.json`，其指向 `canonical/release-*/manifest.json` 與 Parquet。現行 00_資料收集_v3.8.4_個股.ipynb 實際**內嵌**七個採集模組；本補收是**獨立** research candidate writer，不覆寫該 Notebook、既有 stable collector，或大盤產業 00B。

請在 GitHub 版本化管理 `research/colab/valuation_backfill.py`、`research/colab/12_Valuation_PE_PB_研究補收_v1.ipynb`、本 README 及 `tests/test_valuation_backfill.py`；Notebook 只載入 Drive `janusChatGPT/CoLab程式/valuation_backfill.py`，並以預存 SHA256 拒絕版本漂移。不得使用第二套內嵌模組。GitHub main 實際 SHA 必須由最終同步人填入交付收據並讀回確認（尚未同步前請勿將此項標完成）。

## 最新 Drive 輸入證據（只讀）

2026-10-23 以 Google Drive 連接核對 `CURRENT.json` 指向 `release-0bbae8d9c1ca7d8d`；其 manifest `version=3.1.0`、`publication_allowed=false`，列 155 個參照檔、financials 1,181,442 列、revenue 92,910 列、valuation 78,730 列、ohlcv 799,468 列、corporate_actions 891 列。**這些是 manifest 宣稱值**，並非本輪逐檔 hash 與 Parquet row-count 真實讀回。指紋與狀態詳 `INPUT_REFERENCE_RECEIPT.json`；`CURRENT` 未被修改。

## 執行方法

打開 Notebook，逐格執行 1～6：固定套件、掛 Drive、驗 ROOT／模組 hash、設定 3 檔樣本、盤點及計算缺口。預設 `DRY_RUN=True` 和 `RUN_FETCH=False`；執行全部**不會發送來源請求**。

核對 `gap_plan.csv`、`request_plan.json` 的股票、期數、來源、預估請求數後，才將 `RUN_FETCH=True` 與 `DRY_RUN=False`；保守上限 `MAX_REQUESTS=3`、`MAX_SYMBOLS=3`、`MAX_RUNTIME_MINUTES=5`、`MAX_RETRIES=2`、`REQUEST_INTERVAL=1`。token 用 Colab Secrets 的 `FINMIND_TOKEN` 或環境變數，不寫入 repo 或明文報告。可事前僅做有界來源探測；未提供授權或實際測試收據，不宣稱 live 驗證。

CLI 用法（Colab 第 3 格需先完成 Drive mount 與文件同步）：

```bash
python valuation_backfill.py inventory --run-id valuation-research-v1
python valuation_backfill.py plan --run-id valuation-research-v1 --symbols 2330,2882,6488 --markets 2330=twse,2882=twse,6488=tpex --start 2025-01-01 --end 2026-09-30
python valuation_backfill.py fetch --run-id valuation-research-v1
# 僅在已核對請求計畫後才可明確執行以下有界請求；切勿用作全市場歷史補收
python valuation_backfill.py fetch --run-id valuation-research-v1 --run-fetch --no-dry-run --max-requests 3 --max-symbols 3 --max-runtime-minutes 5
python valuation_backfill.py normalize --run-id valuation-research-v1
python valuation_backfill.py derive --run-id valuation-research-v1
python valuation_backfill.py validate --run-id valuation-research-v1
python valuation_backfill.py report --run-id valuation-research-v1
```

## 中斷／續跑／修訂

固定相同 `RUN_ID` 及來源 plan 重跑；每個工作由 `source × dataset × market × symbol × period_range` stable SHA 組成 `task_id`。`complete.json` 與 `raw.json`、`rows.json` 的 SHA/row-count/key 必須讀回符合才認可成功；損壞者需人工隔離並新建 candidate run，**不能覆蓋不可變檔案**。`writer.lock` 即使過期也不自動搶鎖，確認舊 writer 確實停止、人工記錄後移除 stale lock。修改選股、資料截止、來源映射或 canonical 上游版本需開新 RUN_ID；當前版本對同 RUN_ID 重新產生不同計畫尚未提供原子防護，因此仍列**缺口**，不得視為多工 writer 完整驗收。

停止作業：用 Colab 中斷執行，下一次先執行 Drive、版本與 inventory/plan，再查狀態；請求上限正常記 `BUDGET_PAUSED`。若為網路突然中斷，`writer.lock` 可能殘留；請先人工查明再處理。沒有新增付費會員與全市場批次查詢。

## 分級、標準化與 PIT

`EXISTING_USABLE`=已有可用；`DERIVABLE`=原始科目有機會安全推導；`MAPPING_REQUIRED`=已有原值但單位／scope／口徑需證據；`FETCH_REQUIRED`=確實缺原始科目；`SOURCE_UNAVAILABLE`=沒有合法可用來源；`NOT_APPLICABLE`=公司／產業不適用。現行自動計畫實際只確定前三類及 FETCH_REQUIRED；**SOURCE_UNAVAILABLE/NOT_APPLICABLE 尚無依公司產業的自動分類證據**。

FinMind 官方文件已確認 `/api/v4/data` 和個股財報資料集 `TaiwanStockFinancialStatements`、`TaiwanStockBalanceSheet`、`TaiwanStockCashFlowsStatement`、`TaiwanStockMonthRevenue`、`TaiwanStockPER`。`date` 是期末，不是公告日。FinMind 的 raw 若未能證實 `statement_scope`、`period_basis`、幣別單位與修訂版本，一律保留 `UNKNOWN`，標 `MAPPING_REQUIRED`、`PIT_UNVERIFIED`，不因 HTTP 200 而變成可訓練資料。官方及第三方授權的保存／訓練／轉散條件未全面核實，列 `NOT_VERIFIED`。

所有原始值和標準化值保留；負淨利合法、非正分母不造數、EPS 不對累計值差分、存量科目不累加、未知 `published_at=null`、`fetched_at` 不冒充公告日。明確可稽核相容的 YTD 才能轉單季。`available_at` 不可早於最慢依賴值公布時間。參見 `valuation_factor_contract.json`。

## 輸出檔名

`inventory.csv`、`gap_plan.csv`、`request_plan.json`、`input_snapshot.json`、`collection_progress.csv`、`observations.parquet`（僅有有效 fetch 結果才產生）、`financial_mapping_audit.csv`、`factors.csv`、`factor_readiness.csv`、`coverage_by_market_period.csv`、`field_coverage.csv`、`source_conflicts.csv`、`quality_issues.csv`、`pit_status_summary.json`、`source_capabilities.json`、`candidate_manifest.json`、`fetch_receipt.json`、`執行摘要.md`。所有候選檔在 `模型研究/valuation/backfill_candidates/<RUN_ID>/`；既有 canonical 不改。

## 可用範圍／尚未完成

這是**安全的補收骨架與可稽核候選輸出**，不是完整 P1/P2 財務 mapping 產品。現階段只自動 derive 同範圍／幣別／單位已 VERIFIED 的 `debt_ratio`、`cash_to_assets`；TTM、ROE、長窗口營收與產業分類、金融專屬 mapping、衝突跨來源判定、資產平衡、完整覆蓋率聚合等尚未完整實作，factor readiness 必須保持 BLOCKED/NOT_VERIFIED。 `coverage_by_market_period.csv`、`field_coverage.csv` 是明確標記 NOT_VERIFIED 的占位報告，**不得當成真實覆蓋統計**。未做任何 live smoke；不能用 mock 測試替代 Colab/Drive/FinMind 真實讀回。

### 測試

`python -m pytest tests/test_valuation_backfill.py -q`。本地單元測試針對安全門檻、來源分類、checkpoint/hash、YTD、token、負數與預設停用網路；不覆蓋真實 Parquet/Colab 與授權驗收。最終是否通過，以實際收據為準。
