# Janus WBS 6 — API、Flutter 與 Admin

## WBS 6 — FastAPI、Flutter User 與 Admin

### 6.0 目前使用環境

- 目前 GCP `dev` 是 Janus 個人使用階段的真實平行上線環境。WBS-6 的 API、Flutter、Admin、ChatGPT MCP 等能力，只要各自通過必要的 auth、data、runtime 與 integration acceptance，即可在 dev 真實使用；不需要等待另一套 Production 環境或 Pilot 結束。
- localhost／mock／fixture 可做快速開發與 fault injection，但不能代替宣稱完成的 GCP dev URL、真實 OAuth／owner、persisted data、API／MCP／provider 與 Flutter／Admin real-path evidence。
- 未來 `Production` 是多人／對外、HA／SLA、正式營運隔離等升級層級；文件中 `Production Profile` 則是 Analysis Profile 的版本狀態名稱，兩者不可混為同一個環境資格 gate。

### 6.1 FastAPI

- 擴充 WBS 4J 建立的最小 `services/api` FastAPI app；將現有 WSGI handler 逐路由遷移並以 contract tests 保持既有 Admin 行為，完成後才移除 WSGI boundary。
- `/api/v1/public/*` 提供 health、daily brief、sector rotation、topics、candidates、stock health、history、Kline、events。
- `/api/v1/me/*` 提供交易、筆記、關注股、positions 與年度 PnL；Janus Chat API 已在 2026-09-23 hard split 部署中移除；私人資料與已套用 migrations 保留，未隱含搬移或刪除。身分只取自驗證內容，不接受 client 指定 `user_id`。
- `/api/v1/admin/*` 保留控制面能力；public、private 與 admin router 分離 response model、auth、CORS、rate limit、IAM 與 audit。
- cursor／pagination、safe error、404 waiting state；不公開 raw payload、blocked、secret、traceback 或 private artifact reference。

### 6.2 Flutter User App

- 建立 `apps/user_app`，使用 Flutter Material 3 與平台原生元件；不先引入第三方 state／UI 套件。
- Janus User App 依 `../ui.md` 提供今日、關注、記帳／筆記與我的；沒有 Chat／Ask Janus 導航。generic 對話介面由 omniAgent client source 持有，尚未切換 live deployment。
- 個股頁 primary content 依 `../ui/user-app.md` 與 Final Visual Contract：`StockHeader` → 個人持股／成本／估值日 → 筆記與待追蹤 → 健康度 → 白話 AI 摘要 → why／risk → 籌碼 → 公司事件 → evidence／disclaimer；K 線、Metrics、Fact Pack、五角色、CIO 與完整 provenance 預設收在進階資料。
- 個人工作台提供關注股、手動交易、一般筆記、歷史明細、持股、已實現／未實現與年度損益；正式結果只讀 Private Mart，不在 Flutter 或模型內重算。
- 「我的」提供 Janus 私人資料匯出與可稽核刪除流程；cutover 前仍需涵蓋 Janus 持有的歷史 assistant 資料，不提前宣稱 omniAgent data migration 完成。
- 支援 light／dark／system theme、phone／iPad／web responsive、VoiceOver／TalkBack 與至少 44×44 target。
- User App 不顯示 Admin 導覽、公開績效排行榜、下單或券商同步控制。
- UI 驗收必須呈現真實 backend 已知狀態；missing／stale／partial／unavailable／blocked 不得用 mock、sample 或 placeholder 補成成功畫面。

### 6.2.1 `WBS-6-USER-FINAL-VISUAL-CONVERGENCE` — User App 最終 presentation acceptance

本切片是 **presentation acceptance overlay**，不取代資料、API、Mart、Private Mart 或 auth 的既有 WBS，也不表示四頁背後所有 capability 已完成。它定義 User App 在相關 dependency 逐步完成後必須收斂到的最終畫面與 cross-screen acceptance。

權威來源：

- `../ui/user-app.md`
- `../ui/reference/user-app-final/README.md`
- 固定 binary path：`today.png`、`watchlist.png`、`ledger.png`、`stock-detail.png`

四張 PNG 尚未 commit 前，只有 contract 與 path reservation 成立，不得宣稱 visual reference binary 已到位。

#### Today Final

- 保留 deterministic market baseline first：加權／櫃買、market activity、institutional 不依賴 Mart／LLM 才能顯示。
- Mart 可用時疊加 market regime、最多三則 Daily Brief、sector rotation、topics、candidate health；未就緒只退化相應區塊。
- section 各自呈現 date／freshness／coverage／partial／missing；任一 request timeout／error 不得造成永久 spinner。
- 候選股可進 stock detail；Flutter 不自行計算 canonical score。

#### Watchlist Final

- 以 owner-scoped active watchlist 為中心，不顯示平台推薦榜。
- card 顯示 canonical 股票名稱＋代號、recent persisted price／date、held state、target price、pending note／follow-up 與 bounded missing／stale。
- add／remove／reorder、有效 500 檔 admission、50 active distinct symbols quota 與離榜保留語意維持 backend contract。
- 點擊 item 進入 stock detail；不得因 presentation target 自行啟動 scraper／Agent／LLM。

#### Ledger Final

- 第一屏優先 aggregate market value、unrealized PnL／return、YTD realized PnL、valuation date／status。
- aggregate withheld 時顯示 bounded diagnosis，不由 Flutter 忽略 missing/stale position 後自行加總。
- 次導航「持股／紀錄／報表」；持股手機版使用 card hierarchy。
- 紀錄維持 `年份 → 月份 → 單筆交易`，買進支出／賣出回收／股利收入／已實現損益分開。
- 交易 append-only／correction semantics 不變，寫入成功後顯示「交易已儲存，等待投資組合批次更新」。

#### Stock Detail Final

primary content 順序固定為：`StockHeader` → 個人持股／成本／估值日 → 筆記與待追蹤 → `StockHealthCard` → `AiPlainLanguageCard` → 三項「為什麼」／三項「要注意什麼」 → `ChipsStatusCard` → `CompanyEventTimeline` → 可收合 `EvidenceAndSources` → disclaimer。

K 線、Fact Pack、五角色 validated analysis、CIO、估值指標與完整 provenance 屬 advanced section，必須位於 primary content 之後。Fact Pack／roles／CIO 等 dependency 未完成時不得用 sample／placeholder 冒充可用。

#### Cross-screen Acceptance

宣稱本 WBS 完成時至少必須：

- 四張 PNG binary 已存在固定 repository path，且 sample values 明確僅作 illustrative；
- Flutter targeted／golden／screenshot regression 覆蓋四頁主要 hierarchy 與 loading／empty／error／partial／stale／missing states；
- 390×844 級手機 viewport 無 overflow，section order 與 final visual contract 一致；
- 四頁使用一致的 Material 3／cyan-teal／card-based presentation language，不重新發明另一套 User App 資訊架構；
- GCP dev 真實 authenticated URL、真實 owner、persisted backend data 完成 screenshot／browser acceptance；
- UI 不 hard-code mock price、PnL、AI prose、logo 或其他 sample result；
- backend capability 未完成時維持 bounded unavailable／hidden，partial 不得包裝 full success；
- final visual acceptance 與資料／auth／runtime acceptance 必須同時成立，圖片或 build 成功不能單獨構成完成。

### 6.3 Admin UI

WBS 3 已負責 Stage／Core Data Operations 的可操作閉環；本節延伸公開 Mart、governance、AI operations 與 Admin runtime presentation。唯一 active Admin frontend 是 `apps/user_app` Flutter／PWA；2026-10-02 已退役的 legacy static HTML／JS Admin 不再作 fallback 或 parity gate，歷史座標只保留在 archive。

Flutter 隱藏控制不是 security boundary。`/api/v1/admin/*` 每次 request 仍由 backend enforce Admin authorization；User token 不得假設可呼叫 Admin API，User／Admin token audience 差異必須在 implementation WBS 驗證。

2026-10-03 Admin scope 依 `../decision-2026-10-03-admin-ui-scope-and-governance.md` 與 `../ui/admin.md` 收斂：**不重做整個 Admin、不取消既有 `個股`／`市場資訊`／`AI 分析`。** 主導覽目標為：

- `總覽`
- `批次`
- `個股`
- `市場資訊`
- `AI 分析`
- `資料治理`

`資料治理` 取代目前 `進階管理` placeholder；程式未完成 rename 前不得因文件改名宣稱功能完成。保留「資料營運中心」名稱與單面板 navigation；未選分頁不預抓大型 detail。

#### 6.3.1 既有 accepted baseline

以下既有成果依目前 status／runtime evidence 保留，不因 UI scope 收斂重寫成未完成：

- Flutter Admin shell。
- actionable Overview／Batch 基礎能力。
- Stock Workbench 基礎能力。
- persisted execution detail、retry classification、retry lineage 與 source health／Mart persisted read 能力。
- 週六資料品質檢查的 Admin Overview read path。

這些舊 acceptance 不等於新的 operational convergence、Token-first specialist management、On-demand CEO controls 或資料治理頁已完成。

#### 6.3.2 Admin operational convergence

Active scope 以 TODO 順序執行，UI 契約見 `../ui/admin.md`：

- `總覽`：維持 actionable-exceptions-first，只補今日批次、最近 DQ、storage/retention anomaly 與需要處理項目；正常 execution 不佔主要畫面。
- `批次`：以簡單表格／清單顯示 backend effective job／occurrence、schedule/trigger、latest state、duration/last update、latest success，以及 `查看`、安全 `重試`／`手動執行`。預設最近 3 天，保留更早 bounded history；不要求大型 DAG。
- 現行 controller 固定批次為 `ingestion`、`data-supplement`、`mart`、`data-quality`、`private`、`core-cleanup`、`mart-cleanup`。未來 500 screening、dirty specialist update、monthly retrain／reconciliation、On-demand CEO execution 只有實際 implementation/runtime 存在後才顯示。
- `資料治理`：單一精簡頁顯示 Stage/Core/Mart/必要 Private 摘要、active retention、coverage/freshness/DQ、live objects/active bytes、maintenance、protected references 與 anomaly；Public retention 依 `../spec/retention-governance.md`，Private 無核准 contract 時顯示 `未定義/unknown`。
- 第一版不要求 OpenMetadata、DataHub、Airflow、Kestra、Prefect、第二套 scheduler/control plane、metadata catalog、lineage graph、大型 chart 或新 canonical store；現有 Material 元件能完成時不新增第三方 UI framework。
- 一般 Admin 不得瀏覽使用者交易正文／持股內容；Private operations 只顯示必要、去識別化／aggregate metadata。

#### 6.3.3 AI 分析／Analysis Profile

`AI 分析` 保留獨立主功能，依 2026-10-03 Token-first specialist + On-demand CEO 決策：

- Specialist production 主路徑為 Python／SQL／ML，Admin 管 champion/model/version/evaluation、dirty dependency/reuse/reconciliation、monthly retrain/calibration evidence 與 blocked/partial 狀態。
- Codex CLI／OpenRouter／Gemini route 只適用 authorized manual On-demand CEO／rare escalation，不再代表五 specialist daily route。
- `WBS-6-ADMIN-ANALYSIS-PROFILE` 管 specialist model/evaluation profile、CEO provider/model/profile、DB-backed user capability、quota/cooldown、usage/cost 與 audit。
- 重新分析建立新 immutable execution/report，不覆寫舊 artifact；Flutter visibility 不可代替 backend authorization。

#### 6.3.4 個股／市場資訊／Routing

- `個股` 保留現有 Stock Workbench 與後續 dataset health、gap repair、history 等既定工作；舊 artifact immutable，不以 raw JSON 作主要 UX。
- `市場資訊` 保留 500 universe／市場資料營運視角；深度追蹤只呈現去識別化 symbol demand，不顯示 user-to-symbol 關係。
- Provider／market-source priority 仍是 backend versioned routing contract，不由 Flutter hard-code。CEO route 放在 `AI 分析` 進階設定；market source route 放在 `市場資訊` 或 `資料治理` 詳細設定，不另建高複雜度主頁。

### 6.4 驗收條件

- UI 不自行計算後端分數。
- Flutter 不自行計算正式損益；User／Admin navigation and workspace state are separated, while backend authorization, token audience and CORS remain enforced independently.
- empty／unavailable／partial／fallback／blocked 語意正確。
- 未啟用股票 404；已啟用無資料顯示等待批次。
- 詳細驗收依 `../ui.md`。
- User App presentation／layout／visual regression 另依 `../ui/user-app.md` 與 `../ui/reference/user-app-final/README.md`；四張 PNG binary 未 commit 或 cross-screen live screenshot acceptance 未完成時，不得宣稱 Final Visual Convergence 完成。
- Admin operational convergence 需依 `../ui/admin.md` 驗收，包含最小 UI、真實 effective batch/job、retention/storage telemetry、Admin auth 與 browser acceptance；文件 rename、Flutter build 或 API 200 不等於完成。
- tab／navigation 具鍵盤操作與可還原 state；重載後保留所選分頁，未選面板不重複抓取大型 details。
- 詳細 User／Admin 驗收依 `../ui.md`；今日頁所有卡片必須使用同一 analysis-as-of，個人工作台通過交易更正、筆記 revision、關注異動與跨使用者隔離測試。
- 對宣稱 live accepted 的 UI 流程，至少要有目前 GCP dev 真實 URL／runtime、真實 auth／persisted backend 與實際互動 evidence；mock/sample 只可補測，不可獨立完成驗收。

### 6.4.1 Planned Admin analysis semantics

- Specialist rerun 依 active dirty dependency graph：Core/PIT input、feature/engine/model version 改變時只 invalidate 受影響 symbol/role；無變更 reuse。不得回到每日五個 LLM workers。
- 新月營收／財報只更新受影響 Fundamental/Valuation；新 EOD price 更新 cheap valuation/Quant/Risk；新 event 只更新 Event。每月 reconciliation 檢查 missed invalidation、orphan artifact、cache identity 與 model version。
- Specialist change 只標記 CEO report freshness/material delta，**不得自動觸發 CEO LLM**。
- CEO Analysis 只由具 `ceo_analysis.request` 或等價 capability 的 authorized user 明確 request；重新分析建立新 immutable execution/report。
- Analysis Profile 管 specialist champion/model/version/evaluation 與 CEO provider/model/profile。Profile 修改建立新 version；禁止覆蓋舊版，rollback 也建立 audit／version lineage。
- `Production Profile` 是模型／分析設定的 active/released profile 狀態；canonical facts、publication authority 與環境 release status 仍各自獨立。

### 6.5 Janus ChatGPT MCP Connector

ChatGPT connector 是 P1／parallel-live dev capability，採 existing `janus-api` remote read-only MCP path，預設不新增 Cloud Run service，且不成為 Janus 未來 Production topology 的 prerequisite。只要 MCP 自身通過 real-path acceptance，即可在目前 dev 真實使用；它只可讀已核准 public market data、owner-scoped private investment data 與 bounded journal／ledger data；不得接受任意 SQL、table、URI 或 client-selected owner，也不得提供 mutation。

#### `WBS-6-CHATGPT-MCP-CONTRACT`（【Sol】）

- Scope：確認當時 OpenAI Custom MCP／OAuth requirements、Janus auth compatibility、三個 logical tools、read-only classification、owner binding、shared bounded query、public／private allowlist、output／provenance／quota contract。
- Acceptance：無 arbitrary SQL／URI／table／owner input、無 mutation、重用既有 Janus data readers、auth compatibility 有明確 verdict；任何新 auth／GCP component 只記為 blocked decision，不部署。
- Dependency：相關 Core／Private Mart／journal owner-scoped reader contract 已被理解；不依賴完整 `WBS-4C-ACCEPTANCE`。

#### `WBS-6-CHATGPT-MCP-ADAPTER`（【Sol】）

- Blocked until `WBS-6-CHATGPT-MCP-CONTRACT` complete；這是 MCP 本身的 dependency，不是整個 Janus dev 使用資格 gate。
- Scope：在既有 `services/api`／`janus-api` 實作 remote read-only MCP adapter，重用 shared bounded query layer，完成 authenticated owner mapping、tool discovery／call、bounded error／timeout／rate／output limit，且不產生不必要的 Janus chat snapshot。
- Acceptance：MCP initialization／discovery contract、三個 tools schema、owner 不可由 client 選擇、resources allowlisted、輸出 sanitized／bounded、既有 public／me／admin semantics 不變。
- 若既有 `janus-api` 無法安全承載 external MCP endpoint，立即停止並提交架構決策，不自行新增 resource 或擴大 ingress。

#### `WBS-6-PILOT-USEFULNESS-FEEDBACK`（【Sol】）

- 目的：在真實使用期間累積分析是否有持續研究價值的 evidence；只做最小 instrumentation，不做 model tuning 或大型 UI redesign。
- Feedback values：`useful`、`neutral`、`misleading`；可選 bounded reason 為 `discovered_risk`、`useful_context`、`already_known`、`too_generic`、`stale`、`missing_data`、`wrong_interpretation`、`other`。
- Feedback 必須 authenticated owner-scoped、綁定 immutable／traceable analysis result、只保存 bounded metadata、不修改歷史 analysis、不影響 deterministic score、不成為 publication input；優先重用既有 Flutter／Web analysis card。

### 6.6 `WBS-6-RESEARCH-CONTEXT-COMPOSITION`（Pilot Evolution／Planned）

- `WBS-6-RESEARCH-CONTEXT-CONTRACT` 先固定 market／company／supply-chain／private／quality sections、typed selectors、same-`analysis_as_of`、PIT、freshness、provenance 與 explicit missing-state semantics；它是 proposed contract，不是現有 endpoint。
- 在 existing `janus-api` 組合 proposed `ResearchContext`，共用 typed selectors、allowlist、owner binding、date／record／byte bounds、sanitization、provenance 與 same-`analysis_as_of`。
- UI 與 `WBS-6-CHATGPT-MCP-*` 消費同一 bounded contract；MCP 只讀、不接受 SQL／table／URI／owner input，不回傳 storage locator／credential，不提供 mutation。
- Google Drive 不是 runtime dependency。不新建 ChatGPT Cloud Run service；若 existing `janus-api` 安全上不足，依既有 MCP contract 停止並提交架構決策。
- UI 不計算 canonical financial／technical／portfolio values；只呈現 Mart 值、evidence、freshness、missing／stale／partial 與 owner scope。
- 本節 planned 能力通過自身 acceptance 後可直接在 parallel-live dev 使用；不另外等待 Production 環境。
