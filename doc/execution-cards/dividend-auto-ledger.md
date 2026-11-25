# 股利自動推算與一鍵入帳工程卡（DIV-01 ～ DIV-04）

更新：2026-11-25。依 [正式 SPEC](../spec/dividend-auto-ledger.md) 與 [PROJECT_RULES](../PROJECT_RULES.md)（§0.7）執行；唯一進度與驗收狀態在 [TODO](../todo.md)。本輪僅同步規格與工程卡（`DOC_ONLY`），未授權修改程式、未執行測試、migration 或部署。

## 順序與責任

| ID | 工作項目 | 前置依賴 | 驗收與退出條件（Definition of Done） | 回退方式 |
|---|---|---|---|---|
| **DIV-01** | Schema Migration 與 `private.pending_dividend_events` 建立；補齊 `corporate_actions.stock_dividend_ratio` 欄位與來源同步確認 | 無 | 唯一鍵 `UNIQUE (owner_id, canonical_symbol, ex_date, action_type)` 生效；Migration 可逆向降版 | 執行降版 Migration |
| **DIV-02** | 後端確定性推算引擎（`Decimal` 重播 $Q_{\text{ex}-1}$、現金／股票推算、二代健保／ETF／KY／彈性面額邏輯、防重複比對、盤後排程與補掃） | DIV-01 | [SPEC §6.2](../spec/dividend-auto-ledger.md#62-邊界案例驗收矩陣測試必要條件) TC-01～TC-08 邊界測試案例 100% 通過 | 關閉排程旗標 `DIVIDEND_AUTO_SCAN_ENABLED=false` |
| **DIV-03** | 5 支 Additive API 端點實作（含 `expected_ledger_version` 樂觀鎖、原子交易寫入 Ledger 與 `owner_id` 隔離） | DIV-02 | 跨 Owner 存取回傳 403/404；版本衝突回傳 409 且無部分寫入或髒資料 | 停用新路由或功能旗標 |
| **DIV-04** | Flutter 提示徽章、待確認股利清單、逐筆微調 Bottom Sheet、批次一鍵確認與歷史補掃 UI | DIV-03 | 390px／200% 字級無溢出；確認入帳後持股股數、平均成本與現金餘額即時同步 | 隱藏 UI 功能旗標，既有記帳零影響 |

## 開工指令（由使用者指定工項後使用）

```text
你是 Janus / OmniForge 工程師。請先讀取 GitHub repo `tommylin15/janus-omniforge`（main 分支）之 `AGENTS.md`、`doc/PROJECT_RULES.md`、`doc/README.md`、`doc/todo.md`、`doc/spec/dividend-auto-ledger.md` 與 `doc/execution-cards/dividend-auto-ledger.md`。

本次任務：執行【DIV-01 與 DIV-02】（建立 `private.pending_dividend_events` 與 `corporate_actions.stock_dividend_ratio` 之可逆向 Migration，並實作純 Python `Decimal` 確定性現金／股票股利推算引擎與 TC-01～TC-08 邊界測試）。
規則：
1. 先記錄目前 `main` 最新 SHA，核對現行 `corporate_actions`、交易帳本（Owner Ledger）與移動平均成本重播邏輯，重用既有模組不重造輪子。
2. 嚴格隔離公共市場資料（`corporate_actions`）與私人草稿（`private.pending_dividend_events`），嚴禁任何私人欄位流入公共快取或 `AIAnalysisInput`。
3. 零 LLM 呼叫、零浮點數運算（全面使用 `decimal.Decimal`）；不得未經使用者明確呼叫確認 API 即自動改寫或覆蓋真實交易帳本。
4. 配股率須直接採用權威 `stock_dividend_ratio`，不可寫死除以 10 元面額；已 `CONFIRMED` 紀錄絕不因補登舊交易而被排程改寫。
5. 未經實測與 Dev 部署驗證者一律誠實標註 `NOT_VERIFIED`，並依規範回報修改、測試證據與回退位置。
```

## 相關邊界

- 本功能採「逐筆／批次一鍵確認入帳」半自動流程，所有確認均須通過 `expected_ledger_version` 樂觀鎖與 Single DB Transaction。
- 未經實際測試、CI、Migration、Dev 部署與真實讀回驗證，一律維持 `DOC_ONLY`／`NOT_VERIFIED`，不得宣稱完成。
