# Janus UI — Admin UI

## 9.0 Target workspace

Admin 的目標是 `apps/user_app` 內的 Flutter workspace，與 User 共用 codebase 但不共用
權限。`/api/v1/admin/*` 每次由 backend enforce Admin authorization；User token audience
不可直接呼叫 Admin API，Flutter 隱藏控制也不是 security boundary。2026-10-02 使用者明確
決定 legacy static HTML／JS Admin 直接退役，不再作為 fallback，也不再等待 Flutter parity／
rollback gate；Flutter／PWA 是唯一 active Admin frontend。Legacy source 的可還原座標保留於
`archive/legacy-static-admin-retired-2026-10-02.md`，但不得重新納入 runtime，除非使用者日後另行決定。

主導覽固定為「總覽、批次、個股、市場資訊、AI 分析、進階管理」，平常使用中文；execution ID、
snapshot、hash、provider、model、prompt 與 artifact 等工程欄位放在「進階／詳細資訊」。

### 9.0.1 總覽與批次

- 首頁採 actionable-issues-first：Core、Mart、AI 分析、失敗／阻擋四類卡片只突出需要
  處理項目；無異常時顯示「今日沒有需要處理的事項」，正常 execution 不佔主要空間。
- 首頁 issue card **不得只是被動數字**。有非零項目時，card 必須可進入對應的 filtered
  明細／批次清單，至少能辨識「哪一筆、為什麼、最後更新、可否處理」；可重試項目才顯示
  retry／rerun action。首頁不重複塞完整工程細節，而是完成「看見異常 → drill-down → 處理」閉環。
- `WBS-3-DATA-SUPPLEMENT-V1` 追加的週六資料品質檢查結果，完成接線後顯示於總覽／批次：
  最近檢查時間、結果、受影響個股／dataset／欄位、安全原因、是否需要調整每日排程，以及
  檢核文件入口。尚無檢查結果時顯示「尚未檢查」，不得以 0 或正常取代 unknown；檢查本身
  執行失敗須與資料品質不合格區分。使用者已決定先只看 Admin UI，不建立 Codex automation／
  通知或 Email。此追加需求尚未實作／部署，不能視為現有可用功能。
- 失敗 item 顯示 retryable／non-retryable／blocked 分類；只能重試 retryable failed
  item。重試建立新 execution，保留舊 execution 與 retry lineage；partial success 不
  顯示成 full success。
- 「批次」擴充為 Job Control Center：列出目前有效的 master／batch controller，以及其
  dispatch 的 ingestion、Mart、五角色 AI、Private Pipeline、cleanup／maintenance 等子工作；
  每列至少顯示 effective schedule／trigger、latest execution state、started/finished/last update、
  latest success 與安全的 manual rerun。UI 不得把「enqueue 成功」當成 workload 成功。
- 批次明細預設顯示最近 **3 天** execution／occurrence timeline；更早紀錄保留並以日期範圍、
  cursor 或等價方式選取，不因首頁視窗縮短就刪除歷史。controller／child lineage、Cloud Run
  execution reference 與 safe failure reason 應可 drill-down，但 secret／raw payload 不得暴露。
- Manual rerun 必須走 backend allowlist、idempotency／duplicate guard、dependency／exclusive
  guard 與 audit，不讓 Flutter 直接操作 checkpoint、Cloud Run 任意 job name 或 storage object。

### 9.0.2 Storage／Private operations

- Admin 提供 Iceberg／GCS operational monitor，至少涵蓋 Stage、Core、Mart 與必要的 Private
  Mart 指標：active snapshot／manifest、live object count、live bytes、最近一次 maintenance、
  snapshot/reference protection、retention window、planned/actual reclaimed objects/bytes 與 anomaly。
- UI 必須區分 **Iceberg/GCS live objects／active bytes** 與雲端帳單可能包含的 non-current、
  soft-delete／versioned bytes；沒有可靠 billable-storage evidence 時顯示 `unknown`，不得把 live
  bytes 說成實際帳單容量。Storage dashboard 優先讀 persisted maintenance／telemetry，不在每次
  page load 即時 enumerate 整個 bucket。
- 可呈現「Core snapshot manifests 數、Mart report index 數、被 publication 精確引用的 Mart
  snapshot 數、protected retention date range」等摘要；所有數字需帶資料時間／scope，未知不補 0。
- Private Pipeline 顯示 current checkpoint、checkpoint updated time、最新可見 change/ledger version、
  pending/backlog（可可靠計算時）、last execution/result、latest Private Mart valuation date 與 lag。
  一般 Admin 不顯示使用者交易正文／持股內容；只顯示操作所需的去識別化／aggregate metadata。
- Private Pipeline 的「實際有效啟動方式／schedule」以當下 GitHub main + live Scheduler／batch
  controller evidence 為準。若 direct Scheduler 與 controller migration 同時存在，Admin 必須如實
  顯示，先完成重複觸發／cutover 驗證再修改排程，不能只依舊文件或 UI 字串推定。

### 9.0.3 Routing controls

- Provider／market-source priority 是 backend versioned routing contract，不由 Flutter hard-code。
  Admin 只編輯排序與已核准設定；runtime 讀取已提交版本並保存 effective route/version、attempt、
  fallback reason 與實際 source/provider。所有修改保留 actor、timestamp、before/after 與 optimistic lock。
- 五分析師預設 provider priority：**Codex CLI → OpenRouter → Gemini**。Admin 可用 drag/reorder
  前後調整全域 default；只有 `approved`／已核准 profile 才能成為 executable route。未核准、auth
  不可用、paid gate 未授權的 provider 可顯示 blocked/disabled，但不得因被排到前面就自動啟用。
  per-role override 放在 Analysis Profile 的進階設定；沒有 override 時五角色共用 default route。
- 行情 routing 分盤中／盤後兩條設定。使用者指定的目標預設為：盤中 **Yahoo → Fugle realtime →
  TWSE MIS**；盤後 **TWSE published/EOD → Fugle → Yahoo**。實際啟用仍受 source authorization、
  license、quota／cost 與 health gate；未核准來源必須跳過並明示 blocked，禁止 silent fallback。
- Routing UI 顯示每個 entry 的 enabled/approved/auth/health、last success、last failure、最近 latency
  與可取得的 quota/cost status；缺資料顯示 unknown。排序修改不等於 provider/source 已完成 live acceptance。

## 9. Admin UI

### 9.1 Flutter Admin workspace（`/app/admin`）

- 頁面品牌／標題保留「資料營運中心」；若沿用左側 Admin 導覽，右側仍一次只顯示一個功能面板。
- Flutter Admin 保留 bounded read semantics。新 AI role、CIO、Profile 與 prompt editing 在對應 Planned
  WBS 完成前不得顯示為可用。選取狀態需可由 URL 或等價 navigation state 還原；未選分頁不預抓大型 details。
- Desktop 顯示水平或側邊 tabs；窄螢幕可用可捲動 tablist 或等價單選導覽，但頁面標題與目前分頁名稱必須可見。tab 支援方向鍵、Home／End、Enter／Space，並正確連結 `aria-controls`／`aria-labelledby`。

「股票管理」：

- 全部股票，不套 public enabled filter；代號／名稱搜尋、每頁 10 筆。
- 新增、編輯、enabled toggle、本頁全選與跨頁保留。
- Analysis queue 只代表 persisted execution request；queued 不顯示為完成，retry 仍須依 failure
  classification。新 AI analyst／CIO execution 依 Planned WBS 5 contracts 驗證後才可啟用。
- 有 market／report／fundamental 關聯時禁止刪除並顯示數量。

「股票資料狀態」：

- Core 最新交易日、dataset、coverage、row count、null count／ratio、DQ、quarantine、freshness、source、snapshot ID 與 updated time 使用欄列表格，不直接輸出 JSON blob。
- 表格採類 Excel 閱讀方式：sticky header、欄位對齊、排序、篩選、分頁、欄位顯示／隱藏、橫向捲動及空值 `—`；不要求 spreadsheet 公式或任意 inline edit。
- row expand／「查看」才載入明細；巢狀 quality flags、association、quarantine reason 轉成子表或 key/value definition list。raw payload、object URI、敏感 URL 與完整 upstream error 不得提供「查看 JSON」旁路。

「最近執行」：

- 預設最近 3 天 persisted execution；另提供更早歷史選取。需要快速營運視角時可保留「最近 50 次」作 bounded query preset，但不得成為唯一歷史入口。
- row click／「查看」才讀結構化 details；execution item 以 source、dataset、target date、processed／success／failure／retry、Stage／Core commit、safe message 欄位顯示，不以 JSON 作主要內容。

「資料源健康」、「深度追蹤名單」、「排程與保存設定」、「資料源設定」各自只呈現對應資料與控制，按鈕不得跨面板造成用途不明。「深度追蹤名單」只顯示去識別化 symbol demand、effective time 與 cadence，不顯示 user-to-symbol 關係。

「Mart 分析」：

- 現行 Mart surface 只讀已持久化的 `mart_scoped_analysis`，不得以空表或無 consumer 的 queued execution 假裝新 AI 能力可用。
- 可依 analysis date、scope（market／industry／symbol）、industry、symbol、角色、prompt version、analysis outcome 與 publication status 篩選；明細顯示 summary、score、confidence、missing data、evidence reference、Core／Mart snapshot 與版本。
- 歷史 prompt version 與分析 artifact 只能檢視，不可原地改寫；重新分析必須建立新的
  queued execution。System Guardrail 與 Output Schema locked；Role Methodology／CIO
  Prompt 由唯一 Admin 編輯並產生 immutable version、content hash、author、timestamp
  與 Analysis Profile reference。

### 9.1 個股工作台（Planned）

- 支援代號／中文名稱搜尋、dataset health、gap repair、role-impact mapping、affected-
  role automatic rerun，以及 `analysis_as_of`／execution／snapshot 歷史切換。
- 個股頁可檢視 immutable facts、五份 validated role analysis 與 CIO；舊 artifact 不可
  原地修改。技術 lineage 放在進階，不以 raw JSON 作主要 UX。

### 9.2 Analysis Profile（Planned）

- 預設顯示 Production Profile、provider route、model、reasoning、output length；進階才顯示
  per-role provider/model override、supported parameters、prompt versions、test symbols、
  compare、rollback 與 technical lineage。
- Provider route 預設 `Codex CLI → OpenRouter → Gemini`，Admin 可排序已核准 provider；
  調整建立新 version／audit，不覆寫舊 execution 的 effective routing lineage。未核准或需要新增
  付費 gate 的 provider 不因排序自動啟用。
- 預設所有角色同 route/model policy；不支援的 parameter 不送 provider。固定 5–10 檔 test symbols
  可比較 current Production 與新 Production version，但不是 Candidate approval gate。
- Admin 可直接建立新 Production version，不得覆蓋舊版；rollback 建立新的 audit／
  version lineage。單角色重跑預設使用目前 Production Profile，進階才可 override。

### 9.2 `/admin/governance`

- Typed editing。
- Group validation。
- Diff preview。
- Immutable revision history。
- Optimistic lock。
- 顯示 approved／development-default／pending。
- Workflow 使用 immutable snapshot，不讀取未提交表單。

### 9.3 `/admin/reports`

- 篩選 blocked／manual review／insufficient／publishable。
- 顯示 evidence、blocking reason、governance version。
- block／unblock／approve 需要理由、操作者與 audit trail。
- 不可直接修改原始 evidence 或 deterministic score。

## 資料補強品質檢查（已實作）

Admin Overview 顯示獨立週六檢查的最近時間、通過／需處理／執行失敗、受影響資料與是否需調整每日補資料；「結果與檢核文件」可檢視安全結果及完整操作文件。結果來自 `data_supplement_quality`，文件使用 Admin 授權端點 `/api/v1/admin/data-quality/runbook`。不透過 Email 或 Codex automation 通知。
