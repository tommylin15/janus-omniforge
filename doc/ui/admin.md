# Janus UI — Admin UI

## 9.0 Target workspace

Admin 的目標是 `apps/user_app` 內的 Flutter workspace，與 User 共用 codebase 但不共用
權限。`/api/v1/admin/*` 每次由 backend enforce Admin authorization；User token audience
不可直接呼叫 Admin API，Flutter 隱藏控制也不是 security boundary。現有 static HTML／JS
Admin 只在 migration 期間保留，parity、auth、browser/runtime acceptance 與 rollback
plan 未完成前不得 deprecate。

主導覽固定為「總覽、批次、個股、AI 分析、進階管理」，平常使用中文；execution ID、
snapshot、hash、provider、model、prompt 與 artifact 等工程欄位放在「進階／詳細資訊」。

### 9.0.1 總覽與批次

- 首頁採 actionable-issues-first：Core、Mart、AI 分析、失敗／阻擋四類卡片只突出需要
  處理項目；無異常時顯示「今日沒有需要處理的事項」，正常 execution 不佔主要空間。
- 失敗 item 顯示 retryable／non-retryable／blocked 分類；只能重試 retryable failed
  item。重試建立新 execution，保留舊 execution 與 retry lineage；partial success 不
  顯示成 full success。

## 9. Admin UI

### 9.1 `/admin/stocks`

- 頁面品牌／標題保留「資料營運中心」；若沿用左側 Admin 導覽，右側仍一次只顯示一個功能面板。
- Legacy static Admin current surface 使用 `tablist` 提供資料營運分頁，並已有 persisted
  「Mart 分析」index／review；Flutter target 必須保留 bounded read semantics。新 AI role、
  CIO、Profile 與 prompt editing 在對應 Planned WBS 完成前不得顯示為可用。選取狀態寫入
  `?tab=`，重載與分享 URL 後可還原；未選分頁不預抓大型 details。
- Desktop 顯示水平或側邊 tabs；窄螢幕可用可捲動 tablist 或等價單選導覽，但頁面標題與目前分頁名稱必須可見。tab 支援方向鍵、Home／End、Enter／Space，並正確連結 `aria-controls`／`aria-labelledby`。

「股票管理」：

- 全部股票，不套 public enabled filter；代號／名稱搜尋、每頁 10 筆。
- 新增、編輯、enabled toggle、本頁全選與跨頁保留。
- Legacy static Admin 的 Analysis queue 只代表 persisted execution request；queued 不顯示為
  完成，retry 仍須依 failure classification。新 AI analyst／CIO execution 依 Planned
  WBS 5 contracts 驗證後才可啟用。
- 有 market／report／fundamental 關聯時禁止刪除並顯示數量。

「股票資料狀態」：

- Core 最新交易日、dataset、coverage、row count、null count／ratio、DQ、quarantine、freshness、source、snapshot ID 與 updated time 使用欄列表格，不直接輸出 JSON blob。
- 表格採類 Excel 閱讀方式：sticky header、欄位對齊、排序、篩選、分頁、欄位顯示／隱藏、橫向捲動及空值 `—`；不要求 spreadsheet 公式或任意 inline edit。
- row expand／「查看」才載入明細；巢狀 quality flags、association、quarantine reason 轉成子表或 key/value definition list。raw payload、object URI、敏感 URL 與完整 upstream error 不得提供「查看 JSON」旁路。

「最近執行」：

- 最近 50 次 persisted execution；row click／「查看」才讀結構化 details。
- execution item 以 source、dataset、target date、processed／success／failure／retry、Stage／Core commit、safe message 欄位顯示，不以 JSON 作主要內容。

「資料源健康」、「深度追蹤名單」、「排程與保存設定」、「資料源設定」各自只呈現對應資料與控制，按鈕不得跨面板造成用途不明。「深度追蹤名單」只顯示去識別化 symbol demand、effective time 與 cadence，不顯示 user-to-symbol 關係。

「Mart 分析」：

- Current legacy surface 只讀已持久化的 `mart_scoped_analysis`，不得以空表或無 consumer
  的 queued execution 假裝新 AI 能力可用。
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

- 預設顯示 Production Profile、provider、model、reasoning、output length；進階才顯示
  per-role provider/model override、supported parameters、prompt versions、test symbols、
  compare、rollback 與 technical lineage。
- 預設所有角色同模型；不支援的 parameter 不送 provider。固定 5–10 檔 test symbols
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
