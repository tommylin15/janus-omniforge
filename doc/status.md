# Janus Current Status

更新：2026-09-24

用途：提供「現在在哪裡、下一步是什麼、哪些尚未完成」的短入口。這不是新的 source of truth；實作以 GitHub `main` 為準，完成狀態以 tests／CI／deployment／live runtime／integration evidence 為準。完整未完成工作仍在 [`todo.md`](todo.md)，完整歷史與 build／revision／digest evidence 仍在 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

## 目前結論

- GCP `dev` 是 Janus 個人使用階段的真實平行上線環境，不是只用 fixture／mock 的 POC 環境。
- Janus hard split 已完成：通用 Chat／Agent runtime 不再屬於 Janus active scope；Janus 保留 User／Admin、投資 domain API，以及 authenticated read-only MCP／OAuth connector。
- 現行 runtime 已收斂使用 `janus-runtime-bundle`；API 與既有三個 Cloud Run Jobs 的相關 runtime acceptance 已有 GCP dev evidence。
- ChatGPT MCP 已可 discovery／invoke 三個 read-only tools：`janus_sources`、`janus_market_context`、`janus_private_context`；market 與 private bounded reads 已有 live evidence。
- OAuth `offline_access`、refresh-token issuance、90-day sliding inactivity、one-time rotation 與 revocation 已部署；access token 到期後的 live refresh／rotation 已有 runtime evidence。
- MCP market-context credential routing defect已修正並有 authenticated market read evidence。
- **`WBS-8-CHATGPT-MCP-ACCEPTANCE` 尚未完成。**目前唯一剩餘 connector acceptance 是第二 owner 的 live A/B attribution／isolation：必須確認當前授權確實是 owner B、B 只能讀 B 私有資料，再切回 owner A 驗證 A 仍只能讀 A。
- 最高優先項目 `WBS-6-TRANSACTION-UX-2` 已完成。Flutter/API 本地測試、canonical dev 100% traffic 切換及 Chrome authenticated read-only acceptance 均通過；持股、交易月份／明細、年度報表與表單可載入，缺價／partial 與 Mart pending 狀態正確顯示。操作表單後皆取消，沒有修改個人帳本。此項不是 Dev Pilot Entry blocker。新 Mart 會保存每檔行情日，早於組合估值日的行情標為 stale。

## 下一個執行序列

1. **完成 `WBS-8-CHATGPT-MCP-ACCEPTANCE` 的 owner A/B live isolation。**
   - 不接受僅「authenticated private call 成功」作為證據；response 未帶 identity 時，必須用可稽核流程確認授權身分與各 owner 的資料邊界。
   - 不讀取或輸出 token／secret payload。
   - partial success 不得標記 full acceptance。
2. **重新評估 `WBS-8-DEV-PILOT-ENTRY`。**
   - 依 `todo.md` 的正式 Entry Gate 逐項檢查；MCP connector 可由使用者明確決定是否允許以 blocked 狀態啟動 Pilot，不能由文件自行放寬 gate。
   - 只有 Entry Gate 真正通過時才記錄 `pilot_started_at`。
3. **Pilot 開始後才進入 `WBS-8-DEV-PILOT-RUN`。**
   - 6 個 calendar months 的 operational evidence 不得預填或以開發 checkpoint 代替。

## 不在立即執行佇列

以下仍是有效需求，但目前屬 planned／blocked／deferred，不應和上述三步混成同一個 active queue：

- 全市場其他 datasets 與個股深度追蹤來源擴充。
- Mart Fact Packs、AI role contracts／validation／providers、CIO synthesis、rerun/cache。
- Flutter Admin shell、overview／batch、stock workbench、Analysis Profile、legacy retirement。
- Pilot Mart AI evaluation。
- Research Context Pilot Evolution roadmap。
- 完整 P2 calibration、跨裝置／A11y、production architecture／HA／backup planning。
- P4 完整 DQ 強化與 30% gate calibration。
- 未核准來源、paid source、新 GCP service／HA／multi-region 等仍維持各自 gate。

完整 dependency、acceptance 與分類請直接讀 [`todo.md`](todo.md)，不要從本頁推導被省略的細節。

## Evidence 讀取順序

需要判斷「是否完成」時依序看：

1. GitHub `main` 的實際 code／schema／migration／workflow／tests。
2. 最新 tests／CI／Cloud Build／deployment／live runtime／trigger／workload／integration evidence。
3. 本頁做快速定位。
4. [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 查完整 evidence ledger 與歷史 checkpoint。
5. `archive/` 只用於歷史原因與被取代設計。

文件修改、commit 或 status 摘要更新本身，都不代表功能完成。
