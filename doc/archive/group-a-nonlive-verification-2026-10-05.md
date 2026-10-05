# A 組非 Live 驗證 checkpoint — 2026-10-05

用途：保存 A 組在不使用 authenticated browser／真實 UI 操作的前提下，已可由 GitHub `main`、tests 與既有 CI/deploy evidence 確認的結果。此文件**不是 A 組完成證明**，也不得取代 GCP dev 真實登入、真實資料、真實 UI、runtime readback 與效能驗收。

## 1. Ledger freshness / canonical consistency 靜態追查

### 1.1 operational position projection

- `infra/postgres/migrations/041_operational_position_projection.sql` 建立 `private.current_positions` 與 `private.refresh_current_positions`。
- trade ledger mutation path 會同步呼叫 current-position refresh；因此 operational positions 是交易異動後的同步 projection，不需等待 Private Mart 才能得到最新 shares／cost basis state。
- `tests/test_portfolio_api_completeness.py` 對 041 的 bounded rebuild 與 API synchronous refresh 保有 contract test。

### 1.2 Private Mart annual P&L / monthly summary

- `services/api/private_pipeline.py` 由 canonical trade ledger 重新計算 `mart_user_annual_pnl`、`mart_user_monthly_ledger_summary` 等 derived marts；輸出帶 `ledger_version` 與 `valuation_date`。
- annual bucket 在該年度存在交易時建立；BUY-only 年度的 realized P&L 可為 `0`，不需要捏造缺值。
- Private Pipeline 是 derived snapshot，不是 trade mutation request 內同步重算的第二套 canonical ledger。

### 1.3 serving freshness gate

- `services/api/store.py::PrivateIcebergStore.mart()` 已對 transaction-derived marts 與 valuation marts套用最新 operational ledger-version gate。
- `mart_user_annual_pnl`／`mart_user_monthly_ledger_summary` 若落後 current ledger version，serving 會 withholding 為空，不把舊 realized P&L 當成最新值。
- `mart_user_portfolio_summary` 若落後 current ledger version，serving 會回 `aggregate_status=withheld`／`valuation_status=partial`，保留 operational current cost basis，但不發布 stale market value／unrealized P&L。
- `tests/test_portfolio_api_completeness.py` 已覆蓋：stale annual P&L withholding、stale monthly summary withholding、stale valuation summary withheld、current snapshot unchanged。

### 1.4 Flutter read/refresh path

- Ledger/Journal page 同一次 load 會讀 trades、cashflows、portfolio summary、annual P&L、monthly summary 與 positions，並非三個 subview 各自維護完全獨立的 backend snapshot source。
- 既有 Flutter tests 已覆蓋 Journal refresh 重新讀取主要 Ledger endpoints 與 holdings refresh；因此「完全沒有 refresh 呼叫」不是目前 main 可支持的 root cause。
- UI 已辨識 portfolio `aggregate_status=withheld`，以「總額暫不發布」等 bounded 語意呈現，不用假 0 填補 valuation 缺值。
- annual P&L 若 serving 因 stale 而回空，目前 UI 會顯示缺值符號；是否需要進一步區分「本年度確定無 realized trade = 0」與「derived mart 尚待刷新 = pending」仍屬 A 組非 AI UX semantics 待收斂項目，不能只靠靜態追查宣稱完成。

## 2. Repo scheduler contract

`scripts/gcp/apply-private-pipeline-schedulers-dev.sh` 目前宣告 Asia/Taipei 平日排程：

- 07:40
- 11:00
- 14:00
- 21:30

這代表 repo contract 的 Private Pipeline 是 bounded batch refresh，不是每筆 trade mutation 後立即重跑完整 Private Mart。

**注意：**以上只代表 GitHub `main` 的 scheduler 設定；實際 GCP Scheduler 是否與 repo 一致、最近 execution receipt、failure/retry 與 freshness SLA，仍必須用 GCP dev runtime evidence 驗證。

## 3. CI / deploy evidence

### `2d8a7bf6c916f8901bb29779d48dfbe753a52420`

Workflow run `37305142870`：

- API targeted tests：146 passed。
- ingestion targeted tests：135 passed。
- ingestion deploy：success。
- migration 044 job：success。
- Private Pipeline deploy：success。
- API deploy：success。

### `5d37e5fb6c8bd05562e110a5538f673ed8ef2150`

Workflow run `37306165330`：

- API targeted tests：147 passed；包含 `tests/test_portfolio_api_completeness.py`。
- Private Pipeline deploy：success。
- API deploy：success。

以上 CI/deploy 成功只證明對應 commit 的自動測試與部署 job 成功，不等於 authenticated User App、owner isolation、資料 freshness、四頁 Final Visual Contract 或效能 live acceptance 成功。

## 4. 本輪可排除的錯誤假設

目前 GitHub `main` 不支持以下簡化判斷：

1. 「`/journal/pnl` 完全沒有 freshness gate」— 不正確；gate 位於共用 `PrivateIcebergStore.mart()`。
2. 「portfolio summary 會無條件把舊 Mart 當最新值」— 不正確；stale summary 會被轉成 withheld/partial。
3. 「Ledger 三個 subview 一定是各自獨立 provider，才造成資料不同步」— 目前 Flutter implementation 顯示主要資料由同一 Journal load path 聚合；若 live 畫面仍不同步，必須再用真實 request/state/runtime evidence 定位。
4. 「Private Pipeline 每筆交易後會立即重算 annual P&L」— 不正確；repo contract 為排程式 derived refresh，operational positions 才是同步 projection。

## 5. 仍未完成、不得由本 checkpoint 代替的 acceptance

- 真實 Google authenticated User／Admin browser path。
- owner isolation 的 live negative/positive readback。
- Today／Watchlist／Ledger／Stock Detail 在 390px 級真實畫面的 Final Visual Contract 比對。
- 真實交易新增／修改後，Holdings／Records／Reports／YTD realized P&L 的時間序列 refresh/invalidation readback。
- GCP Scheduler／Job 實際 schedule、recent execution receipt、failure/retry 與 Private Mart freshness readback。
- p95 warm core ≤ 2 秒、visited-page restore ≤ 300ms 的真實裝置／樣本效能證據。
- Admin 真實資料治理／effective jobs／容量與去識別化畫面驗收。

A 組在上述 live evidence 完成前維持 `partial`。
