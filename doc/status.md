# Janus Current Status

更新：2026-09-26

用途：提供「現在在哪裡、下一步是什麼、哪些尚未完成」的短入口。這不是新的 source of truth；實作以 GitHub `main` 為準，完成狀態以 tests／CI／deployment／live runtime／integration evidence 為準。完整未完成工作仍在 [`todo.md`](todo.md)，完整歷史與 build／revision／digest evidence 仍在 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)。

## 目前結論

- GCP `dev` 是 Janus 個人使用階段的真實平行上線環境，不是只用 fixture／mock 的 POC 環境。
- Janus hard split 已完成：通用 Chat／Agent runtime 不再屬於 Janus active scope；Janus 保留 User／Admin、投資 domain API，以及 authenticated read-only MCP／OAuth connector。
- 現行 runtime 已收斂使用 `janus-runtime-bundle`；API 與既有三個 Cloud Run Jobs 的相關 runtime acceptance 已有 GCP dev evidence。
- ChatGPT MCP 已可 discovery／invoke 三個 read-only tools：`janus_sources`、`janus_market_context`、`janus_private_context`；market 與 private bounded reads 已有 live evidence。
- OAuth `offline_access`、refresh-token issuance、90-day sliding inactivity、one-time rotation 與 revocation 已部署；access token 到期後的 live refresh／rotation 已有 runtime evidence。
- MCP market-context credential routing defect已修正並有 authenticated market read evidence。
- **`WBS-8-CHATGPT-MCP-ACCEPTANCE` 的 Owner A/B live read isolation 已通過。**ChatGPT 外掛帳戶設定分別確認 A、B 的目前選取狀態，再各自以新對話查詢相同四種私人資源；B 的 profile 可讀，但 positions／trades／performance 為 missing，而 A 的三項均有資料。owner_id 注入由工具 schema 在送出前拒絕。摘要雜湊不一致，故不作為驗收判據；詳細限制見 operations-and-testing。
- **`WBS-8-DEV-PILOT-ENTRY` 已通過。**2026-09-24T15:29:19Z 記為 `pilot_started_at`；既有 `janus-private-pipeline` 已部署獨立 image digest，execution `janus-private-pipeline-dd77n` 以 `Completed=True`／`succeededCount=1` 結束。Outcome／feedback 仍為 0 rows、feedback target 1；尚無 baseline-linked report，沒有造測試資料。完整 evidence 見 operations-and-testing。
- **`WBS-8-DEV-PILOT-RUN` 已進入 operational evidence window，目前仍為 partial。**Pilot 起點後的 Scheduler execution `janus-ingestion-core-n8bs2` 曾在 TWSE 休市日 `2026-09-25` 對 `twse-valuation`、`twse-institutional`、`twse-market-activity` 產生 `ValueError`。版本化修復 `029_twse_2026_holiday_overrides.sql` 已由既有 operator IAP 路徑成功套用，migration marker 與 `2026-09-25`／`2026-09-28` holiday overrides 已有 live evidence。`twse-valuation` bounded acceptance 已通過：requested `2026-09-26` 的 execution `janus-ingestion-core-7z8kv` 最終 `Completed=True`／`succeededCount=1`／container `exit(0)`，application log 顯示 `as_of=2026-09-24`、`dates=[2026-09-24]`、`failed=0`、`status=succeeded`。`twse-institutional` bounded acceptance 亦已通過：GitHub Actions run `36216088848` 成功，execution `janus-ingestion-core-pwgn9` 正確回推至 `2026-09-24`；第 1 attempt 曾以 `HTTPError`／container `exit(1)` 結束，但 Cloud Run 依既有 `maxRetries=1` 自動 retry，第 2 attempt container `exit(0)`，execution 最終 `Completed=True`／`succeededCount=1`。成功 application summary 為 `as_of=2026-09-24`、`dates=[2026-09-24]`、`failed=0`、`status=succeeded`、`staged=1`、`core_created=12`，`core.institutional_v1` snapshot 報告 324 rows；Mart trigger 為 `not_required`。這證明 institutional 不再重現原 calendar `ValueError`，但同時保留首次 transient HTTP failure 的真實 evidence。`twse-market-activity` 尚待獨立 bounded live acceptance，因此不能宣稱整體 calendar repair 或 `WBS-8-DEV-PILOT-RUN` 完成。
- 最高優先項目 `WBS-6-TRANSACTION-UX-2` 已完成。Flutter/API 本地測試、canonical dev 100% traffic 切換及 Chrome authenticated read-only acceptance 均通過；持股、交易月份／明細、年度報表與表單可載入，缺價／partial 與 Mart pending 狀態正確顯示。操作表單後皆取消，沒有修改個人帳本。此項不是 Dev Pilot Entry blocker。新 Mart 會保存每檔行情日，早於組合估值日的行情標為 stale。

## 下一個執行序列

1. **繼續 `WBS-8-DEV-PILOT-RUN` 六個月 evidence window。**
   - 下一個原子項目是 `twse-market-activity` 的 bounded live ingestion acceptance，確認 requested 休市／週末日期會回推到 `2026-09-24`，且不再重現原 `ValueError`。
   - 起點 `pilot_started_at=2026-09-24T15:29:19Z`；持續記錄真實 Scheduler／ingestion／analysis、outcome、usefulness、cost、操作介入、失敗與 security／privacy evidence。
   - 開發 checkpoint 不得代替六個 calendar months 的 operational evidence。

## 不在立即執行佇列

以下仍是有效需求，但目前屬 planned／blocked／deferred，不應和上述步驟混成同一個 active queue：

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
