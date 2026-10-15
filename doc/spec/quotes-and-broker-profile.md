# Operational Quote Router／Broker Profile

交易前試算、成交後快速更新與正式重算的責任／速度目標見 [持股優先契約](holdings-first.md)。

## 行情契約

### Active market scope

2026-10-13 使用者恢復三項優先整合，官方 EOD 行情範圍改為 **TWSE + TPEx 全部個股**。每市場一次官方整批擷取，保存原始 Stage、canonical Core OHLCV、provenance 與 PostgreSQL serving；未持有、未關注、未入研究 500 的個股也先保存，交易入帳後直接依 owner positions 查既有報價。

2026-10-13 後續決策：研究／screening 母體及關注新增股票資格一律改全上市櫃個股，取消 Liquid 500 admission；既有 50 筆關注 quota 保留。全市場 coverage 缺失率 TWSE ≤10%、TPEx ≤30% 分市場過關，詳見 [全市場／總控契約](full-market-batch-policy.md)。ETF 既有授權路徑保留，00719B 可用官方 TPEx EOD；未驗證盤中資料不可當 live tick。盤中 MIS 保持可見需求／TTL，不新增全市場逐分鐘排程。

### Persistent latest-price resolver

User-visible latest price is resolved server-side. Flutter never decides whether to read MIS or EOD.
The resolver combines two persistent PostgreSQL read models:

1. `control.operational_last_quotes`: last successful authorized TWSE MIS quote;
2. `publication.stock_latest` (`ohlcv`): latest persisted EOD serving projection rebuilt from canonical Core.

The small in-process `MisQuotes.cache` is only a 10-second anti-burst optimization. It is not the
authoritative cache and may disappear on Cloud Run restart. Last-success continuity and the normal
refresh TTL are based on PostgreSQL, so the serving state survives process restarts and scale-to-zero.

Core Iceberg OHLCV remains canonical history. Operational/MIS values never write or rewrite canonical
OHLCV, Private Mart or publication history. Same-day EOD data takes precedence over same-day MIS once
the 14:30 ingestion has committed its serving projection.

Resolver states:

- `intraday`: current trading-day MIS quote during 09:00–13:30 Asia/Taipei;
- `closing_pending_eod`: last current-day MIS quote after 13:30 while same-day EOD is not yet available;
- `eod_final`: persisted canonical EOD serving value for that date;
- `stale`: only an older successful value is available;
- `missing`: no usable persisted value.

Source, `quote_at`, `received_at`, `price_date`, route version, state and final/non-final semantics
remain explicit. A failed MIS request never clears the last successful persisted value.

### Stock Header／持股估值語意

`GET /api/v1/public/stock-header/{symbol}` 先讀 bounded canonical OHLCV，再套 latest-price resolver。為顯示最近一次漲跌，backend 最多讀最近兩筆正式 OHLCV，回傳 `previous_close`、`change`、`change_percent`。

- 若 resolver 已切到同日 `eod_final`，previous close 使用前一交易日。
- 若盤中 MIS 價格日期晚於最新正式 EOD，previous close 使用最新正式 EOD。
- 缺 reference close 時欄位保持 null，不補 0。

Owner 持股畫面與 Stock Detail「我的持股」使用 `GET /api/v1/me/portfolio/quotes` latest-price valuation（market price／market value／unrealized PnL／return）。`/journal/positions` 仍提供 operational shares／average cost fallback，但不得讓已取得 latest-price 的持股卡顯示較舊現價。

### Demand-driven MIS refresh

There is **no one-minute market quote Scheduler**. When the App is unused, MIS request volume is zero.

During a regular TWSE session, visible Today／Watchlist／Holdings／Stock Detail pages may revalidate
once per minute. The backend applies a persistent 60-second TTL before calling MIS, so multiple reads
inside the TTL use the same PostgreSQL last-success value. Leaving the page, backgrounding the App or
leaving regular market hours stops UI polling.

Holdings also provides an explicit **「更新股價」** action. It resolves the authenticated owner's
current holdings and refreshes only those TWSE symbols. Manual refresh bypasses the normal 60-second
TTL but retains a 10-second hard throttle. Caller-supplied owner/symbol lists are not accepted.

TAIEX follows the same demand-driven pattern for Today. No TPEx index is queried or displayed.

### EOD handoff

The existing `janus-batch-controller` owns both ingestion slots; no second Scheduler or Cloud Run Job
is created:

- 07:30 Asia/Taipei: normal daily ingestion contract;
- 14:30 Asia/Taipei: same-day TWSE/TPEx full-market price/index close using the existing `janus-ingestion-core`,
  execution-level `INGESTION_DATE=<same Taipei date>` and
  `INGESTION_DATASETS=twse-market-volume,tpex-market-volume,taiex`.

From 13:30 until the same-day EOD projection is available, UI may continue to show the final MIS value
as `closing_pending_eod`. Holdings stops one-minute polling at 13:30; after the 14:30 handoff time it
needs only one successful persistent resolver read per page lifecycle to pick up `eod_final`, and tab
re-entry must not repeatedly refetch after that successful read. An explicit user refresh or a ledger
mutation that invalidates the displayed holdings may request another read.

When same-day EOD is persisted, the resolver switches to `eod_final` without a frontend API/source
switch. If 14:30 EOD is delayed or fails, last MIS remains visible with non-final/pending semantics
rather than falling back silently to yesterday.

## 官方 TPEx 指定日期行情（長期契約）

TPEx `dailyQuotes` 是**正式的按交易日查價能力**，不僅是 `00697B` 的一次性修補。對 Core 尚未涵蓋、但已確認為 TPEx 且符合授權來源的持有商品，使用系統按需路徑補齊官方收盤價；不是放寬研究母體的 Canonical OHLCV 標準。


- **最新批量入口**：`https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes`，只保留近七日的候選資料，不將回傳順序視為時間排序。
- **歷史定日入口**：`https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date=YYYY%2FMM%2FDD&response=json`。以**官方回應內的 date** 與指定交易日完全相等作驗收，禁止以 URL 參數本身取代來源日期；曾遇到舊版 URL 忽略 10/14 參數，回傳 10/15，因此不得重用它來歷史回補。
- **缺值拒絕**：不存在、未發布（當日 14:30 前）、非數值／非有限正值、日期不符、schema 異常、WAF／HTML、來源不合格都維持 missing／partial，不能把前一日或後一日的資料假裝當日資料。
- **長期儲存與追溯**：`control.official_tpex_eod_history`（migration 061）以 `(symbol,trade_date)` 為 immutable key，保存價格、`source_uri`、`record_sha256`、`first_observed_at`；由正式資料庫角色寫入；另維持最新報價快取。衝突不能靜默改寫、更新不可覆蓋先前的交易日。
- **估值 PIT**：Private Mart 先讀 Canonical Core，同一商品缺價時才讀 `trade_date <= valuation_date` 的已保存官方價；較早日價格標示 stale，不把當日或未來價格倒灌歷史估值。ETF 不因未入股票研究池 500／全股票母體而失去已授權的行情來源。
- **執行負荷**：Owner 的按需查價與既有 Private Pipeline 共用執行路徑、限流、失敗冷卻與部署鎖；不新增高頻 Schedule、額外付費 API、容器或平行寫入者。研究級嚴格 PIT 特徵是否可回推仍由 first-observed 與資料可用時間另行判定；補價不等於 canonical 升級。

## Broker Profile

`GET /api/v1/me/broker-profile` 回 owner 的最新 profile；尚無設定為 version 0。
`PUT` 要求 `Idempotency-Key`、`expected_version`，版本衝突回 409。
欄位：fee_discount_multiplier（0–1）、minimum_fee（非負 TWD）、
cash_strategy（reserve／balanced／invested）、declared_cash／cash_as_of（同時有值或皆 null）。
每次變更新增 immutable `private.broker_profile_revisions`，保留 rule_version、
版本、日期與 owner audit change；重送同 key 回原 revision。

申報現金是使用者手填 snapshot，**不是 canonical cash ledger balance**，
不參與正式 portfolio aggregate／cash ratio。設定不追溯改寫已儲存交易的 fee／tax。
目前沒有新增 CASH_IN／CASH_OUT，也沒有券商同步或成本法切換。
2026-10-15 自動費稅及歷史更正的新需求與未完成驗收見 [持股契約](holdings-first.md)／TODO；完整可稽核 cash ledger 尚未由此切片交付；
若其為 A 組所需 acceptance，狀態維持 partial，不以 profile CRUD 當成完成。

私人匯出包含完整 profile revisions；既有刪除 pipeline 在同一 owner 範圍清除 revisions。
共享 public quote 不屬私人資料，刪除 owner 不刪除它。UI 顯示申報現金／日期與版本，
讀取／儲存失敗可重試；不得把申報值呈現為正式餘額。

## Migration／交付 lineage

- `044_quotes_broker_profile.sql`：quotes／broker-profile 基礎能力。
- `046_twse_only_latest_price.sql`：收斂 active scope 為 TWSE latest-price。
- `047_latest_price_route_v2.sql`：latest-price route v2。
- migrations 只在需要時由既有 dev workflow 執行；已成功 migration 不因文件更新重跑。
- migration／CI／Cloud Run／runtime acceptance 必須另有 evidence；規格文件本身不構成成功證據。2026-10-06 本輪 live evidence 見 [latest-price／Ledger UI 驗收紀錄](../archive/latest-price-ledger-ui-acceptance-2026-10-06.md)。


### TPEx 官方日收盤價補齊與 legacy aggregate 驗收注意事項

2026-10-15 P0 00697B／00719B 實際驗收：已驗證按 2026-10-14 官方來源日查價與歷史價資料庫，真實 dev Owner v354 的 8/8 positions／unrealized rows 均有價格與 PnL，`mart_user_portfolio_summary` `aggregate_status=available`、`missing_price_count=0`、`affected_symbol_count=0`，聚合市值、未實現損益、報酬皆有值。實證見 [Owner readonly #38732675488](https://github.com/tommylin15/janus-omniforge/actions/runs/38732675488) 和 [final receipt gate #38733406224](https://github.com/tommylin15/janus-omniforge/actions/runs/38733406224)。

舊 Private Iceberg summary schema 不含 `stale_price_count` 欄位（查讀為 null，不是確定值 0）。接受 `aggregate_status=available` 的根據是 deterministic `calculate_risk_marts()` 同時計算缺價與 stale 數，任何一項大於零即把 aggregate 設成 withheld；因此必須聯合核對 `missing_price_count=0`、`affected_symbol_count=0` 與總 PnL 完整，不准把缺失欄位直接填零或因不存在而誤判持股缺價。若未來要在 serving 實際顯示 `stale_price_count`，需獨立加入 Private Iceberg 的 additive schema evolution 並以同版 deployment／資料讀回驗收；目前未聲稱該欄位已發佈。P0 backend PASS 不代表最新交易日或正式 App UI 已 PASS。
