# Janus UI — User App 頁面

更新：2026-10-11（四頁視覺優先）

## 5. User App 頁面

本文件只保存目前有效的 User App 資訊架構與狀態語意。被取代的「五個生成式 role／CIO」UI 不再是 active contract；現行研究架構為 persisted 五 specialist + authorized manual On-demand CEO。

**2026-10-11 新的四頁視覺契約：**[A 正式 UI 規格](visual-first-four-pages.md)／[B 工程工作單](visual-first-delivery.md)。舊四 PNG 是最低基礎值、非圖表上限。各頁唯一 Hero，先圖與大數字後文字；當本次新順序與舊 PNG 不一致，以新規格為準，原資料治理不變。

## 5.0 Final Visual Contract

手機版最終 presentation target 由 [`reference/user-app-final/README.md`](reference/user-app-final/README.md) 定義，固定四張圖：

- `reference/user-app-final/today.png` — 今日
- `reference/user-app-final/watchlist.png` — 關注
- `reference/user-app-final/ledger.png` — 記帳／筆記
- `reference/user-app-final/stock-detail.png` — 個股詳情

圖片規範資訊架構、section order、card hierarchy、手機資訊密度與視覺語言；sample price、PnL、法人金額、日期、AI prose、健康度、logo、sparkline、mock chart 只作 illustrative，不得 hard-code 或當 canonical data。

資料正確性、missing／stale／partial／blocked、auth／owner isolation、PIT／provenance、source authorization、canonical number、publication 與 LLM boundary 以 active SPEC／WBS／runtime contract 為準。PNG 未 commit 或 live acceptance 未完成時不得宣稱 final visual convergence 完成。

對 A 組而言，Final Visual Contract 不是後續 cosmetic polish。Today／Watchlist／Ledger／Stock Detail 的**非 AI 主體 UI**必須在既有 GCP dev、真實登入、真實 owner、真實資料與真實 API/runtime 下先明顯收斂；至少包含 section order、card hierarchy、資訊密度、spacing、主要色彩、mobile layout、390px 級版面，以及 loading／empty／error／partial／stale／missing 不破壞主要 hierarchy。若真實畫面仍明顯像 legacy UI，即為 A 組 acceptance failure／implementation gap。

Specialist／CEO 等 AI-only 區塊未就緒時，可以 bounded unavailable／hidden／partial；不得因 AI 尚未完成而保留舊版非 AI layout。A 組的真實驗收發現 UI/data-state/functional gap 後，需回到 implementation 修正並重新部署／重驗，不能只留下報告。

## 5.1 今日

「今日」是**個人相關市場入口**：先在不阻塞首屏的前提下找有來源且同時點的本人持股／關注變化；不足時退回 deterministic published market baseline／已驗證市場判讀。Mart／研究內容是 enhancement，不得反過來阻擋 baseline。

首屏順序：

1. `MyRelevantTodayHero`（有合格 owner-scoped 持股／關注異動時優先；無則 `MarketVerdictHero`，再無才以 TAIEX snapshot 作唯一主 Hero；三者不堆疊）
2. `MarketSnapshotCard`（TAIEX 主數字與合法小趨勢）
3. `DailyBriefCard`（同日最多三則，無資料不得補假文）
4. `MarketActivityCard`／`InstitutionalFlowCard`（次級短卡）
5. `SectorRotationList`／`HotTopicList`／`CandidateHealthList`（各自 persisted data 可用時）
6. 各區塊自己的日期、freshness、coverage、partial／stale／fallback／missing 與 disclaimer

Deterministic market cards 可保留 source-specific `as_of`／trade date；首頁指數只保留 TAIEX，TPEx／櫃買不再是 active product scope。盤中 TAIEX 可由 latest-price resolver 顯示 MIS，14:30 EOD 成功後切回正式 benchmark。Mart 子產品必須使用同一 `analysis_as_of`，不得把不同日期的最新版拼成「今日分析」。

單一 dependency timeout／error 不得造成永久 spinner；`mart_daily_brief` 未就緒只退化研究區塊，不讓 deterministic baseline 整頁不可用。

## 5.2 關注

以 authenticated owner 的 active watchlist 為中心，不顯示平台推薦榜，也不因搜尋／page load 觸發 scraper、Agent 或 LLM。

- 搜尋支援股票代號與中文名稱，使用 canonical stock-master search contract；第一層輸入 dialog 的主要動作明確標示「搜尋」，選定股票後才在設定／確認步驟使用「儲存」。
- 新加入受目前有效約 500 market universe 與最多 50 active distinct symbols guard 約束。
- 既有關注離開 500 時保留並標明狀態，不因 universe 變更自動刪除。
- 顯示 canonical name＋symbol、latest-price resolver 的 price／date／source／state、held state、target price、pending note／follow-up、bounded missing／stale。盤中只有此頁可見且 App 在前景時才每分鐘 revalidate；沒有 App demand 時不呼叫 MIS。
- add／remove／reorder、target price／note 都走 backend contract；Flutter 不自行建立 owner mapping 或 admission 規則。
- 點擊股票進 Stock Detail。

## 5.3 個股詳情

Primary content 固定順序（2026-10-11 視覺優先）：

1. `StockHeader`（現價、漲跌／幅大數字、行情日／來源）
2. 個人持股、成本與估值日期
3. `QuickPriceVolumeTrend`（真實短價量圖或資料不足原因）
4. `StockHealthCard`／五 specialist 狀態及一行摘要
5. 三項支持／三項風險
6. `StockChartNavigator`（價格／營收／EPS／估值／法人／事件圖表）
7. 個人筆記與待追蹤事項
8. `ChipsStatusCard`／`CompanyEventTimeline`
9. 可收合 `EvidenceAndSources`
10. `ComplianceDisclaimer`

`StockHeader` 顯示 latest-price resolver 的現價／正式收盤價與行情日；backend bounded 讀最近兩筆 canonical OHLCV，回傳 `previous_close/change/change_percent`。正值紅、負值綠、0／未知中性；Flutter 不另抓行情重算漲跌。

「我的持股」價格／market value／unrealized PnL／return 優先讀 owner-scoped `/api/v1/me/portfolio/quotes` latest-price valuation；`/journal/positions` 只作 operational fallback，避免 Stock Header 已更新但持股卡仍停在舊價格。未實現損益與百分比同樣採獲利紅、虧損綠。

短價量圖與圖表總覽入口屬 primary，不得僅在 Advanced 展開後才看得到。完整 K 線、Fact Pack、五 specialist 完整 artifacts、CEO report、參數及 provenance 可按需留 Advanced；未成熟 series 顯示具體資料缺口。

### 5.3.1 五 specialist

五 specialist 是 persisted Python／SQL／ML production outputs：

- Fundamental
- Valuation
- Quant
- Risk／Regime
- Event／Catalyst

User 只讀已持久化／validated artifact；plain-language 來自 structured output + SHAP／rules／templates，正常 path 不需要 LLM API。

每個 specialist 顯示與產品有關的：

- analysis/data as-of；
- status／freshness；
- 主要 metrics／drivers；
- missing／stale／partial；
- evidence／provenance；
- what changed（如有）。

模型版本、input hash、snapshot、完整 feature contribution 等工程資訊放 Advanced detail，不搶 primary UX。

### 5.3.2 On-demand CEO

CEO report 是 symbol-level persisted research artifact，不是 page-load narrator。

- 沒有有效 CEO report：顯示「尚無 CEO 分析」或 bounded unavailable；不得自動呼叫 LLM。
- 有 report：顯示 report as-of、產生時間、specialist freshness/material delta、status、主要 thesis／risks／unknowns。
- 只有 backend capability（例如 `ceo_analysis.request`）允許的使用者才顯示 `分析`／`重新分析`。
- 點擊後建立新的 immutable execution；舊 report 保留，不原地覆寫。
- request 需受 in-flight、quota／cooldown、profile／provider approval 等 backend guard；Flutter visibility 不代表 authorization。
- CEO 不計算或覆寫 canonical number，validator failure 顯示 structured partial／blocked。

### 5.3.3 歷史

歷史可依 `analysis_as_of`／execution／artifact version 檢視：

- facts／Fact Pack；
- specialist outputs；
- CEO reports；
- provenance／source references。

歷史 artifact immutable；不得借用最新資料回填舊 artifact 的 null／unknown。

未知／停用股票顯示 404；已啟用但資料或 specialist 尚未產生時顯示 bounded waiting／unavailable，不以 placeholder 冒充完成。

## 5.4 個人記帳與筆記

本頁是 P0 主功能，不依賴公開 Mart／LLM。使用 segmented control 切換「記帳／筆記」；進入記帳預設次導航為 **持股**，Ledger 次導航至少包含 **持股／紀錄／報表**。

### 5.4.1 Ledger／operational projection

- 交易與更正使用 append-only ledger／correction semantics。
- mutation 成功表示 ledger 已持久化；backend 同步更新 deterministic operational position projection，讓 shares／average cost／cash impact 可立即反映。
- Flutter 不計算 authoritative holdings、PnL、exposure、performance。
- Private Mart 仍擁有 canonical valuation／PnL／exposure／performance／reconciliation；若尚未追上，UI 明示 valuation date／checkpoint／pending。
- 正式 aggregate 若因 missing／stale／valuation-date mismatch 不可靠，backend withheld 並回 bounded diagnosis；Flutter 不忽略缺值自行加總。
- 「持股／紀錄／報表／筆記」次導覽固定在本頁上方；四格 holdings summary **只於持股**顯示。其他次頁不重複顯示，但仍共享 canonical position／valuation semantics、ledger version／as-of 與 freshness checkpoint。

Ledger／Holdings 一致性至少涵蓋 shares、cost／average cost、market value、unrealized PnL、realized PnL、YTD realized PnL、valuation date、as-of／data freshness、pending transaction／pending Private Mart。若不同 subview 的數值不同，UI 必須能表達其正式 freshness／as-of 差異；不能讓使用者看到無解釋的互相矛盾摘要。


**2026-10-12 持股獨立估值／視覺收斂（使用者核准，P0）：**
- **Personal Holdings Universe ≠ 500 檔研究池**。以 owner 的 append-only ledger／`private.current_positions` 做持股池唯一 membership；買進、賣出、股票股利、更正、作廢交易 commit 後同步重建 operational positions／ledger version，新增、加碼、減碼即進出持股池（0 股從 active 移往歷史，歷史交易不刪除），不需要等每天 500 檔 screening。持股行情 service 每次讀取 owner 最新 holdings symbols，且交易修改時使 quote/valuation cache invalidated；已授權外部券商資料**未同步交易前不能推知成交**。
- 股數與成本取同 owner operational checkpoint；價格讀來源授權且具日期與 provenance 的上市 TWSE／上櫃 TPEx 股票、ETF 正式收盤／可授權盤中行情；不因離開 500 檔而拒絕。00719B 為 TPEx 債券 ETF，不得套用 TWSE MIS 股票通道。先補合法 TPEx source/identity、held-symbol serving projection/持久化 latest-price，正式 Mart 再以同 checkpoint 計算損益。來源與交易不同步需顯示狀態；無可信價格不能推估價格／PnL，亦不得阻塞 operational shares/cost、已實現交易明細。
- **兩種更新**：交易 membership 隨 ledger 寫入即時變更；價格只在頁面前景交易時段按需 revalidate／手動更新，收盤後走官方 EOD 交接。避免使用每分鐘排程掃所有持股或逐檔 Iceberg/HTTP；TPEx 無已核准盤中來源時明示 EOD-only，不宣稱即時。
- **卡片同欄同指標**：第一視覺列左為個股＋股數＋價／成本，右為「未實現總損益（NT$）＋持有報酬％」；第二列集中「當日最新現價、每股漲跌／漲跌幅、現有股數的當日變動額」，日期／來源尾註。永不把「當日股價變動」與「持有至今累計損益」在同一水平列左右對稱。缺價時維持精簡卡、簡短原因，不能讓錯誤報錯巨幅擠掉 Hero。
- 對照 `reference/user-app-final/ledger.png` 與真實桌面截圖作 responsive convergence：只有一張市場持股市值主 Hero（未實現、報酬、年度已實現在內嵌次級欄），完整無價時保留精簡 Hero 並明示 missing symbols；下方緊湊股票列、近期紀錄；桌面主欄合理 max width，手機 390px 無 overflow；只有官方可追溯收盤序列才畫 mini sparkline，否則不畫假線。保持台股紅獲利／綠虧損與負號／狀態文字。
- 目前 Preview 截圖 00719B 缺價且全部總額 withheld、重算 Cloud Run dispatch 失敗、Hero 空白佔位過大，**現況 VISUAL FAIL / DATA PARTIAL**。資料 fallback 與 private recalc 派送故障必須獨立診斷；不得把第一個當成第二個的根因。完整開發後一次跑整合 tests＋GitHub Actions Release＋0% candidate＋自動 OAuth＋固定 Preview＋owner 真實桌面／390px 截圖，才可以轉 PASS。


### 5.4.2 持股

第一屏資料可用時，僅「持股」次頁優先顯示**持股市值主 Hero**、可驗證損益貢獻圖及下列四項有主次的摘要：

- aggregate market value；
- unrealized PnL／return；
- YTD realized PnL；
- valuation date／status。

未驗證 cash／其他資產完整性前，不能把持股市值稱為總資產，也不能用即時 quote 畫假歷史資產線。手機持股用較大字、紅漲綠跌的可掃描 card：canonical name／symbol、shares、market price／average cost、前一交易日官方收盤價、當日每股漲跌／百分比／以現持股數估算的價格變動額、unrealized PnL／return、price／valuation status。每檔都直接顯示未實現損益與百分比，正值紅、負值綠、0／未知中性；價格與未實現估值使用 latest-price resolver 回傳的 owner holdings valuation。operational shares／cost 與 canonical valuation／PnL 的資料時間仍須可判讀。

首屏優先呼叫 owner-scoped `/api/v1/me/portfolio/snapshot`：只從既有 PostgreSQL current_positions、latest-price resolver 的 last-success persistent state 及官方已發布 OHLCV serving projection 讀取，禁止 request-time MIS network／Private Mart 掃描；舊 API 僅供相容性／明確失敗備援。年度 PnL、交易歷史及重算狀態於首屏後另外載入。昨收以 PostgreSQL 已發布 OHLCV serving projection 批次讀取，不每檔逐一查 Iceberg。無有效昨收、報價 stale、參考日不合法或 checkpoint 不一致時，當日漲跌維持缺值；持股價格變動額不代表包含交易、費稅及除權息的實際當日交易損益。

持股分頁使用 latest-price resolver：盤中且 App 位於前景／持股分頁時每 1 分鐘 revalidate；13:30 後停止每分鐘輪詢，14:30 EOD handoff 時間到後只需成功讀取一次 persistent latest state，同一頁面生命週期內的 tab re-entry 不得重複自動抓取。13:30–14:30 若頁面已開啟，可保留最後 persistent state，並在 14:30 安排一次 handoff read；使用者明確按 refresh／交易異動後的必要同步不受此「tab re-entry 不重抓」限制。保留可見的「更新股價」手動入口，backend 僅對 authenticated owner 的目前 TWSE 持股執行 MIS refresh；手動刷新略過 60 秒 TTL，但仍有 10 秒 hard throttle。離開持股、App 進背景或市場關閉後停止輪詢；沒有 App demand 時不執行每分鐘行情工作。更新失敗保留 PostgreSQL last-success 並明示報價狀態，不以失敗回應覆寫 canonical EOD／Private Mart。

YTD realized PnL 必須有明確 display semantics：

- 當年度確定沒有已實現交易，且 canonical aggregate 可確認零值時，顯示 `0`；
- 資料不足、projection／Private Mart 尚待刷新、valuation/as-of 不一致時，顯示 bounded empty／unavailable／pending，而不是用假 `0` 補值；
- 已有已實現交易且 authoritative aggregate 可用時，不得長期缺值或完全不顯示。
- 只有 YTD/Private Mart 確認為 pending／stale、確實需要重算時才顯示「重新計算損益」；正常可用、確認為 0 或單純 API unavailable 時不顯示。手動重算只建立 authenticated owner 的 queue request，Flutter 與 User API request thread 都不直接寫 canonical Private Mart。同 owner 在 `QUEUED/RUNNING/CANCEL_REQUESTED` 期間按鈕 disabled；終態為 `FAILED/CANCELLED` 時顯示 safe reason 與「重新嘗試」，不得讓使用者無限空等。
- User UI 的 realized／unrealized PnL 與其報酬百分比統一採台股語意：獲利紅、虧損綠、0／未知中性；負值以減號顯示，不使用會計括號。

### 5.4.3 紀錄

資訊架構：`年度 selector → 按月份／按個股 → 可收合群組 → 單筆交易`。

- 年度 selector 至少涵蓋目前年度與前五年，並在同區直接顯示該年度 authoritative 已實現損益；多幣別、pending、資料不足不得硬湊單一數字。
- 「按月份」與「按個股」的每個群組預設收合；群組標題只顯示分類名稱與 **已實現損益**，不再堆買進支出、賣出回收、股利收入、交易筆數等摘要。
- 已清倉、目前不在持股清單中的股票仍可從歷史年度「按個股」查看。
- 月份／個股／年度已實現損益都必須由 backend／Private Mart 使用同一 moving-average、fee／tax 與 correction semantics 產生；Flutter 不從畫面交易自行加總 authoritative PnL。
- 展開群組後，單筆主視圖保持精簡：日期、event type、canonical name／symbol、適用時的 shares × price；完整 metadata 與 correction workflow 由 detail／「建立更正」承接，並提供「刪除交易」。刪除採 append-only reversal-only semantics：原始事件不做 SQL DELETE，新增 REVERSAL 後立即刷新 operational positions，並觸發 Private Mart 重算；若作廢買進／股票股利會使任一後續賣出失去足夠股數，backend 必須拒絕。

cash flow 與 PnL 不得混為同義。交易類型目前為買進、賣出、現金股利、股票股利；backend 負責 fee／tax rule 與 persisted rule/profile version。

切換到「紀錄」時不再顯示持股專屬四格摘要；Records 本身顯示 ledger transactions 與其 own as-of。若 transaction mutation 已成功而 aggregate 尚未刷新，需明示 pending／checkpoint，不得默默顯示舊摘要。

### 5.4.4 報表／refresh semantics

- 報表／圖表只讀 canonical backend／Private Mart aggregate，不由 Flutter 從局部交易或目前畫面資料自行重算正式 PnL／performance。
- 報表頁不顯示持股四格摘要，但使用相同 canonical／ledger version checkpoint；不得因 tab 切換維持不同版本的舊數值。
- 報表需顯示可判讀的 valuation date／as-of／freshness／pending／stale 狀態。若 aggregation 尚未追上 transaction／position projection，應顯示 bounded pending，而不是把舊數值當最新。
- 交易新增、修改、同步或 position projection 更新後，Holdings summary、Ledger summary、Records、Reports、YTD realized PnL 都必須進入一致的 refresh／invalidation 流程；舊 cache 不得長時間殘留而沒有 freshness 說明。
- Ledger mutation commit 後先由 ledger version mismatch 自動形成 stale/pending fence，API 只 enqueue authenticated owner，並由既有 `janus-private-pipeline` Cloud Run Job 的 owner-queue mode 處理；不呼叫會 revalue 全體 owner 的 `PrivatePipeline.run()`。不同 owner 可由 2–8 個 Cloud Run task 平行計算，同 owner concurrency 固定 1；shared Iceberg write 先用 advisory lock 序列化。scheduled full pipeline 保留為 durability／reconciliation fallback。
- 真正更新機制以 backend/runtime contract 為準。若採 batch，正式 evidence 應能指出 Job、Scheduler／trigger、頻率、source table、target projection、freshness SLA 與 failure 行為；若非 batch，應能追溯 event-driven／synchronous／materialization 的實際鏈路。UI 不得在 root cause 未查明前把 stale report 解釋成「正常等待批次」。
- Reports acceptance 必須追查並對齊 report API、transaction source、position projection、report aggregation source、DB table/view/materialized projection、cache TTL/invalidation 與 transaction 入帳後更新鏈路；最後以 evidence 判定 `implemented`／`partial`／`missing`／`blocked`。

### 5.4.5 Broker Profile／cash

私人 Broker Profile 可保存 current cash／cash strategy、fee discount multiplier、minimum fee 與 rule/profile version。現金優先由可稽核 cash ledger（opening/deposit/withdrawal/trade/dividend）推導；任何 CASH_IN／CASH_OUT／adjustment 仍須 append-only／audit。

目前 canonical cost method 維持移動平均法；未核准 FIFO 前不提供任意切換。scenario／預計交易不得直接寫正式 ledger／PnL。

### 5.4.6 Notes

一般筆記使用 revision model，可獨立存在或連結股票／交易；支援文字、股票、年份與 pending follow-up filter。修改保留歷史版本。

## 5.5 行情 read path

行情採 persistent DB-first latest-price resolver。Active market scope 為 **TWSE + TAIEX**；
TPEx／櫃買不再查詢、顯示或接受新 active coverage。

- regular session（09:00–13:30 Asia/Taipei）：可見的 Today／Watchlist／Holdings／Stock Detail 每分鐘最多 revalidate；backend 只有 persistent quote 超過 60 秒 TTL 才打 MIS。
- 13:30 後若同日正式 EOD 尚未到位：保留最後 MIS，狀態 `closing_pending_eod`。
- 14:30 EOD ingestion 成功並更新 serving projection：同日 `core_ohlcv`／TAIEX EOD 優先，狀態 `eod_final`。
- App 未使用、頁面不可見或 App 在背景：不因「每分鐘」規則產生 MIS request。
- Holdings 手動「更新股價」只刷新 owner 當前 TWSE 持股；不接受 caller 指定 owner，且有 10 秒 hard throttle。
- MIS 只寫 long-lived operational PostgreSQL last-success；正式 EOD serving 由 canonical Core projection 重建。MIS 絕不寫 canonical Core OHLCV。
- source、quote time、receive time、price date、state、final flag 必須可判讀；missing／stale 不補 0、不拿掛單價冒充成交。

## 5.6 資產與風險

- 顯示總資產、現金水位、持股、估值日期與缺價狀態；正式數值只讀 Private Mart。
- exposure 先以可讀比例／列表呈現；跨產業 membership 需版本化分攤說明。
- 年度績效顯示 realized PnL、dividend、fees/tax、trade count、XIRR status；無根、多根或資料不足不得顯示 0%。
- stress test 顯示 deterministic scenario 與 data as-of；Janus UI 不提供模型 runtime selector。

## 5.7 我的

- theme：light／dark／system；字體縮放跟隨系統。
- 投資屬性可含 risk tolerance、horizon、primary goal、minimum cash ratio；提供給外部 AI 前需明確 opt-in。
- 提供 Janus 私人資料匯出與可稽核刪除；`CLEANUP_PENDING` 不得顯示完成。
- 不放方案定價、公開績效排行榜、預測戰績或券商同步控制。

## 5.8 Research Context（Planned）

在既有資訊架構中增量呈現：

- market regime／deterministic signal summary；
- research thesis supporting／invalidating evidence；
- candidate／strategy state；
- 可用時的 supply-chain exposure／signal；
- portfolio impact；
- provenance／freshness／missing data。

不另建聊天面板；Janus ResearchContext 由 bounded API／MCP 提供。private section 仍受 owner auth 與明確授權。

## 5.9 Loading／效能

- 主 navigation 頁保持 persistent state；切頁不無條件重送全部 API。
- 不在 widget `build()` 內建立會因 rebuild 重送的 request future。
- composite screen 使用 section-level loading／partial；已持久化資料可先顯示再 revalidate。
- Ledger 首屏不得等待未啟用分頁：持股只載必要 core state 與 latest-price；紀錄／報表／筆記依切換 lazy load，頁內相同 GET 重用 request future，避免最慢 fan-out request 阻塞整頁。
- backend latency root cause 必須先量測 auth、DB、Iceberg、fan-out、p50／p95；沒有 evidence 不預設 CPU／RAM／index 是原因。
- high-frequency read 優先 bounded DB read model／cache／connection pool；GET 不做與讀取無關的 retirement write。

## 5.10 數值顯示

- 使用共用 typed formatter，不讓各 widget raw interpolation。
- 股價語意固定 2 位小數。
- 金額、股數、比例依產品契約四捨五入整數、comma 千分位；負數用括號。
- symbol、日期、version、hash、decimal trade input 保留原語意。
- targeted／golden regression 覆蓋主要格式。

## 5.11 跨專案邊界

Janus User App 不提供 Chat／Ask Janus／provider／runtime／MCP／Skills／approval 產品入口。generic conversation UI 由 omniAgent 持有；Janus 透過 authenticated bounded API／MCP 提供投資 context。

任何 UI completion 都必須依真實 backend capability 呈現；missing／stale／partial／unavailable／blocked 不得用 sample／placeholder 補成成功。
