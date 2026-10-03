# 2026-10-02 Admin／User／Routing／Provider 決策總結

2026-10-03 整理註記：本文保留 2026-10-02 的產品決策；第 7、16 節 runtime／completion 敘述為當時 checkpoint，不取代最新 `status.md`／`todo.md`。補資料第一版已結案，五分析師目前版本資料前置已滿足；Provider 已有 bounded dev execution，整體 auth／免費資格／額度／target 情境及每日自然鏈路驗收仍未完成。本文第 15 節是 backlog 內部依賴建議，正式跨工作組順序只以 `todo.md` 為準。

本文件整理 2026-10-02 對話到目前為止已確認的產品、資料、治理與工程決策。它是 active decision／planning note，不是 implementation completion 證據；目前實作與完成狀態仍以 GitHub `main`、tests／CI、deployment、live runtime 與 integration evidence 為準。

## 1. 執行順序與 TODO 約束

- 目前 foreground queue **不變**：`WBS-5-MART-AI-PROVIDERS` 仍是下一個／當前優先 WBS。
- 本次 Admin、User App、行情 routing、storage monitor、Private Mart checkpoint、效能與操作池需求屬於已確認 backlog／contract extension；除與 `WBS-5-MART-AI-PROVIDERS` 直接相關的 provider routing／approval 外，不應插隊改變 foreground WBS 順序。
- `WBS-5-MART-AI-PROVIDERS` 未完成前不得因 router code、credential probe、單元測試或 deploy 成功就宣稱五分析師每日 workload 完成；仍需 GCP dev 真實 execution、target integration、validator、artifact readback、auth lifecycle 與 bounded failure evidence。
- 任何 source/provider 若尚未通過授權、free-tier／billing 或 live acceptance gate，只能標記 `candidate`／`blocked`／`partial`，不得文件先行寫成 production-ready。

## 2. Admin 首頁：「需要處理的事項」

現有首頁 priority area 的方向正確，但目前若只呈現數字而無法理解或處理，產品上不足。

要求：

- 非零卡片必須可點入 filtered 明細，至少回答「哪一筆、為什麼、最後更新、目前狀態、可否處理」。
- 只有 backend 判定 retryable／rerunnable 的項目才顯示 action；不可把 generic count 當成操作能力。
- 成功 execution 不佔主要空間；failed／partial／retrying／blocked／review-required／invalid 才進 priority area。
- partial success 不得包裝成 full success。
- 重試／重跑建立新 execution，保留舊 execution、lineage、trace、reason 與 audit。

## 3. Admin Job Control Center

在既有「批次」頁擴充，不建立第二套 job system。

- 列出 master／batch controller 以及其 dispatch 的 ingestion、Mart、五角色 AI、Private Pipeline、cleanup／maintenance 等子工作。
- 每列顯示 effective schedule／trigger、latest execution state、last update、latest success、started／finished，以及安全的 manual rerun。
- 預設明細顯示最近 3 天 execution／occurrence timeline；更早歷史仍可透過日期範圍／cursor 選取，不因 UI 預設視窗縮短而刪除。
- controller／child lineage、Cloud Run execution reference、safe failure reason 可 drill-down。
- manual rerun 必須走 backend allowlist、idempotency／duplicate guard、dependency／exclusive guard 與 audit；Flutter 不直接操作任意 Cloud Run job、checkpoint 或 storage object。
- 「enqueue 成功」不等於 workload 成功。

## 4. Iceberg／GCS Storage Monitor

Admin 增加 storage／maintenance operational monitor，涵蓋 Stage、Core、Mart 與必要的 Private Mart metadata。

至少顯示：

- active snapshot／manifest 數；
- live object count／live bytes；
- 最近 maintenance time／result；
- snapshot/reference protection；
- retention window；
- planned／actual reclaimed object／bytes；
- anomaly／growth warning；
- Mart report index 數；
- publication 精確引用的 Mart snapshot 數；
- protected retention date range。

示例資訊可類似：「15 Core snapshot manifests；Mart publication index 103 reports、23 exact-referenced Mart snapshots，retention 2027-09-10～2027-09-22」，但 UI 數字必須來自 persisted telemetry／index，不能 hard-code。

重要語意：

- `live objects／active bytes` 與 cloud billable storage 必須分開。
- billable bytes 若沒有 non-current／soft-delete／version evidence，顯示 `unknown`，不可用 live bytes 冒充帳單容量。
- Admin page load 不應即時 enumerate 整個 GCS bucket；優先讀 maintenance／retention 已持久化的 telemetry。

## 5. Private Mart checkpoint／Private Pipeline

Admin 顯示完整 Private Pipeline operational state，但不暴露使用者交易正文／持股內容。

至少顯示：

- `private.pipeline_checkpoints` 的 current checkpoint／`change_id`；
- checkpoint `updated_at`；
- 最新可見 ledger／change version；
- 可可靠計算時的 backlog；
- last execution／result；
- latest Private Mart valuation date；
- lag／pending deletion／revaluation metadata（若可可靠取得）。

手動執行只觸發安全的 pipeline/job/controller action；**不可直接人工修改 checkpoint**。

Private Pipeline 實際有效啟動方式與 schedule 以 GitHub main + live Scheduler／batch-controller evidence 為準；若 migration 期間 direct Scheduler 與 controller 同時存在，Admin 必須如實顯示並先完成 duplicate／cutover 驗證。

## 6. Routing：共同治理原則

行情來源與 AI provider 都改為 backend versioned routing contract；Admin 只負責調整已核准來源／provider 的順序。

共同規則：

- routing 設定需版本化，保存 actor、timestamp、before／after 與 optimistic lock。
- 未核准、credential 不可用、paid gate 未授權或 health 不合格的 entry 可顯示 blocked／disabled，但不得因拖到第一順位就自動啟用。
- 每次 execution／request 必須保存 effective route、routing config version／hash、實際 source/provider、attempt 與 fallback reason。
- execution 啟動後固定 immutable routing snapshot；Admin 後續改順序不得改寫舊 execution 的 replay／lineage。
- fallback 只能在明確可 fallback 的 failure class 發生，例如 transport failure、timeout、rate limit、provider unavailable、auth unavailable／capacity；schema／validator／grounding failure 不應藉由換 provider 靜默繞過。
- 若沒有可用 approved route，fail closed；不得產生 placeholder。
- 排序不等於授權；新付費 API／model／subscription 仍需使用者明確授權。

## 7. 五分析師 AI Provider Routing

使用者指定的預設順序：

**Codex CLI → OpenRouter → Gemini**

- 五角色預設共用同一 global route；per-role override 僅放 Analysis Profile 進階設定，沒有明確需要前不複製五份設定。
- `WBS-5-MART-AI-PROVIDERS` 的 provider router、attempt audit 與 immutable route snapshot 屬本 WBS acceptance。
- all-five roles 仍只讀公開 immutable Fact Packs／evidence，不把私人持股數量、成本或 owner mapping 寫回 public Mart／provider artifact。

### 7.1 2026-10-02 Credential／免費資格 live probe 狀態

既有 `janus-runtime-bundle` 中三個 credential 已做安全 probe；只驗證 key 是否存在、API 是否可認證，不輸出 secret 值。

- **Fugle**：`fugle_api_key` 存在；`2330` quote probe HTTP 200。Credential／基本 API 可用。
- **Gemini**：`gemini_api_key` 存在；models endpoint HTTP 200，可見 `generateContent` models。這只證明 credential/model discovery 可用，**不證明該 key 所屬 project 一定沒有 billing／一定符合 Free Tier**。
- **OpenRouter**：`openrouter_api_key` 存在；key endpoint HTTP 200；metadata 回報 `is_free_tier=false`。因此不能直接標記 approved-free。

目前免費 gate：

- Fugle：可進免費 source approval；限制於 owner-private display／bounded latest-quote cache，不核准 public redistribution。
- OpenRouter：仍需實際 `$0`／free-only model route live probe；runtime 必須 `free_only`，若找不到 prompt／completion 都為 `$0` 的 route 即 fail closed，不得 fallback 到付費模型。
- Gemini：在證明 Free Tier／billing 狀態前，generation 維持 blocked；model-list probe 不等於 free entitlement acceptance。
- Codex CLI：已有先前 bounded live evidence，但本 WBS 的整體 auth lifecycle、target/provider same-execution 與自然批次仍未完成。

## 8. 行情來源 Routing

使用者指定的目標預設：

- 盤中：**Yahoo → Fugle realtime → TWSE MIS**
- 盤後：**TWSE published/EOD → Fugle → Yahoo**

但 effective route 只使用已核准來源：

- **Fugle**：API key 已 live probe 成功，可進免費 approval；核准範圍限私人展示與 bounded cache，需保留 source／quote timestamp／received timestamp／session／freshness／status provenance。
- **Yahoo**：目前不可核准為 Janus 自動化 runtime source；在未取得明確授權前維持 `blocked`，Admin 可顯示目標順位但 effective route 必須跳過。
- **TWSE MIS**：既有 Janus runtime 已有 MIS 實作與 bounded acceptance；若要把網站 endpoint 的自動 backend 擷取／持久化擴張成新的用途，仍需依 source authorization contract 審查，不因既有 UI 能用就自動擴大授權範圍。

建議新增 `QuoteRouter`：

- 依 market session 選擇 route；
- per-provider timeout／bounded retry；
- source authorization／quota／health gate；
- latest success 持久化到 operational DB read model；
- DB-first response，再 refresh source；成功後持久化並更新 UI；
- intraday operational quote **不得覆寫 canonical Core OHLCV／Private Mart EOD valuation**；
- 如需研究/audit，可非同步 append 到 Iceberg，但 interactive UI 不等待 Iceberg。

## 9. Watchlist／個股搜尋／個股研究資訊

### Watchlist

- 搜尋必須支援股票代號與**中文名稱**。
- 建議共用單一 canonical stock search endpoint/component，例如以 stock master 回傳 canonical name＋symbol＋active／Liquid-500 eligibility；Watchlist 與交易表單共用。
- 搜尋不得觸發 scraper／Agent／LLM。

### 個股詳情

- 不另開「建議」頁，整合到既有 stock detail。
- 現有 `StockHealthCard`／`AiPlainLanguageCard`／why／risk／evidence 架構延伸顯示研究資訊、資料日期、confidence、status、provenance 與 disclaimer。
- 不把 confidence 當獲利機率，也不得把 AI prose 呈現成保證性投資建議。

## 10. User App 載入效能

目前「spinner 很慢」先視為結構性 latency 問題，不先歸因於 CPU／RAM。

高優先候選：

- Flutter 主導航 page recreation，切頁可能重建 state／future；
- 在 widget `build()` 內直接建立 `Future.wait(...)`，rebuild 可能重新發 request；
- Stock Detail／Today／Profile 等 API fan-out；
- full-page spinner 等待全部 dependency，而非 section-level loading；
- PostgreSQL repository 每個 method 以新 `psycopg.connect()` 建立連線，未見 explicit pool；
- private portfolio read path 直接讀 Iceberg，interactive latency 偏高；
- watchlist GET path 執行 retirement UPDATE，可能是不必要的讀路徑 write／lock；
- Cloud Run `min-instances=0` 可降低 idle cost，但會造成 idle 後 first-request cold start；它不能解釋所有頁面都慢。
- Google ID-token auth path目前未見 application-level explicit cache，應量測 auth duration／cert fetch，不可未量測就宣稱每次一定遠端抓證書。

優化順序：

1. 先加 request／dependency latency instrumentation，確認 p50／p95、DB connect、auth、Iceberg、各 endpoint fan-out。
2. Flutter 主頁改 persistent pages（例如 `IndexedStack`／keep-alive），future/state 只初始化一次，refresh 明確觸發。
3. stale-while-revalidate／DB-first cached read；避免全頁 spinner。
4. section-level loading／partial；單一 dependency timeout 不阻塞整頁。
5. PostgreSQL connection pool／query profiling；有 evidence 才調 index／autovacuum／resource。
6. 對高頻 composite screen 評估 bounded aggregate/BFF endpoint 或 operational read model，避免 interactive path 直接反覆掃 Iceberg。

不得在沒有 `EXPLAIN ANALYZE`／pg stats／runtime metrics 前宣稱 DB index、bloat、CPU／RAM 是 root cause。

## 11. 記帳／筆記：第一頁、行情保存與 refresh

- 記帳／筆記第一頁預設切到 **持股**，不是紀錄。
- 页面先讀 DB 中 last successful quote／valuation read model，立即顯示既有資料與 timestamp，再非同步 refresh。
- refresh 成功後持久化 source／quote_at／received_at／session／freshness，再更新 UI。
- refresh 失敗保留 last success 並明示 stale／refresh error，不把舊值改成 0。
- top-right refresh 保留，和自動 refresh 共用同一 backend route／policy。

## 12. 交易後即時持股更新

使用者要求「交易 API 成功後立即看到持股變化」。這與目前「等待 Private Mart 批次」契約不同，應採雙層模型：

- ledger 仍 append-only 並同步持久化；
- backend 同 transaction／可稽核流程更新 synchronous operational position projection（shares、average cost、cash impact 等 deterministic state）；
- Flutter 不自行計算權威持股；
- canonical valuation／PnL／risk／exposure 仍由 Private Mart 產生，UI 顯示其 valuation date／checkpoint／pending status；
- Private Mart 後續做 reconciliation／history，不因 operational projection 而失去 canonical role。

## 13. 「操作池」／券商交易設定

在記帳／筆記新增可編輯私人交易設定：

- current cash／operating cash；
- broker fee discount multiplier，例如 `0.4` 代表券商手續費按標準費率的 40%；
- minimum broker handling fee；
- 必要時保存 commission rule/profile version。

治理要求：

- trade UI 不要求使用者每次手填 fee／tax；後端根據 instrument／event／day-trade／rule version 計算並保存 exact fee／tax／rule version，前端可 preview。
- 現金最好由可稽核 cash ledger（opening balance、deposit／withdrawal、trade、dividend）推導，而不是只有一個可任意覆寫的 free-floating cash number；若新增 CASH_IN／CASH_OUT 或 cash-adjustment，需另有 append-only／audit contract。
- broker discount 只是輸入與 fee rule，不得改變 canonical PnL accounting contract 的歷史重現性。

## 14. 數值格式

全 User UI 掃描並統一 typed formatter：

- 股價語意：現價、估值、平均成本、成交單價、目標價等固定 **2 位小數**；
- 金額、股數、比例：依現行產品 contract 四捨五入整數＋comma 千分位；負數用括號；
- 股票代號、日期、版本、hash、十進位交易輸入保持其原語意，不套會計格式。

應集中為 `formatPrice`／`formatAmount`／`formatShares`／`formatPercent` 類型化 formatter，並以 targeted／golden regression 防止 raw numeric interpolation 回歸。

## 15. 建議實作順序（不改變 foreground queue）

本段是 backlog 依賴順序，不是把它們插到 `WBS-5-MART-AI-PROVIDERS` 前面。

1. 完成目前 `WBS-5-MART-AI-PROVIDERS`：OpenRouter free-only probe、Gemini free-tier／billing gate、provider routing live acceptance、target/provider same execution、auth lifecycle。
2. User latency instrumentation／root-cause profiling。
3. Flutter persistent page state／request cache／DB pool等已量測確認的 P0 latency fix。
4. persisted last quote read model＋Quote Router。
5. transaction synchronous position projection。
6. Admin Routing：AI providers＋quote sources，versioned reorder／audit／effective snapshot。
7. Private checkpoint＋Job Control Center 完整化。
8. Iceberg／GCS storage monitor。
9. Watchlist／trade 中文名稱 autocomplete 共用 search。
10. 操作池／fee-tax rule。
11. 數值 formatter 全面收斂。
12. User Final Visual Convergence 與跨頁 live acceptance。

## 16. 目前 completion boundary

截至本文件建立時：

- Credential probe：Fugle／Gemini／OpenRouter **已完成**。
- Fugle source approval：**可進核准，但正式 control-plane review/effective runtime 尚需 evidence**。
- OpenRouter free-only：**partial／pending live `$0` request acceptance**。
- Gemini Free Tier：**blocked pending billing/free-tier confirmation**。
- Provider router code／targeted tests：已有 implementation/test evidence；**不等於 dev runtime acceptance**。
- Provider routing dev deployment／五角色完整 live acceptance：**尚未完成／不得標 done**。
- Admin effective routing UI：**尚未完成**。
- Quote multi-source router／persisted DB quote：**尚未完成**。
- User performance remediation、instant position projection、operation pool、storage monitor、Private checkpoint UI：**尚未完成**。

後續每個 WBS／UI slice 仍依 `PROJECT_RULES.md` 的 implementation＋tests＋CI＋deployment＋runtime＋integration evidence 判定完成。