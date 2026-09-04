# Janus UI — Admin UI

## 9. Admin UI

### 9.1 `/admin/stocks`

- 頁面品牌／標題保留「資料營運中心」；若沿用左側 Admin 導覽，右側仍一次只顯示一個功能面板。
- 第一階段使用 `tablist` 開放「股票管理」、「股票資料狀態」、「最近執行」、「資料源健康」、「深度追蹤名單」、「排程與保存設定」、「資料源設定」七個資料營運分頁。「Mart 分析」hidden／disabled，直到 WBS 5 persisted consumer 完成。選取狀態寫入 `?tab=`，重載與分享 URL 後可還原；未選分頁不預抓大型 details。
- Desktop 顯示水平或側邊 tabs；窄螢幕可用可捲動 tablist 或等價單選導覽，但頁面標題與目前分頁名稱必須可見。tab 支援方向鍵、Home／End、Enter／Space，並正確連結 `aria-controls`／`aria-labelledby`。

「股票管理」：

- 全部股票，不套 public enabled filter；代號／名稱搜尋、每頁 10 筆。
- 新增、編輯、enabled toggle、本頁全選與跨頁保留。
- 第一階段只啟用 Collection／backfill；Analysis 顯示尚未開放且不得建立 queued execution。WBS 5 persisted consumer 完成後才分開啟用 Analysis；queued 不顯示為完成。
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

- 第一階段 hidden／disabled；不得以空表或無 consumer 的 queued execution 假裝可用。
- 以單一資料表讀取已持久化的 `mart_scoped_analysis`。
- 可依 analysis date、scope（market／industry／symbol）、industry、symbol、角色、prompt version、analysis outcome 與 publication status 篩選；明細顯示 summary、score、confidence、missing data、evidence reference、Core／Mart snapshot 與版本。
- 歷史 prompt version 與分析 artifact 只能檢視，不可原地改寫；重新分析必須建立新的 queued execution。Prompt 由 repository 版控，不在 Admin 編輯。

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
