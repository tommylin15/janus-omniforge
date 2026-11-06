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


## V2 覆蓋決策｜2026-11-05：一般股優先、融資兩週趨勢、法人金流

本節覆蓋 V1 的「持股前三檔」與法人股數長條卡。V1 的部署收據不代表 V2 部署成功。

### Owner 持股卡
- 今日首頁先列出全部 TWD 一般股（兩欄窄版卡，寬度不足退成單欄），附代碼、名稱、現價、可證實的漲跌額及漲跌幅、實際來源日／時間。ETF／BOND_ETF 獨立在下方並預設收合、可展開，不丟失交易或報價資料。
- API 的部位新增 instrument_kind（依 stock_identities 正式類型，缺失時僅為 UI 類型使用代碼型態後備辨識），不將 ETF 塞進股票研究母體。
- 單檔選擇後沿用 Owner 限定的分鐘曲線，無兩個真實分鐘點不畫線。休市顯示最後有效價格日期；沒有有效的比較前收，不創造漲跌額與幅度。
- 前景盤中 60 秒 QuoteRouter、Shioaji simulation=True、跨讀者 PostgreSQL singleflight 保持原契約；不新增排程、下單或高頻籌碼輪詢。

### EOD 籌碼（TWSE 上市市場限定）
- 新增公開 /api/v1/public/market-leverage-flow：與 market-home.v1、Owner 私有資料、60 秒即時報價拆開，使用固定 TWSE 官方 URL、2.5 秒單次 timeout、有界查詢及每服務執行個體 1 小時快取。僅進入首頁時請求，停留整日後不宣稱自動取得晚間資料。
- TWSE MI_MARGN：讀取「融資金額(仟元)」近 10 個實際有資料交易日，換算億元折線與逐日明細。每日變化＝同份官方報表的「今日餘額−前日餘額」，不是今天減昨天的「今日餘額」；官方次日會修訂前日餘額，明確標示最新來源日。
  - https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=YYYYMMDD&selectType=MS&response=json
- TWSE BFI82U：外資、投信與自營商（自行買賣+避險）取官方買賣超金額 TWD，另顯示與前一有資料交易日買賣超的差異，不拿股數乘收盤價推估，不稱為法人持股變化。自營商包含避險，不推論純方向。
  - https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate=YYYYMMDD&type=day&response=json
- 目前只涵蓋上市市場，不能標示台股全市場、上櫃或當日即時籌碼。官方來源失敗、回應日期不符、欄位差異、交易日缺失一律保留 missing／partial，不造數字／填充交易日。

### 上線驗收
- 股票列表給 ETF 0050/00697B/00719B 排在前、普通股 2330/2327/2382 在後的測資，必須仍顯示全部三檔普通股，ETF 可收放；驗 Owner 報價日期、可用漲跌與分鐘線。
- Python 專項／Flutter analyze、test、build 需全 PASS，融資與法人須實際官方回應解析並確認日期與金額單位。
- 經既有固定版 GHCR Release、0% Candidate、OAuth/Owner guard、Dev 100% Promotion、實際 API/已登入 Owner 手機讀回才可稱整體完成；提交程式／CI 綠燈不代表 Live 完成。


## V4｜今日頁持股走勢聚焦與去重（2026-11-05 使用者核定）

- **今日唯一主體是走勢**：上方 TAIEX 09:00–13:30、下方單張可切換的持股分鐘圖；移除逐檔大張價格、日漲跌、當日持股金額卡及重複的現金／總資產摘要。最新價、高低與時間由被選取的分鐘圖承擔，圖上方僅補資料日／狀態。
- **快速切換**：橫向 chip 列先普通股，ETF 預設收合；點代碼或前後箭頭切換單一股票分鐘線；「詳情」跳原本個股頁。不另造另一套完整持股頁；只有 ETF 的用戶可直接選第一檔 ETF。
- **頁面職責**：今日看盤中走勢／盤後法人與融資；持股／記帳看多檔持股價、股數、成本、市值、當日和累計損益及報表；個股詳情看長期 K 線、營運、估值、籌碼與模型研究。持股資料不因此刪除。
- **行情真實性**：實際採樣的分鐘點為 sampled_live_quote；授權 Shioaji 歷史回補的完整 1 分 K 收盤價為 historical_1m_close，分別標記。不能混成同樣即時來源、不能用首個分鐘點假裝正式昨收，也不能插補沒有交易或缺少資料的分鐘。
- **效能**：保持前景每 60 秒共用行情，不逐一抓所有持股歷史。切換只讀所選標的，補回 K 棒僅在頁面開啟／有大缺口時受跨實例冷卻控制，不受 60 秒輪詢影響；首頁不再讀只供持股頁使用的 Owner 資產 snapshot。
- **驗收**：7 檔（含 ETF）皆可由 390px 手機操作切換，僅一張個股圖、沒有多張重複價差／損益卡、切換不混舊股票分鐘線、Owner auth 與資料日期保留。K 棒回補是否真正成功依另一路 Live Runtime evidence 判定。


### V4 歷史 1 分 K 回補：Owner 正向驗收紀錄（2026-11-06）

- **User-confirmed PASS**：使用者於既有 Dev App 親自驗收，明確回報「驗收成功，有回補分鐘點」。此項確認已發布的 App／API／私有 Shioaji Proxy 回補功能對 Owner 產生可見的歷史分鐘點，按已核定的真實 Dev 使用情境判定功能驗收成功。
- **範圍限制**：此回報未提供逐檔 symbol、回補分鐘數、API `status/saved`、PG row counts 或 09:00–13:30 全時段覆蓋率，不宣稱每檔都補齊或已獨立核實所有資料行。其他 UI 功能（ETF 切換、紅綠分色、零線與 60 秒刷新）的逐項真人驗收維持原狀。
- **先前 CI 驗證故障的處置**：GitHub Actions runner 的 WIF ID token 取得失敗只影響 CI 私有 Proxy 探針，不改寫為 runtime 失敗，亦不假稱 CI 探針 PASS；不為此擴張 IAM。原正式資料路徑、`simulation=True`、三天保留、90 分鐘冷卻與每檔每日三次上限不變。


## V5｜買賣五檔按需面板（2026-11-06）

- 在「持股今日走勢」選定股票的 09:00–13:30 分鐘圖**下方**新增單張買賣五檔，跟隨原本普通股／ETF chip、前後箭頭切換，不新增多張大卡或重複損益摘要。
- **官方 API 語意澄清**：Shioaji `api.snapshots()` 僅提供最佳一檔委買／賣價量；完整五檔來自 `QuoteType.BidAsk` 的 `BidAskSTKv1` 訂閱回調，不能將單檔 Snapshot 虛構成五檔，也不可高頻輪詢 `snapshots()`。
  - 官方 Snapshot：https://sinotrade.github.io/zh/tutor/market_data/snapshot/
  - 官方 BidAsk：https://sinotrade.github.io/zh/tutor/market_data/streaming/stocks/
- Proxy 使用既有 `simulation=True`、私人 Cloud Run OIDC 與唯一串流連線管理者；新增 `GET /order-book/{symbol}` 僅讀在頁面請求時建立的整股 BidAsk 訂閱，維持 130 秒需求租期／過期退訂、120 秒資料新鮮度。**絕不使用下單 API**。
- Janus API 新增 `GET /api/v1/me/portfolio/order-book?symbol=...`：僅 Owner 正股數 TWD 持股，403/401 沿用既有 OAuth、未持有 404、錯誤代號 422；再由 API 用 OIDC 取得私有 Proxy，驗證股票代碼、市場、時間、來源、五檔數量、價格與張數。缺值／過期／部分五檔不得假裝完整。
- Flutter 只有初次選股、切股與使用者按「手動讀取五檔」才取得資料，不參與原本 60 秒行情、K 棒回補或 Scheduler；顯示委買／委賣 1–5、價量、相對量條、兩邊加總、台北報價時刻與來源。手動刷新是對共享訂閱快取再次讀取，不是 `snapshots()` 輪詢。
- 驗收分層：Proxy 測試 BidAsk 回調／禁用 Snapshot／租期清理，API 測 Owner 權限與交換所時序／缺值，Flutter 390px Widget 測五檔及換股不串資料；正式上線需 Proxy、Janus API、Flutter 同版部署及有權 Owner 盤中確認真五檔，未驗證保持 partial。


### V5 Release／Dev 收據（2026-11-06）

- Proxy simulation-only BidAsk [#42148419484](https://github.com/tommylin15/janus-omniforge/actions/runs/42148419484) PASS；Flutter analyze／test／build [#42149261653](https://github.com/tommylin15/janus-omniforge/actions/runs/42149261653) PASS。
- 固定來源 `c4a30876e544629e82089c65130e1b6f5062caa3` 完整 Python＋Flutter + 四 GHCR image Release [#42149287772](https://github.com/tommylin15/janus-omniforge/actions/runs/42149287772) PASS；0% Candidate [#42149960939](https://github.com/tommylin15/janus-omniforge/actions/runs/42149960939) PASS；OAuth 負向＋市場行情 parity [#42150196571](https://github.com/tommylin15/janus-omniforge/actions/runs/42150196571) PASS；受控 API/App 100% promotion [#42150459206](https://github.com/tommylin15/janus-omniforge/actions/runs/42150459206) PASS。
- Live Owner authenticated 五檔實際值 UAT **NOT_VERIFIED**；上面是軟體／發布／匿名與公開讀回，不可推論至少一檔已得到五檔有效 BidAsk callback。

- **獨立現役唯讀回驗**：[ #42150855735 ](https://github.com/tommylin15/janus-omniforge/actions/runs/42150855735) `API_LIVE_READBACK_PASS`；active traffic 100%、build-id `c4a30876e544629e82089c65130e1b6f5062caa3`、不可變 GHCR digest、公開 2330 讀取 HTTP 200、未登入五檔 /portfolio/order-book 拒絕、GCP mutation 0。Owner authenticated 五檔實際價量仍需使用者本人頁面驗收。


## V6｜2026-11-06 今日走勢分鐘點缺口修正

- 2327／加權指數於 10:27 顯示 10:25／10:26 孤點，是資料缺漏而非純粹繪圖錯誤。圖表只連續相鄰真實分鐘點；歷史 Kbar 上次補到當時，其後頁面無持續前景讀價時會產生空洞。
- 根因：原前端同一檔使用兩小時 slot，後端又設每檔 90 分鐘的跨使用者 Kbar 冷卻，再次進頁仍無法補齊數十分鐘缺口。
- 修正：只在進入可見頁／返回前景／切換個股時依 30 分鐘 slot 嘗試回補，**從 60 秒行情計時路徑解除歷史補收**；PG 仍先以實際分鐘涵蓋率判斷稀疏（不足約 85%），只有不足時跨使用者原子 claim，冷卻縮至 30 分鐘，**每日最多 3 次** 不變。歷史 migration 078 記錄當時 90m 制度，現役 policy 以 V6 覆蓋。
- 不增加 Scheduler、Job、付費資源、常駐 Shioaji 連線；simulation=True／Kbar 真資料／Owner 驗證／3 天保留與歷史 Kbar 和即時採樣來源分離維持不變。
- 當 API 受三次額度所限、券商歷史無資料、合法無成交或休市，仍保留斷線，不能畫假直線。CI／Dev 部署和真人真值分開驗收。


### V6 發布收據｜2026-11-06

- 變更 commit `28d553168f676f404cb901aa33243ae4a5936076`；固定 Release source `7a2100dd203328792d1d35af87413e9dfc8a4f8b`。
- Flutter CI [#42152043926](https://github.com/tommylin15/janus-omniforge/actions/runs/42152043926) PASS、完整 Python＋Flutter + 4 GHCR digest [#42152171609](https://github.com/tommylin15/janus-omniforge/actions/runs/42152171609) PASS；0% [#42152812792](https://github.com/tommylin15/janus-omniforge/actions/runs/42152812792)、OAuth/market parity [#42152981514](https://github.com/tommylin15/janus-omniforge/actions/runs/42152981514)、API/App-only 100% [#42153121460](https://github.com/tommylin15/janus-omniforge/actions/runs/42153121460) 均 PASS。
- 獨立現役固定 SHA、GHCR digest、App build-id、Owner 匿名隔離、公開價格 200／TAIEX 分鐘資料契約唯讀回驗 [#42153300173](https://github.com/tommylin15/janus-omniforge/actions/runs/42153300173) PASS。
- **尚待**：沒有已登入 Owner 身分實際讓 2327／TAIEX 重新進頁後再讀 Kbars 的正向收據，也沒有本輪缺口數／PG Kbar rows 前後對照，因此只可宣稱 CODE／TEST／Dev live deploy PASS，不宣稱市場全天分鐘資料已經完整。


### V5／V6 Owner 實機驗收結案（2026-11-06）

- **驗收來源**：使用者在既有 Dev App 重新進入「今日」頁後回報：「分鐘點正常回補了，五檔買賣也有了」。據此將 V6 持股／大盤分鐘缺口回補，以及 V5 個股分鐘圖下方買賣五檔**使用者操作驗收**判定為 `OWNER_UAT_PASS / CLOSED`。
- 此回報證實新版畫面上的分鐘回補與五檔顯示可用，並與上述同版 Flutter／Python、Private Proxy、API-only 100% 切流及獨立 Runtime 收據共同支持功能結案。**不推定** 09:00–13:30 每分鐘都完整、所有持股均有五檔、每檔的數量正確、手動刷新及休市／缺值分支都已逐一測試；未附逐分鐘 PG row count 或券商原始五檔回應。既有無資料不造點、三次回補上限及五檔新鮮度控制不變。
- 前文關於「Owner 尚待」「NOT_VERIFIED」均屬本次驗收**之前**的歷史狀態；當前以此段使用者確認為準，不為已通過的正常顯示再要求重複驗收。
