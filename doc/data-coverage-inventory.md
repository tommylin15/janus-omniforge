# Janus Data Coverage & Quality Inventory

> 目的：區分「API／resource 可查」與「來源、adapter、Core publication、PIT、DQ 與歷史深度實際可用」。
>
> 本表是 `WBS-3-DATASET-COVERAGE-INVENTORY` 的 active inventory。狀態以 GitHub `main` 與 Janus dev runtime evidence 為準；`janus_sources` 的 resource allowlist 只代表 contract 存在，不代表資料完整。

## 狀態定義

- **Implemented**：adapter、Core publication、PIT/provenance、DQ 與 live evidence 均符合目前用途。
- **Partial**：已有 live data，但 coverage、時間語意、欄位、DQ、歷史深度或 market scope 尚有缺口。
- **Missing**：contract／adapter 可能存在，但目前 live Core 沒有可用資料。
- **Unknown**：目前 evidence 不足，不能推測。

## 2026-09-25 live inventory

| dataset | market | primary source / adapter | Core live evidence | cadence / freshness | PIT timestamp | provenance | status | 目前主要缺口 |
|---|---|---|---|---|---|---|---|---|
| `ohlcv` | TWSE / TPEX | TWSE `STOCK_DAY`; TPEX daily quotes | 2330、1102、2327、4958 可讀；近期資料存在 | 日資料；抽樣最新落在 2026-09-14 | `trade_date` + `observed_at` | 有 | Partial | `change_percent` 目前為 null；歷史深度與全市場 freshness 尚未量化；TPEX live coverage 未完成抽查 |
| `valuation` | TWSE | TWSE `BWIBBU_d` | 2330、1102 有 PE/PB/殖利率近期資料 | 日資料；抽樣到 2026-09-17 | `observed_date` + `observed_at` | 有 | Partial | 尚未證明 TPEX/全市場 coverage、歷史深度與 missing-rate SLA |
| `institutional` | TWSE | TWSE `T86` | 2330、1102 有外資／投信／自營商資料 | 日資料；抽樣到 2026-09-17 | `trade_date` + `observed_at` | 有 | Partial | live `dealer` buy/sell/net 不符合算術一致性；舊資料需依修正後 normalizer bounded backfill |
| `financials` | TWSE listed + fallback | MOPS/TWSE OpenAPI `t187ap06_L_ci`; FinMind fallback | 2330、1102、2327、4958 有 Q2 2026 rows | 財報週期 | `published_at` / `observed_at` | 有 | Partial | `出表日期` 被當 publication time，live Q2 row 出現 `published_at=2026-09-25`、`observed_at=2026-03-31`；舊資料 EPS unit 錯；目前僅一般業損益表 endpoint，產業/statement coverage 不完整 |
| `events` | TWSE | TWSE/MOPS material information | 2330、1102 有近期事件 | 事件驅動 | `published_at` + `effective_date` | 有 | Partial | 歷史深度薄；`severity` 多為 null；尚未建立完整事件 DQ / classification coverage |
| `market-activity` | TWSE | TWSE `TWTB4U` 等 | 2330、1102 有當沖股數/金額 | 日資料；抽樣到 2026-09-17 | `trade_date` + `observed_at` | 有 | Partial | metric coverage 很窄；尚未量化全市場/歷史 completeness |
| `benchmark` | TWSE / TPEX | TAIEX history; TPEX index | `benchmark_id=TAIEX` 可讀，live Core 至少有 2026-09-14～2026-09-22 rows | 日資料；抽樣到 2026-09-22 | `trade_date` + `observed_at` | 有 | Partial | `return_percent` 目前為 null；TPEX benchmark、歷史深度與 freshness SLA 尚未完整驗證；MCP 的 `symbol` selector 對此 resource 實際代表 `benchmark_id`，易造成誤判 |

## 已確認的 correctness 問題

### P0 — Institutional dealer 欄位語意

TWSE `T86` 同時提供：

- `自營商買賣超股數`（總計）
- `自營商買進/賣出/買賣超股數(自行買賣)`
- `自營商買進/賣出/買賣超股數(避險)`

舊 normalizer 的 `dealer` 使用「自行買賣 buy/sell」搭配「總計 net」，因此可能產生 `buy - sell != net`。2026-09-25 已修改為：

`dealer_buy = self_buy + hedge_buy`

`dealer_sell = self_sell + hedge_sell`

`dealer_net = official_total_net`

並新增 regression test。舊 Core rows 仍需 bounded backfill 才會消除既有錯誤值。

### P0 — Financial PIT semantics

目前 MOPS/TWSE OpenAPI 的 `出表日期` 被寫入 `published_at`。Live canary 顯示 Q2 2026 財報資料在 2026-09-25 ingest 時被標成 2026-09-25 publication，而 `observed_at` 卻落在 2026-03-31；這不是可直接信任的 PIT publication chronology。

在取得可靠原始 filing publication timestamp 前：

- 不得把 API export/report date 偽裝成 filing publication time；
- historical backfill 不得推定資料在更早日期已可得；
- Mart 仍必須要求 financial evidence 有可稽核 availability timestamp。

### P0 — Financial units

舊 normalizer 將一般 MOPS row 的所有 metric 都標為 `TWD_thousands`，例如 `基本每股盈餘（元）= 2.13` 也被錯標。2026-09-25 已先修正 normalization：

- EPS / 每股金額 → `TWD_per_share`
- 明確 `%` metric → `percent`
- 上游若已提供 `unit` → 保留上游 unit
- FinMind 等無可靠 unit metadata 的 fallback → 不自動猜成 `TWD_thousands`
- 其他一般 MOPS 金額型 statement metric 暫維持現行 `TWD_thousands` contract，後續仍需逐 statement 對照官方欄位定義

舊 Core rows 仍需 bounded backfill。

### P1 — Benchmark selector 語意

`CoreContextReader.page()` 對一般 dataset 使用 `symbol` 欄位，但 `benchmark` 特例使用 `benchmark_id`。因此 `janus_market_context(symbol="2330", resource="benchmark")` 回 missing 並不能證明 benchmark Core 缺資料；使用 `symbol="TAIEX"` 可讀到 live benchmark rows。

這是 context contract 的可用性問題，不是 benchmark dataset missing。後續應讓 tool/schema 說明更清楚，並另外驗證 benchmark freshness / history / TPEX coverage。

## 執行優先序

1. 完成 institutional / financial unit 修正的 CI、dev deployment 與 live evidence；再安排 bounded backfill。
2. 釐清 financial filing availability/PIT contract，再處理 historical backfill。
3. 補 benchmark return / freshness / TPEX coverage 驗證，修正文案避免 selector 誤判。
4. 為 `valuation / institutional / financials / events / market-activity / benchmark` 建 dataset-specific DQ，不再只有 OHLCV 有強 DQ。
5. 建立可重跑 coverage audit：至少統計 symbol coverage、date range、row count、null rate、duplicate/quarantine、freshness、provenance、PIT violations。
6. Correctness 穩定後再擴 source 與大規模 backfill。

## 驗收原則

- 缺資料維持 `Missing/Partial`，不得用 API allowlist 或 adapter 存在取代 live evidence。
- backfill 前先修 semantics / unit / PIT，避免大量寫入錯資料。
- 每次修正需有 targeted tests；部署後需用 Janus dev live context / Core evidence 驗證。
- 新 source 若非官方來源，必須保留 source authorization / provenance 並與 canonical data 分流。
