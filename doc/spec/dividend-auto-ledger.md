# Janus / OmniForge｜股利自動推算與一鍵入帳規格書

> **日期**：2026-11-25（Asia/Taipei）｜**版本**：`v1.0`  
> **狀態**：`DOC_ONLY`（已同步規格至 GitHub，程式未實作、未測試、未部署；`NOT_VERIFIED`）  
> **Drive 來源**：`janusChatGPT/06_股利自動推算與一鍵入帳規格書.md`（`v1.0`）  
> **治理與執行入口**：[PROJECT_RULES](../PROJECT_RULES.md)（§0.7） → [WBS](../wbs.md) → [唯一 TODO](../todo.md) → [執行卡](../execution-cards/dividend-auto-ledger.md)；相關契約見 [持股優先契約](holdings-first.md)、[API + AI 個股分析重構規格](ai-stock-analysis-v2.md)、[User App UI 契約](../ui/user-app.md)  
> **決策依據**：使用者 2026-11-25 明確拍板——
> 1. 同時支援 **「現金股利 + 股票股利」** 自動推算與入帳。
> 2. 採用 **「逐筆／批次一鍵確認入帳」** 半自動流程（系統產生待確認草稿，經使用者核對或微調扣項後寫入真實帳本，不零確認自動改寫帳本）。

---

## 1. 目標、範圍與架構紅線

### 1.1 產品目標
解決使用者目前必須人工查詢除權息資料、手算配息金額／配股股數與逐筆手動補登交易的痛點，提供：
* **每日自動推算**：盤後依最新公司行動與使用者歷史持股，自動產生待確認股利草稿。
* **歷史漏記補掃**：支援手動觸發掃描歷史持有期間漏記的現金股利與股票股利。
* **逐筆微調與批次確認**：可在核對銀行實際匯入明細（匯費、二代健保補充保費、畸零股差異）後，單筆或批次一鍵寫入真實交易帳本（Owner Ledger）。

### 1.2 專案架構紅線（對齊 `AGENTS.md`、`doc/PROJECT_RULES.md` 與 [API + AI 個股分析重構規格](ai-stock-analysis-v2.md)）
1. **公共市場資料與私人帳本嚴格隔離**：
   * 除權息基準資料（`corporate_actions`）屬於公共市場層，全系統共用且不含任何私人資訊。
   * 持股重播、待確認股利草稿（`private.pending_dividend_events`）與正式交易紀錄嚴格歸屬 `private.*`（依 `owner_id` 隔離），**嚴禁**流入公共快取或 `AIAnalysisInput`。
2. **純後端確定性計算（零 LLM 呼叫）**：
   * 所有基準股數、股利毛額、扣項試算、配股股數與成本攤提**必須在後端以高精度十進位（`Decimal`）確定性計算**，嚴禁交由 LLM 或前端自行推算權威數值。
3. **不自動竄改真實帳本**：
   * 草稿產生與重算僅寫入 `private.pending_dividend_events`；唯有使用者明確呼叫確認 API，且通過 `expected_ledger_version` 樂觀鎖驗證後，才寫入正式交易帳本。
   * 已經使用者確認入帳（`CONFIRMED`）的紀錄，後續即使補登舊交易或修正市場公告，**絕不**自動修改或刪除已入帳交易，僅在必要時提示差異。
4. **Additive API 與可回退原則**：
   * 所有端點均為新增（Additive），不破壞既有記帳、持股查詢與現金餘額 API 契約。

---

## 2. 資料模型與 Schema 設計

### 2.1 公共層：`corporate_actions`（必要欄位規格）
沿用並擴充既有公共公司行動表，作為股利推算的唯一權威市場輸入：

| 欄位名稱 | 型別 | 說明與口徑 |
|---|---|---|
| `action_id` | `UUID / TEXT` | 主鍵 |
| `canonical_symbol` | `TEXT` | 標準化標的代碼（如 `2330.TW`、`0050.TW`） |
| `market` | `TEXT` | `TWSE` / `TPEx` |
| `security_type` | `TEXT` | `common_stock` / `financial` / `etf` / `reit` / `ky_stock`（影響二代健保與所得警示邏輯） |
| `ex_date` | `DATE` | 除息日或除權日（判定持有基準：需於 `ex_date` 前一交易日收盤持有） |
| `payment_date` | `DATE NULL` | 股利發放日（部分剛公告除息日之標的初期可能為 `NULL`） |
| `action_type` | `TEXT` | `CASH_DIVIDEND` / `STOCK_DIVIDEND`（若同日除權息，拆分為兩筆或由結構化欄位分別記載） |
| `cash_dividend_per_share` | `NUMERIC(18,6)` | 每股現金股利（元），無則為 `0` |
| `stock_dividend_ratio` | `NUMERIC(18,8)` | **權威每股配股率**（單位：股／每股；例如每張配 100 股則為 `0.10000000`）。**不可**一律寫死除以面額 10 元，須直接採用交易所公告配股率以相容彈性面額股（如 1 元、5 元面額股）。 |
| `par_value` | `NUMERIC(10,4) NULL` | 股票面額（供顯示與輔助稽核，預設 `10.0`） |
| `source_name` | `TEXT` | 資料來源（如 `TWSE`、`TPEx`、`MOPS`） |
| `source_updated_at` | `TIMESTAMPTZ` | 來源最後更新時間 |

### 2.2 私人層：`private.pending_dividend_events`

| 欄位名稱 | 型別 | 說明 |
|---|---|---|
| `draft_id` | `UUID` (PK) | 草稿唯一識別碼 |
| `owner_id` | `TEXT` (Indexed) | 所屬使用者識別碼（所有查詢與異動必帶權限檢查） |
| `canonical_symbol` | `TEXT` | 標的代碼 |
| `company_name` | `TEXT` | 標的名稱快照 |
| `security_type` | `TEXT` | `common_stock` / `financial` / `etf` / `reit` / `ky_stock` |
| `action_type` | `TEXT` | `CASH_DIVIDEND` 或 `STOCK_DIVIDEND` |
| `ex_date` | `DATE` | 除權息日 |
| `payment_date` | `DATE NULL` | 預定發放日 |
| `eligible_shares` | `NUMERIC(18,4)` | 推算當下重播出的除權息前一日基準持有股數 $Q_{\text{ex}-1}$ |
| `rate_per_share` | `NUMERIC(18,8)` | 每股現金（元）或每股配股率（股／股） |
| `gross_cash_amount` | `NUMERIC(18,2) NULL` | 推算現金股利毛額（`CASH_DIVIDEND` 專用） |
| `estimated_remit_fee` | `NUMERIC(18,2)` | 預估銀行匯費（預設 `10`，使用者可改為 `0` 或其他數值） |
| `estimated_nhi_fee` | `NUMERIC(18,2)` | 預估二代健保補充保費（預設依規則估算，使用者可微調） |
| `net_cash_amount` | `NUMERIC(18,2) NULL` | 最終預估實領現金（`gross_cash_amount - estimated_remit_fee - estimated_nhi_fee`，使用者微調後更新） |
| `estimated_stock_shares` | `NUMERIC(18,4) NULL` | 推算可得股票股利整股數（`STOCK_DIVIDEND` 專用） |
| `fractional_shares` | `NUMERIC(18,6) NULL` | 未滿 1 股之畸零股數（供 UI 提示，不直接計入整股入帳） |
| `confirmed_stock_shares` | `NUMERIC(18,4) NULL` | 最終確認入帳股數（預設等於 `estimated_stock_shares`，使用者可微調） |
| `status` | `TEXT` | `PENDING` / `CONFIRMED` / `DISMISSED` / `ALREADY_RECORDED` / `STALE` |
| `warnings` | `JSONB` | 結構化警示碼陣列（如 `["NHI_ESTIMATED", "ETF_EQUALIZATION_CHECK"]`） |
| `ledger_version_at_calc` | `BIGINT` | 推算當下的使用者帳本版本號，用於偵測補登舊交易 |
| `confirmed_trade_id` | `UUID NULL` | 確認入帳後對應寫入的真實交易紀錄 ID |
| `user_note` | `TEXT NULL` | 使用者備註 |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | 建立與最後更新時間 |

* **冪等唯一鍵**：`UNIQUE (owner_id, canonical_symbol, ex_date, action_type)`
  * 確保同一使用者、同一標的、同一除權息日與同一類型（現金／股票）只會存在一筆草稿，避免排程重跑或多次手動補掃產生重複提醒。

### 2.3 草稿狀態機（Status Lifecycle）

```text
  [掃描/排程推算]
        │
        ├── 偵測帳本已有相符手動股利紀錄 ──► ALREADY_RECORDED（不顯示待確認）
        │
        ▼
     PENDING ◄───(補登 ex_date 前交易，點「重新整理/重算」)─── STALE（暫時標記待重算）
      │   │
      │   ├── 使用者點「忽略」 ──────────────────────────► DISMISSED
      │   │
      │   └── 使用者「確認入帳」（樂觀鎖通過） ──────────► CONFIRMED（寫入 Ledger）
```

* **狀態保護規則**：
  * 任何情況下，`CONFIRMED` 與 `DISMISSED` 不會被排程重新改回 `PENDING`。
  * 若使用者的 `ledger_version` 推進，且異動交易的 `trade_date < draft.ex_date`（即補登或修改了除權息日前的買賣），後端將尚未確認的 `PENDING` 草稿標記為 `STALE` 並自動重算 `eligible_shares` 與金額／股數後回復為 `PENDING`（若重算後 $Q_{\text{ex}-1} \le 0$，則自動移除或轉為 `DISMISSED`）。

---

## 3. 後端確定性推算規則

所有計算於 Python 後端使用 `decimal.Decimal` 執行，禁止使用二進位浮點數（`float`）直接做金額與股數乘法。

### 3.1 基準持有股數 $Q_{\text{ex}-1}$ 計算
* **時間切點**：重播該 `owner_id` 針對 `canonical_symbol` 在 `trade_date < ex_date`（嚴格小於除權息日）的所有已確認正式交易紀錄。
  * 包含：買進（`+`）、賣出（`-`）、更早期的股票股利（`+`）、公司分割／減資換股調整。
  * **當日買進排除**：`trade_date == ex_date` 買進者不參與該次除權息，不計入 $Q_{\text{ex}-1}$。
  * **除權息前一日買進納入**：`trade_date == ex_date - 1 trading day` 買進者計入 $Q_{\text{ex}-1}$。
* **觸發門檻**：僅當 $Q_{\text{ex}-1} > 0$ 時建立草稿。

### 3.2 現金股利（`CASH_DIVIDEND`）推算規則
1. **毛額計算**：
   $$\text{gross\_cash\_amount} = \lfloor Q_{\text{ex}-1} \times \text{cash\_dividend\_per\_share} \rfloor$$
   （採 `ROUND_FLOOR` 無條件捨去至新台幣整數元；若 `gross_cash_amount <= 0` 則不建立草稿。）
2. **預設匯費（`estimated_remit_fee`）**：
   * 系統預設為 `10` 元（台股跨行匯費常見值），支援使用者於確認前在 UI 直接改為 `0`（同銀行帳戶）或其他金額。
3. **二代健保補充保費（`estimated_nhi_fee`）**：
   * 當 `security_type` 為 `common_stock` 或 `financial`，且 `gross_cash_amount >= 20000`：
     * 預設估算 $\lfloor \text{gross\_cash\_amount} \times 0.0211 \rfloor$（`2.11%` 無條件捨去至整數元），並附加警示碼 `NHI_ESTIMATED`。
   * 當 `security_type` 為 `etf` 或 `reit` 且 `gross_cash_amount >= 20000`：
     * 由於 ETF／REITs 配息常含免扣補充保費之「收益平準金」或「國內財產交易所得」，系統無法於公告當下確知最終股利所得佔比，預設 `estimated_nhi_fee = 0`，並附加警示碼 `ETF_EQUALIZATION_CHECK` 提醒使用者依配息通知書填寫實際扣繳金額。
   * 當 `security_type == "ky_stock"`：
     * KY 股屬於海外所得，免扣國內二代健保補充保費，預設 `estimated_nhi_fee = 0`（附加提示 `KY_OVERSEAS_INCOME`）。
   * 未達 `20,000` 元：預設 `estimated_nhi_fee = 0`。
4. **實領金額（`net_cash_amount`）**：
   $$\text{net\_cash\_amount} = \max(0,\ \text{gross\_cash\_amount} - \text{estimated\_remit\_fee} - \text{estimated\_nhi\_fee})$$

### 3.3 股票股利（`STOCK_DIVIDEND`）推算規則
1. **配股股數計算**：
   * 理論配股總數 $= Q_{\text{ex}-1} \times \text{stock\_dividend\_ratio}$
   * 實得整股數：`estimated_stock_shares = floor(理論配股總數)`
   * 畸零股數：`fractional_shares = 理論配股總數 - estimated_stock_shares`
2. **警示與入帳口徑**：
   * 若 `fractional_shares > 0`，附加警示碼 `HAS_FRACTIONAL_SHARES`（提醒：未滿 1 股之畸零股部分公司會於發放日折發現金或依集保規則處理）。
   * 確認入帳時，寫入正式帳本之 `STOCK_DIVIDEND` 交易紀錄：
     * **交易日期**：預設為 `payment_date`（若尚未公告則暫用 `ex_date` 並標註 `PAYMENT_DATE_TBD`，建議待發放日確定後再確認）。
     * **入帳價格／總成本**：買進成本為 `0`，僅增加持股股數，使該標的持有總成本維持不變、每股平均成本自然攤低。
   * 若 `estimated_stock_shares <= 0` 且僅有極小畸零股，仍可顯示並附 `FRACTIONAL_ONLY` 提示，或由使用者直接點選「忽略」。

### 3.4 同日除權息與防重複規則
* **同日除權＋除息**：拆成兩筆獨立草稿（一筆 `CASH_DIVIDEND`、一筆 `STOCK_DIVIDEND`），後端分別追蹤狀態與入帳類型；前端 UI 依 `(canonical_symbol, ex_date)` 視覺分組呈現，方便使用者一次核對。
* **已手動入帳防重複（Auto-Reconcile）**：
  * 推算草稿前，檢查該 `owner_id` 針對同 `canonical_symbol` 是否已有交易日落於 `[ex_date, payment_date + 14 天]`（若無 `payment_date` 則為 `[ex_date, ex_date + 60 天]`）的相同類型手動股利交易。
  * 若存在且金額誤差在 `±50` 元內（或股數誤差在 `±1` 股內），將草稿標記為 `ALREADY_RECORDED`，不納入「待確認」紅點計數，避免重複入帳。

---

## 4. 觸發機制與 API 契約（Additive）

### 4.1 觸發時機
1. **每日盤後批次排程**：
   * 於每日市場資料更新（含 `corporate_actions` 同步）完成後執行，掃描 `ex_date` 落於「當日或前 7 個交易日內」且為使用者實際有持股之標的，自動寫入／更新 `private.pending_dividend_events`。
   * （註：使用者自訂於「除權息日後即見草稿，並於發放日高亮可確認」或僅在發放日推播，於排程統一產生草稿後交由 UI 標註 `已除息／尚未發放` 與 `已發放／可核對入帳` 兩態呈現。）
2. **使用者手動補掃**：
   * 提供「掃描歷史漏記股利」按鈕，掃描使用者該帳戶有交易紀錄以來的歷史區間（例如自第一筆交易日起至今日），找出過去所有未入帳且未忽略之除權息事件。

### 4.2 API 端點規格（均需通過使用者身分驗證與 `owner_id` 隔離）

| 方法與路徑 | 用途 | 關鍵請求／回應欄位 |
|---|---|---|
| `GET /api/v1/me/dividends/pending` | 取得待確認股利清單與總筆數 | 回應：`{ "pending_count": int, "ledger_version": int, "items": [DraftItem...] }`；支援 query `?status=PENDING` |
| `POST /api/v1/me/dividends/scan` | 手動掃描歷史漏記股利（或強制重算） | 請求：`{ "from_date": "YYYY-MM-DD" (optional), "symbols": [...] (optional) }`；回應：`{ "newly_created": int, "recalculated": int, "already_recorded": int }` |
| `PATCH /api/v1/me/dividends/pending/{draft_id}` | 逐筆微調扣項、實領金額或實得股數 | 請求：`{ "estimated_remit_fee": "0", "estimated_nhi_fee": "422", "net_cash_amount": "19578", "confirmed_stock_shares": "100", "user_note": "..." }`（依類型選填）；後端重驗非負值後更新草稿 |
| `POST /api/v1/me/dividends/pending/confirm` | **逐筆或批次一鍵確認入帳** | 請求：`{ "draft_ids": ["uuid1", "uuid2"], "expected_ledger_version": 42, "trade_date_override": null }` |
| `POST /api/v1/me/dividends/pending/dismiss` | 忽略一筆或多筆草稿 | 請求：`{ "draft_ids": ["uuid1"], "reason": "optional" }` |

#### 確認入帳（`confirm`）交易原子性與衝突處理
* **Single DB Transaction**：所有 `draft_ids` 必須屬於當前 `owner_id` 且狀態均為 `PENDING`。
* **樂觀鎖驗證**：比對 `expected_ledger_version == current_owner_ledger_version`。若不符（代表期間另有新增／修改交易），整批回傳 `409 Conflict`（附最新版本與是否有 `STALE` 草稿需刷新），不寫入部分成功資料。
* **批次寫入帳本**：
  * 對 `CASH_DIVIDEND`：寫入一筆現金股利交易，同步增加使用者帳本現金餘額 `net_cash_amount`（記錄 `gross`、匯費與補充保費明細於交易 metadata）。
  * 對 `STOCK_DIVIDEND`：寫入一筆配股交易，同步增加該標的持有股數 `confirmed_stock_shares`（成本增加 `0`）。
  * 更新所有對應草稿為 `status = 'CONFIRMED'`、`confirmed_trade_id = new_trade_id`，並遞增 `ledger_version`。

---

## 5. Flutter UI／UX 操作流程

依 Drive `01_Janus_2.0_建議報告書.md` 與 [User App UI 契約](../ui/user-app.md) 原則：**不干擾既有記帳／持股精簡列表**，採輕量入口展開：

1. **記帳／持股頁輕量入口**：
   * 僅在 `pending_count > 0` 時，於列表上方顯示精簡提示列（Pill / Banner）：
     > `待確認股利 (3 筆) · 預估現金 +12,450 元 / 配股 +150 股`　`[查看核對]`
   * 另於「交易紀錄」頁右上角選單提供 **`掃描歷史漏記股利`** 入口。
2. **待確認股利清單頁（逐筆 + 批次）**：
   * **卡片分組呈現**：同標的同除權息日並排顯示現金與股票股利標籤；明確區分狀態標籤：
     * `已發放（可核對入帳）`：`today >= payment_date`
     * `已除息（待發放）`：`ex_date <= today < payment_date`（保留給使用者決定是否先預登或等發放日再確認）
   * **逐筆微調 Bottom Sheet**：
     * 現金股利顯示：`基準持股 × 每股現金 = 毛額`，可點選修改 **匯費（預設 10 元 / 一鍵設為 0）**、**二代健保補充保費** 或直接輸入 **實領金額**。
     * 股票股利顯示：`基準持股 × 配股率 = 實得股數`（如有畸零股則顯示淺灰提示）。
   * **底部固定批次操作列**：
     * 支援「全選可確認（已到發放日）」與手動多選勾選框。
     * 主按鈕：`確認入帳 (N 筆)`；次要操作：`忽略已選`。
     * 確認後即時刷新持股股數、平均成本與現金餘額，並提供簡短 Snackbar 提示已寫入幾筆交易。

---

## 6. WBS 實作切片與邊界驗收矩陣

### 6.1 實作切片（DIV-01 ～ DIV-04）

| ID | 工作項目 | 前置依賴 | 驗收重點 | 回退方式 |
|---|---|---|---|---|
| **DIV-01** | Schema Migration 與 `private.pending_dividend_events` 建立；補齊 `corporate_actions.stock_dividend_ratio` 欄位與來源同步確認 | 無 | 唯一鍵生效；Migration 可逆向降版 | 執行降版 Migration |
| **DIV-02** | 後端確定性推算引擎（`Decimal` 重播 $Q_{\text{ex}-1}$、現金／股票推算、二代健保／ETF／KY／彈性面額邏輯、防重複比對、盤後排程與補掃） | DIV-01 | 下方 §6.2 邊界測試案例 100% 通過 | 關閉排程旗標 `DIVIDEND_AUTO_SCAN_ENABLED=false` |
| **DIV-03** | 5 支 Additive API 端點實作（含 `expected_ledger_version` 樂觀鎖、原子交易寫入 Ledger 與 `owner_id` 隔離） | DIV-02 | 跨 Owner 存取回傳 403/404；版本衝突回滾無髒資料 | 停用新路由或功能旗標 |
| **DIV-04** | Flutter 提示徽章、待確認股利清單、逐筆微調 Bottom Sheet、批次一鍵確認與歷史補掃 UI | DIV-03 | 390px／200% 字級無溢出；確認後持股、成本與現金即時同步 | 隱藏 UI 功能旗標，既有記帳零影響 |

### 6.2 邊界案例驗收矩陣（測試必要條件）

| 案例編號 | 測試情境 | 預期行為 |
|---|---|---|
| **TC-01** | 除息日前 1 交易日收盤買進 1,000 股 vs 除息日當天買進 1,000 股 | 僅前 1 日買進者納入 $Q_{\text{ex}-1}$；當日買進者 $Q_{\text{ex}-1} = 0$ 不產生草稿 |
| **TC-02** | 同日同時除權（配股 0.1）與除息（配息 2.5 元） | 產生兩筆獨立草稿，可分別微調並透過單次批次請求同時確認入帳 |
| **TC-03** | 彈性面額股（非 10 元面額，公告 `stock_dividend_ratio = 0.08`） | 直接以 `stock_dividend_ratio` 計算，不誤用 `÷ 10` 推算 |
| **TC-04** | ETF 單筆現金股利毛額 25,000 元（$\ge 20,000$ 門檻） | `estimated_nhi_fee` 預設 `0` 並附 `ETF_EQUALIZATION_CHECK` 警示；一般個股則預設估算 2.11%（`527` 元）並附 `NHI_ESTIMATED` |
| **TC-05** | 使用者已於發放日後手動輸入該筆股利交易 | 掃描自動偵測並標記為 `ALREADY_RECORDED`，不跳重複提醒 |
| **TC-06** | 產生草稿後，使用者補登一筆 `ex_date` 之前的買進交易 | 原 `PENDING` 草稿標記 `STALE` 並重算最新 $Q_{\text{ex}-1}$；若原草稿已 `CONFIRMED` 則保持不動 |
| **TC-07** | 併發／版本衝突（舊 `expected_ledger_version` 呼叫 `confirm`） | 回傳 `409 Conflict`，整批不寫入帳本，帳本版本與筆數不變 |
| **TC-08** | 跨 Owner 隔離（Owner B 嘗試讀取、微調或確認 Owner A 的 `draft_id`） | 嚴格拒絕（403/404），無法讀取或異動任何私人紀錄 |
