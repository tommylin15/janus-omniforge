# Janus 今日首頁｜即時線圖重構 V1（2026-11-04）

## 使用者決策

- 原「今天值得看」出現 2026-10-27、10-28 的過期收盤價與觀察提示，影響資訊信任；**整卡移除**，不換一套舊文字摘要。
- 今日首頁改為 **市場即時 → 持股即時 → 其他正式資料**。TWD 單位、資料日期與來源需清楚；不將使用者資產估計與正式 Mart 的 canonical 數字混淆。
- 現有 Shioaji quote proxy 為唯一新增股票盤中來源，必須使用 `simulation=True`、不下單；既有 TWSE MIS fallback 仍走既有授權管道。
- 資料按需刷新：僅首頁可見且 App 前景、台北工作日 09:00–13:30 才約每 60 秒一次。不新增 Scheduler、不新增 paid resource，也不讓多人頁面觸發重疊上游任務。保留後端 PostgreSQL session advisory singleflight 與 shared TTL。
- 線圖標示最高／最低價格、發生時間、最新觀測位階（0–100%）。**只能稱「已收集分鐘點的高低」**，不是全天真正最高／最低；Shioaji 即時 Quote 未提供可驗證的全天極值發生時間。不補造頁面未開啟的 09:00 起始曲線。
- 第一版首頁顯示 TAIEX 今日分鐘折線、可切換 5／20／30 天正式 EOD 收盤歷史；持股前三檔的最新報價、當日漲跌與日變動金額、日期／時間，點選其中一檔可切換已收集的當日分鐘線。沒有足夠點就不畫圖，未登入不讀取個人報價。

## API／資料流

### 既有行情
- `GET /api/v1/public/market-home`：原先已包含 `sections.taiex.data.intraday_points`，minute_at 實際存於 `control.operational_index_minutes`；輸出為 `[{date: ISO8601, value: string}]`。近端現價／正式日線各有獨立口徑。
- `GET /api/v1/me/portfolio/quotes`：既有 Owner OAuth，按需取得持股報價與日期、前收、當日變動及市場狀態。要求 API 的 `quote_state=intraday`、`price_status=available`、報價日為台北今日、來源為 Shioaji／MIS，且報價時間距今不超過 120 秒，才在首頁顯示「盤中」。其他狀況保留 dated last-success，不顯示虛構今日損益。
- 原 `/api/v1/me/today-changes` 不再由首頁呼叫；後端既有研究 API 本輪不刪，避免其他讀者或專案依賴突然失效。

### 新增股票分鐘點
- Migration `076_operational_stock_minutes`：`control.operational_symbol_minutes` 依 `(symbol,minute_at)` 唯一；紀錄 `quote_at,price,received_at,source`，僅在原 `QuoteRouter.save_last_quotes` 真實盤中來源通過檢查後寫入，不從歷史 EOD 推估，不再建高頻 Worker。
- 同分鐘有重覆資料時只採較新的真實 `quote_at`；每次有盤中股票寫入時清除三天以前的分鐘點，且保留既有交易、持股及 EOD。
- `GET /api/v1/me/portfolio/intraday?symbol=2330` 需通過 Owner OAuth，證實該標的是該 Owner 目前有正股數的 TWD 持股才讀取 `control.operational_symbol_minutes`。只回台北當日最多 270 點。沒有持股 404，未授權 401，格式非法 422；讀取本身不觸發上游報價。
- 返回 `{symbol, as_of, items, count, observation_kind:"page_demanded_minutes", is_full_day:false}`；任何日期缺口只顯示實際點，不填補。
- 表權限只給 `janus_private_api`；公共 API 不得讀取新表。資料列本身不含 Owner ID，使用者持股範圍仍由 API Owner guard 嚴格檢查。

## UI 操作與降級

- 移除 `FinalTodayPage._changes()`、盤前／盤後切換與首次載入的 today-changes 網路請求。保留正式市場活動、法人和經驗證研究資料區，不重設模型。
- 首頁預設 `historyDays=0`。有兩個以上實際分鐘點才繪線；只在分鐘模式顯示「觀測高／低、台北 HH:mm、區間位階」。可點選圖面查詢實際觀測價格與時間；正式 EOD 5／20／30 天歷史仍獨立顯示。
- 持股摘要最多 3 檔，可切換當日觀測線，點右側箭頭進入個股詳情。現價或變動缺失時顯示「—」，過時行情只標示實際價格日；不以查詢時間代替報價時間。
- 休市或切換至其他分頁、App 背景後停止自動請求；再次顯示時進行一輪新的有界讀取。若 quote source 失聯，沿用 dated cache，不宣稱交易日行情已更新。
- **本版不新增** 全市場 tick 訂閱、成交量異常預測、行情警報派送、停損停利訊號或第三方收費訂閱。這些需另外確定資料可用性與通知需求。

## 2026-11-04 Dev 工程閉環與驗收收據

本次 CODE／OFFLINE TEST／DEV DB MIGRATION／固定映像 RELEASE／零流量 CANDIDATE／AUTH BOUNDARY／API 100% PROMOTION／獨立 API RUNTIME READBACK **均 PASS**；尚未有已登入使用者真實盤中資料兩個以上分鐘點的人工操作收據，該單項維持待 Owner UAT，而非標記全案 FULL PASS。

- 全量 Flutter 149 tests PASS：[41807675862](https://github.com/tommylin15/janus-omniforge/actions/runs/41807675862)。
- 完整 Python／Flutter Release PASS：[41807949511](https://github.com/tommylin15/janus-omniforge/actions/runs/41807949511)，source `daaa49b286c12f00034ef9dddd90897141080403`。
- Migration 076 PASS：[41807779405](https://github.com/tommylin15/janus-omniforge/actions/runs/41807779405)，不更改流量及既有 Job image。
- 0% Candidate PASS：[41808789288](https://github.com/tommylin15/janus-omniforge/actions/runs/41808789288)；授權與公開行情比較 PASS：[41808975077](https://github.com/tommylin15/janus-omniforge/actions/runs/41808975077)。
- API／Flutter Dev 100% 受控切流 PASS：[41809140720](https://github.com/tommylin15/janus-omniforge/actions/runs/41809140720)，保留 prior-serving GHCR source `60b10da3e2ed4a5b5de3933e592cd8c246f0dcb8` 作可回復基準。
- 獨立唯讀 Dev runtime PASS：[41809409248](https://github.com/tommylin15/janus-omniforge/actions/runs/41809409248)；證實 active build id、100% immutable source、健康檢查、公開 market-home、匿名 Owner 分鐘線拒絕。此步**不**驗證有權限 Owner 的分鐘線實際內容。
- 本輪沒有更改現有四個 Cloud Run Jobs、Scheduler、IAM、Owner ledger。真實盤中兩輪分鐘點，須在交易時間且打開頁面後才可採集；休市或初次單點是合法「資料不足」而非假 PASS。

## 工程驗收與發布

順序：修改 UI／API／Migration／測試 → Python＋Flutter 全量 GHCR Release → Dev migration 076 → 0% 固定 digest Candidate → OAuth／Owner negative/public market boundary → 100% Dev API 切流 → Live Dev readback → 最終一次集中驗收回報。

- 自動化：`tests/test_today_intraday_owner.py` 驗 Owner 401／404／422、今天分鐘點、無推造交易；`apps/user_app/test/today_market_visual_test.dart` 和 `change_analysis_test.dart` 驗實際分鐘高低與移除舊卡片。保留現有 quote singleflight／Shioaji simulation 測試。
- Runtime：Migration 076 必須 PASS 且 ACL 正確；新的 `/app/build-id.txt` 需等於 fixed-source SHA；未登入讀個股分鐘點應拒絕；大盤頁與持股讀取不新增 batch／Scheduler。
- 真正盤中當日高低的驗收需在有至少兩筆有效 Quote 的 09:00–13:30 交易日進行；不能以 CI fixture、休市或只有單點的 API 回應說明已完成完整 live quote 驗收。
- 本輪任務結案依當次 Release／Dev runtime 的實際證據；沒有證據維持 partial／unknown，不以單純 commit 或發版綠燈冒稱 Owner 實機 PASS。
