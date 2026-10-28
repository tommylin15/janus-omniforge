# 個股頁圖資 v2：參考畫面盤點、做法與預計 UI（2026-10-28）

> 狀態：**規劃＋部分實作（partial）**。本文件依使用者提供之參考 App 截圖（國巨 2327）盤點，區分「現有資料可做」與「缺資料」。
> 參考截圖僅作版面參考，Janus 自有評分不保證與參考 App 數值一致。資料一律標註來源；缺值顯示「—」或「資料不足」，不補值、不推算。

## 1. 盤點總表

| # | 區塊（參考畫面） | 可行性 | 資料來源（現有） | 缺口 / 備註 |
|---|---|---|---|---|
| 1 | 報價列：價、漲跌、總量、量增/量縮 % | ✅ 可做 | stock-header、`ohlcv` | 量縮% = 今日量 ÷ 前 5 日均量 − 1 |
| 2 | 標籤：上市/上櫃、產業、可當沖 | ✅ 可做 | `stock_master`、`day_trading_suspension` | 有股期／有權證：缺（期交所/權證清單未收） |
| 3 | 日 / 週 / 月 K＋MA5/20/60/240＋成交量＋KD(9) | ✅ 已實作後端、前端元件 | `ohlcv` → `GET /public/stocks/{s}/price-series?period=day\|week\|month` | Tier 2 標的 Serving 僅保留 ~120 日 → 240MA、週/月 K 期數不足時顯示「資料不足」 |
| 4 | 技術1/技術2（MACD、RSI 等） | ✅ 可做 | 同上，前端計算 | 待排 |
| 5 | 月營收：單月柱＋股價線、MoM、YoY、累計 YoY | ✅ 前端元件已寫 | `visual-series?metric=revenue`＋月 K 收盤 | Serving 營收僅留 **24 個月** → 只能顯示 2 年；參考畫面 2022 起需放寬 retention |
| 6 | 累計月營收＋累計 YoY | ✅ 前端元件已寫 | 同上 | 年中缺月則累計顯示「—」 |
| 7 | 「本月營收創新高」橫幅 | ⚠️ 部分 | 同上 | 只能宣稱「近 24 個月新高」，不得寫「歷史新高」 |
| 8 | 年度走勢（年營收） | ❌ 缺資料 | — | 需 ≥ 3 年營收（放寬 retention 或讀 Core） |
| 9 | EPS 柱＋股價線、季本益比 | ✅ 前端元件已寫 | `visual-series?metric=eps`（12 季）＋季底收盤 | 本益比 = 季底收盤 ÷ 近四季 EPS；缺季不算 |
| 10 | 同業本益比 | ⚠️ 可做（需新聚合） | `valuation` 全市場 × `stock_master` 產業 | 以同產業 PE 中位數，需批次產出 publication |
| 11 | 收益比、本業佔比 | ⚠️ 部分 | FinMind `TaiwanStockFinancialStatements` | 需營業利益、稅前淨利欄位入 Core，尚未投影 |
| 12 | ROE / ROA（含近四季） | ❌ 缺資料 | — | 需資產負債表（股東權益、總資產），未收 |
| 13 | 基本概況：本益比、股價淨值比、殖利率 | ✅ 可做 | `valuation` | — |
| 14 | 預估本益比 | ❌ 缺資料 | — | 需法人預估 EPS（多為付費） |
| 15 | 基本資訊：股本、市值、掛牌年數、經營項目、個股焦點、細產業 | ❌ 缺資料（大多） | 產業分類 ✅ | 需 MOPS 公司基本資料 adapter（免費）；「個股焦點」「細產業」無官方來源 |
| 16 | 屬性雷達：長期存股 / 波段價值 / 短線價差 % | ⚠️ 可做（需定義） | `ohlcv`、`day_trading`、`valuation`、EPS | 見 §3，自有規則；百分位以全市場橫斷面計算 |
| 17 | 短線特徵表：20 日均當沖量、20 日均量、5 日漲幅、日振幅 | ✅ 可做 | `ohlcv`、`day_trading`（`day_trade_shares`） | — |
| 18 | 多空因素健診（符合 N 項） | ⚠️ 可做（需規則表） | 法人、融資券、借券、當沖、營收、估值 | 需規則清單版本化 |
| 19 | 法人買賣超 | ✅ 已有 | `institutional` | — |
| 20 | 大戶持股 %、偷偷賣股、籌碼分佈 | ❌ 缺資料 | — | TDCC 股權分散表（`tdcc` 已核准 fallback，**無 adapter**） |
| 21 | 主力買賣超 / 分點 / 主力熱門買超 | ❌ 缺資料 | — | 分點資料無免費穩定來源；啟用付費需授權 |
| 22 | 概念股（BBU、超級電容…） | ❌ 缺資料 | — | 需第三方（Yahoo 等）或自建分類 |
| 23 | 法說會 N 天後 | ❌ 缺資料 | — | MOPS 法說會公告 adapter（免費） |
| 24 | 法人目標價 | ❌ 缺資料 | — | 付費／第三方 |
| 25 | 除權息 | ⚠️ 部分 | `twse-events` | 需確認除權息欄位完整度 |
| 26 | 資券 | ✅ 已有 | `financing`、`securities_lending_short` | 前端尚未成圖 |
| 27 | 綜合評語（AI） | ⚠️ 可做 | specialist／四模型 | LLM 不決定數值 |

## 2. 做法

### 2.1 價格序列 API（已實作）
- `GET /api/v1/public/stocks/{symbol}/price-series?period=day|week|month&limit=2..300`
- 只讀 Serving `ohlcv`（最多 1500 筆日線），記憶體聚合：週＝週一起算、月＝當月 1 日起算；O＝首日開、H/L＝極值、C＝末日收、量＝加總（任一日缺量則該根量為 null）。
- `ma5/ma20/ma60/ma240` 以聚合後收盤計算，期數不足為 `null`。`adjusted=false`（未還原除權息）。
- 實作：`packages/web_api/core.py::CoreQueryService.price_series`；路由 `services/api/app.py`；測試 `tests/test_price_series.py`。

### 2.2 前端元件（已寫，**尚未接入個股頁**）
`apps/user_app/lib/final_stock_fundamentals.dart`
- `FvPeriodKChart`：K 線＋4 條均線＋量＋KD(9)；頂部 OHLC 與漲跌、均線數值列。
- `FvRevenueChart`：單月／累計切換；柱＝營收（億元）、線＝月底收盤；表格：月、今年、去年、YoY、MoM。
- `FvEpsChart`：單季 EPS 柱＋季底收盤線；表格：季度、EPS、近四季 EPS、本益比；腳註列出缺資料欄位。
- 月底收盤由 `price-series?period=month` 取得（`fvMonthlyCloseMap`）。

### 2.3 屬性評分（待做，自有規則 v1）
- 短線價差：20 日均當沖量、20 日均量、5 日漲幅、日振幅 → 各自全市場百分位，平均為分數。
- 波段價值：營收 YoY、EPS 年增、PE 相對產業、60 日動能。
- 長期存股：殖利率、EPS 穩定度（12 季標準差）、低波動、PB。
- 分數以批次產出 publication（每日 18:30 管線 A），API 只讀，不在請求時掃全市場。

## 3. 預計 UI（個股頁分頁）

```mermaid
flowchart LR
  H["報價列＋標籤"] --> T["分頁"]
  T --> K["K線：日/週/月切換、MA5/20/60/240、量、KD"]
  T --> R["營收：月營收/累計 切換、柱+股價線、MoM/YoY/累計YoY 表"]
  T --> E["財報：EPS 柱+股價線、季本益比表"]
  T --> B["基本資料：產業、本益比、PB、殖利率（缺資料欄位顯示 —）"]
  T --> P["屬性：三角雷達＋特徵表"]
  T --> C["籌碼：法人、資券（大戶待 TDCC）"]
```

- 配色沿用台股慣例：漲紅 `fvGain`、跌綠 `fvLoss`；均線 5 紫、20 橘、60 藍、240 粉紅。
- 每張圖下方標示來源、單位、是否還原、缺資料說明。
- 缺資料欄位不顯示假值；整欄缺時於腳註說明，不放空白欄。
