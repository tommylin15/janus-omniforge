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
- 個股首屏依序顯示健康度圓環、籌碼狀態與 `Icons.psychology` 白話 AI Card；K 線、Metrics、五角色與 provenance 預設收在進階資料。
- 個人工作台提供關注股、手動交易、一般筆記、歷史明細、持股、已實現／未實現與年度損益；正式結果只讀 Private Mart，不在 Flutter 或模型內重算。
- 「我的」提供 Janus 私人資料匯出與可稽核刪除流程；cutover 前仍需涵蓋 Janus 持有的歷史 assistant 資料，不提前宣稱 omniAgent data migration 完成。
- 支援 light／dark／system theme、phone／iPad／web responsive、VoiceOver／TalkBack 與至少 44×44 target。
- User App 不顯示 Admin 導覽、公開績效排行榜、下單或券商同步控制。
- UI 驗收必須呈現真實 backend 已知狀態；missing／stale／partial／unavailable／blocked 不得用 mock、sample 或 placeholder 補成成功畫面。

### 6.3 Admin UI

- WBS 3 已負責 Stage／Core Data Operations 的可操作閉環；本節延伸公開 Mart、governance
  與 reports。目標是單一 Flutter codebase 內的 User／Admin workspace，不是長期維護
  另一套獨立 HTML／JS UI；現有 static Admin 在 migration 期間保留，直到 parity、
  Admin auth、browser/runtime acceptance 與 rollback plan 全部完成。
- Flutter 隱藏控制不是 security boundary。`/api/v1/admin/*` 每次 request 仍由 backend
  enforce Admin authorization；User token 不得假設可呼叫 Admin API，User／Admin
  token audience 差異必須在 implementation WBS 驗證。
- Admin 主導覽使用中文：總覽、批次、個股、AI 分析、進階管理；工程欄位與 lineage
  放在「進階／詳細資訊」。
- 保留「資料營運中心」名稱與入口；`/admin/stocks` 使用 tablist／單面板模式，右側一次只顯示目前功能，不同功能不得整頁同時堆疊。
- 分頁至少包含：股票管理、股票資料狀態、最近執行、資料源健康、深度追蹤名單、排程與保存設定、資料源設定、Mart 分析。
- 股票管理支援跨頁批次選取；股票資料狀態與 execution／DQ／quarantine 明細以類 Excel 的欄列表格呈現，支援 sticky header、排序、篩選、分頁與欄位顯示，不以 raw JSON 作主要介面。
- Collection／Analysis 分開觸發。
- Legacy static Admin current surface 已有 Collection、Analysis queue 與 persisted「Mart 分析」
  index；它不代表新五角色 AI／CIO／Analysis Profile 已完成。Flutter parity 必須保留已驗收
  的 persisted read／review semantics，再依本 WBS 增加 Planned AI operations。
- 最近 50 次 execution 與按需明細。
- Governance typed edit、validation、diff、history、optimistic lock。
- Data-source health persisted telemetry。
- 全市場／去識別化關注股深度 membership、effective date、cadence、來源授權狀態與 quota 管理；MVP 超過 50 個 active distinct symbols 必須拒絕，Admin 不得取得 user-to-symbol 對應。
- 「資料源設定」只管理已核准來源；候選來源維持 disabled／blocked 設定，不提供審查或啟用控制。
- 「Mart 分析」按 analysis date、scope、industry、symbol、角色、prompt version、analysis outcome 與 publication status 篩選 `mart_scoped_analysis`，只讀已持久化 artifact。
- 一般 Admin 營運頁不得瀏覽使用者交易內容。只有另行核准的隱私事件處理流程可接觸必要最小 metadata，且必須 audit。

### 6.3.1 Planned Admin workspace slices

以下切片全部為 `Planned`，只描述後續 implementation scope；它們未完成時不得宣稱對應能力完成，但也不構成與其無關的現有 dev 功能必須停留在 POC 的理由：

| WBS | Dependency | Acceptance |
|---|---|---|
| `WBS-6-FLUTTER-ADMIN-SHELL` | existing Flutter app、Admin API auth contract、legacy static Admin | 單一 Flutter workspace、responsive shell、中文主導覽；backend Admin auth／audience negative tests 通過；legacy static 保留 |
| `WBS-6-ADMIN-OVERVIEW-BATCH` | ADMIN-SHELL、execution／retry API contract | actionable-issues-first overview、Core／Mart／AI／failure cards、retry classification、retryable failed item、execution lineage；正常 execution 不佔首頁主要空間 |
| `WBS-6-ADMIN-STOCK-WORKBENCH` | ADMIN-SHELL、Core／Mart persisted readers | 代號／中文名搜尋、dataset health、gap repair、role-impact mapping、affected-role rerun、historical facts／roles／CIO view；old execution immutable |
| `WBS-6-ADMIN-ANALYSIS-PROFILE` | MART role/provider/validation contracts、ADMIN-SHELL | Production version history、direct new Production version、rollback with audit lineage、role／CIO prompt editors、locked guardrail、model/capability picker、fixed 5–10 symbols、compare、per-role override |
| `WBS-6-ADMIN-LEGACY-RETIREMENT` | all four slices above、Admin auth acceptance、browser/runtime acceptance、rollback plan | only after Flutter parity and acceptance may legacy HTML Admin be deprecated; no early deletion |

表中的 `Production version` 是 Analysis Profile 的 active/released profile 狀態，不表示必須有獨立 Production GCP environment 才能在 dev 使用或驗收該 profile。

### 6.4 驗收條件

- UI 不自行計算後端分數。
- Flutter 不自行計算正式損益；User／Admin navigation and workspace state are separated,
  while backend authorization, token audience and CORS remain enforced independently.
- empty／unavailable／partial／fallback／blocked 語意正確。
- 未啟用股票 404；已啟用無資料顯示等待批次。
- 詳細驗收依 `../ui.md`。
- tab 具鍵盤操作、ARIA 與可分享 query-string deep link；重載後保留所選分頁，未選面板不重複抓取大型 details。
- 詳細 User／Admin 驗收依 `../ui.md`；今日頁所有卡片必須使用同一 analysis-as-of，個人工作台通過交易更正、筆記 revision、關注異動與跨使用者隔離測試。
- 對宣稱 live accepted 的 UI 流程，至少要有目前 GCP dev 真實 URL／runtime、真實 auth／persisted backend 與實際互動 evidence；mock/sample 只可補測，不可獨立完成驗收。

### 6.4.1 Planned Admin analysis semantics

- 單角色重跑預設使用目前 Production Profile；進階才能 override，完成後自動重跑 CIO
  與 governance recalc，其他 role artifact reuse。
- Core／Fact Pack 改變先更新受影響 Fact Pack；prompt/model 改變不重算 facts；CIO
  prompt/model 改變只跑 CIO；全部重跑保留但藏在進階。
- Profile 修改可直接建立新的 Production version；禁止覆蓋舊 Production；rollback
  也必須建立 audit／version lineage。固定 5–10 檔 test symbols 只作比較，不是
  Candidate approval gate。
- `Production Profile` 是模型／prompt 治理狀態；canonical facts、publication authority 與環境 release status 仍各自獨立。

### 6.5 Janus ChatGPT MCP Connector

ChatGPT connector 是 P1／parallel-live dev capability，採 existing `janus-api` remote
read-only MCP path，預設不新增 Cloud Run service，且不成為 Janus 未來 Production
topology 的 prerequisite。只要 MCP 自身通過 real-path acceptance，即可在目前 dev 真實使用；它只可讀已核准 public market data、owner-scoped private
investment data 與 bounded journal／ledger data；不得接受任意 SQL、table、URI 或
client-selected owner，也不得提供 mutation。

#### `WBS-6-CHATGPT-MCP-CONTRACT`（【Sol】）

- Scope：確認當時 OpenAI Custom MCP／OAuth requirements、Janus auth compatibility、
  三個 logical tools、read-only classification、owner binding、shared bounded
  query、public／private allowlist、output／provenance／quota contract。
- Acceptance：無 arbitrary SQL／URI／table／owner input、無 mutation、重用既有
  Janus data readers、auth compatibility 有明確 verdict；任何新 auth／GCP component
  只記為 blocked decision，不部署。
- Dependency：相關 Core／Private Mart／journal owner-scoped reader contract 已被
  理解；不依賴完整 `WBS-4C-ACCEPTANCE`。

#### `WBS-6-CHATGPT-MCP-ADAPTER`（【Sol】）

- Blocked until `WBS-6-CHATGPT-MCP-CONTRACT` complete；這是 MCP 本身的 dependency，不是整個 Janus dev 使用資格 gate。
- Scope：在既有 `services/api`／`janus-api` 實作 remote read-only MCP adapter，重用
  shared bounded query layer，完成 authenticated owner mapping、tool discovery／call、
  bounded error／timeout／rate／output limit，且不產生不必要的 Janus chat snapshot。
- Acceptance：MCP initialization／discovery contract、三個 tools schema、owner 不可
  由 client 選擇、resources allowlisted、輸出 sanitized／bounded、既有 public／me／admin
  semantics 不變。
- 若既有 `janus-api` 無法安全承載 external MCP endpoint，立即停止並提交架構決策，
  不自行新增 resource 或擴大 ingress。

#### `WBS-6-PILOT-USEFULNESS-FEEDBACK`（【Sol】）

- 目的：在真實使用期間累積分析是否有持續研究價值的 evidence；只做最小 instrumentation，
  不做 model tuning 或大型 UI redesign。
- Feedback values：`useful`、`neutral`、`misleading`；可選 bounded reason 為
  `discovered_risk`、`useful_context`、`already_known`、`too_generic`、`stale`、
  `missing_data`、`wrong_interpretation`、`other`。
- Feedback 必須 authenticated owner-scoped、綁定 immutable／traceable analysis
  result、只保存 bounded metadata、不修改歷史 analysis、不影響 deterministic score、
  不成為 publication input；優先重用既有 Flutter／Web analysis card。

### 6.6 `WBS-6-RESEARCH-CONTEXT-COMPOSITION`（Pilot Evolution／Planned）

- `WBS-6-RESEARCH-CONTEXT-CONTRACT` 先固定 market／company／supply-chain／private／quality sections、typed selectors、same-`analysis_as_of`、PIT、freshness、provenance 與 explicit missing-state semantics；它是 proposed contract，不是現有 endpoint。
- 在 existing `janus-api` 組合 proposed `ResearchContext`，共用 typed selectors、allowlist、owner binding、date／record／byte bounds、sanitization、provenance 與 same-`analysis_as_of`。
- UI 與 `WBS-6-CHATGPT-MCP-*` 消費同一 bounded contract；MCP 只讀、不接受 SQL／table／URI／owner input，不回傳 storage locator／credential，不提供 mutation。
- Google Drive 不是 runtime dependency。不新建 ChatGPT Cloud Run service；若 existing `janus-api` 安全上不足，依既有 MCP contract 停止並提交架構決策。
- UI 不計算 canonical financial／technical／portfolio values；只呈現 Mart 值、evidence、freshness、missing／stale／partial 與 owner scope。
- 本節 planned 能力通過自身 acceptance 後可直接在 parallel-live dev 使用；不另外等待 Production 環境。
