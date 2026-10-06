# Operational Quote Router／Broker Profile

## 行情契約

### Active market scope

Janus active market scope is **TWSE only**. TPEx／櫃買 is retired from active collection,
search/admission, MIS routing, market-home display and future publication. Historical Core rows,
migration history and audit evidence are retained; retirement must not rewrite or delete history.

Latest-price serving scope is:

- current TWSE Liquid 500;
- TWSE holdings that remain valid owner positions even when outside the current 500;
- active TWSE watchlist symbols;
- a currently opened TWSE stock detail;
- TAIEX for the Today market snapshot.

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
- 14:30 Asia/Taipei: same-day TWSE price/index close using the existing `janus-ingestion-core`,
  execution-level `INGESTION_DATE=<same Taipei date>` and
  `INGESTION_DATASETS=twse-market-volume,taiex`.

From 13:30 until the same-day EOD projection is available, UI may continue to show the final MIS value
as `closing_pending_eod`. When same-day EOD is persisted, the resolver switches to `eod_final`
without a frontend API/source switch. If 14:30 EOD is delayed or fails, last MIS remains visible with
non-final/pending semantics rather than falling back silently to yesterday.

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
完整可稽核 cash ledger、profile fee 自動計算／交易 rule snapshot 尚未由此切片交付；
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

