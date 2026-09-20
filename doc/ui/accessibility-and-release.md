# Janus UI — Dialog、A11y 與 Release Checklist

## 10. Dialog 與 A11y

- `role=dialog`、`aria-modal=true`、`aria-labelledby`。
- 開啟後焦點進入 dialog；Tab／Shift+Tab 循環。
- Escape、close、backdrop 行為一致。
- 關閉後恢復 opener focus。
- 保存／恢復 body overflow 與 overscroll behavior。
- iOS rubber-band 不穿透背景。
- 事件長文保留換行，展開控制有 `aria-expanded`。

## 11. UI Release Checklist

### 11.1 第一階段：Stage／Core／Admin

- [ ] 七個資料營運分頁一次只顯示一個 panel；query-string deep link、鍵盤 tabs 與 responsive 導覽通過。
- [ ] Collection／backfill 可完成並顯示 execution item、Stage／Core commit 與安全失敗資訊；
  legacy static Admin 的 persisted Analysis／Mart read path 保持 bounded，queued／partial
  不顯示為完成；新 AI role／CIO／Profile controls 在 Planned WBS 完成前不可用。
- [ ] 股票狀態、execution、DQ／quarantine 均以 bounded 結構化表格呈現，沒有 raw JSON 主視圖。
- [ ] 關注股深度追蹤 membership、50-symbol 營運護欄、已核准來源、排程與 retention 異動可驗證並留下 audit；Admin 看不到 user-to-symbol 關係，候選來源沒有審查或啟用控制。
- [ ] raw payload、secret、敏感 URL、object URI 與 traceback 不出現在 DOM／network response。
- [ ] Modal focus trap、restore、scroll lock、主要控制 ≥44×44 與 WCAG AA 通過。

### 11.2 P0：個人工作台與可切換 AI

- [ ] Flutter `analyze`／widget tests 通過；User／Admin 使用同一 Flutter codebase 的不同
  workspace、認證 audience 與導覽，backend Admin authorization 貫穿每個 Admin request。
- [ ] 啟用「關注／筆記／AI／我的」；「今日」顯示 coming soon／disabled，一般 page load 不觸發即時分析。
- [ ] 交易新增／更正、筆記 revision、關注異動、跨年年度損益、缺價、超賣、匯出與刪除路徑通過；Flutter 與模型不重算正式損益。
- [ ] OpenRouter／Gemini API／Codex 三 runtime 可選，切換建立新 thread／fork；provider、model、skill、context、search、tools 與 citations 可追溯，Codex 不使用直接 OpenAI API fallback。
- [ ] Data Sources 顯示 Janus public／private／external 的日期、provenance、owner／quota 狀態；私人 context 預設不選取。MCP 容器內 stdio／遠端 Streamable HTTP／legacy SSE、動態 tools 與 GCP Skills controls 通過鍵盤、讀屏、錯誤與重連驗收。
- [ ] Codex Items／Turns／Approval Requests 可操作且 request-bound；Cloud Run cold start／timeout／reconnect 有明確狀態，核准 shell／寫檔限 turn 暫存 sandbox，Admin／私人 mutation／下單不可核准；Gemini REST API Grounding citation 與免費額度通過。
- [ ] 使用者 A 無法讀寫或推測使用者 B 的 trade、note、watchlist、chat、position、PnL 或 private artifact reference。
- [ ] User／Admin audience 混用與 client 指定 `user_id` 均被拒絕；email 變更不改變既有 ledger 所有權。
- [ ] 私人資料刪除顯示 `QUEUED`／`CLEANUP_PENDING`／`COMPLETED`，pending 時停用 Codex login／新 turn／私人寫入且不宣稱完成；狀態可由 request owner 重查，完成後 Codex 要求重新登入，保留中 object version 顯示期限。
- [ ] Mobile／iPad／desktop 無水平 overflow；主要路徑通過 VoiceOver／TalkBack。

### 11.3 個人曝險與壓力測試

- [ ] 總資產、現金、持股、產業曝險與年度績效均顯示 valuation date／缺價，比例分攤總和及 XIRR typed status 正確。
- [ ] 投資屬性加入 AI context 前有明確 opt-in；壓力測試 deterministic result 與 AI 解釋分區，模型不能修改數值。
- [ ] 多產業曝險具列表替代內容、鍵盤與讀屏標籤，不只依賴雷達圖或顏色。

### 11.4 後續公開研究 UI

- [ ] 今日頁只組合同一 `analysis_as_of` 的 market／sector／topic／candidate Mart，日期不一致顯示 partial。
- [ ] 個股首屏只顯示健康度、白話摘要、籌碼狀態與風險；K 線及五角色明細預設收合。
- [ ] 健康度具文字與 semantics，不只依賴顏色；分數明示不是獲利機率。
- [ ] K 線替代表格、keyboard、touch、Escape，report history、blocked／null 與 partial／stale／fallback 語意通過。
- [ ] Mart 分析顯示正確 prompt version／content hash；iOS Safari、Android Chrome、iPad Safari 實機通過。
