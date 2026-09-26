# Janus Current Status

更新：2026-09-26

用途：提供「現在在哪裡、下一步是什麼、哪些尚未完成」的短入口。這不是新的 source of truth；實作以 GitHub `main` 為準，完成狀態以 tests／CI／deployment／live runtime／integration evidence 為準。完整未完成工作仍在 [`todo.md`](todo.md)，完整歷史與 build／revision／digest evidence 仍在 [`spec/operations-and-testing.md`](spec/operations-and-testing.md)；六個月 Pilot 新增 operational checkpoint 記於 [`pilot-operational-evidence.md`](pilot-operational-evidence.md)，交易日曆修復的可重跑程序與 bounded acceptance evidence 見 [`runbook-pilot-calendar-repair.md`](runbook-pilot-calendar-repair.md)。

## 目前結論

- GCP `dev` 是 Janus 個人使用階段的真實平行上線環境，不是只用 fixture／mock 的 POC 環境。
- Janus hard split 已完成：通用 Chat／Agent runtime 不再屬於 Janus active scope；Janus 保留 User／Admin、投資 domain API，以及 authenticated read-only MCP／OAuth connector。
- 現行 runtime 已收斂使用 `janus-runtime-bundle`；API 與既有三個 Cloud Run Jobs 的相關 runtime acceptance 已有 GCP dev evidence。
- ChatGPT MCP 已可 discovery／invoke 三個 read-only tools：`janus_sources`、`janus_market_context`、`janus_private_context`；market 與 private bounded reads 已有 live evidence。
- OAuth `offline_access`、refresh-token issuance、90-day sliding inactivity、one-time rotation 與 revocation 已部署；access token 到期後的 live refresh／rotation 已有 runtime evidence。
- MCP market-context credential routing defect已修正並有 authenticated market read evidence。
- **`WBS-8-CHATGPT-MCP-ACCEPTANCE` 的 Owner A/B live read isolation 已通過。**ChatGPT 外掛帳戶設定分別確認 A、B 的目前選取狀態，再各自以新對話查詢相同四種私人資源；B 的 profile 可讀，但 positions／trades／performance 為 missing，而 A 的三項均有資料。owner_id 注入由工具 schema 在送出前拒絕。摘要雜湊不一致，故不作為驗收判據；詳細限制見 operations-and-testing。
- **`WBS-8-DEV-PILOT-ENTRY` 已通過。**2026-09-24T15:29:19Z 記為 `pilot_started_at`；既有 `janus-private-pipeline` 已部署獨立 image digest，execution `janus-private-pipeline-dd77n` 以 `Completed=True`／`succeededCount=1` 結束。Outcome／feedback 仍為 0 rows、feedback target 1；尚無 baseline-linked report，沒有造測試資料。完整 evidence 見 operations-and-testing。
- **`WBS-8-DEV-PILOT-RUN` 已進入 operational evidence window，目前仍為 partial。第一份 operational checkpoint 已記錄。**Fresh read-only inspection GitHub Actions run `36224058493` 確認自然 Scheduler execution `janus-ingestion-core-n8bs2` 由 `janus-ingestion-scheduler` 建立於 `2026-09-25T23:30:01Z`（Asia/Taipei `2026-09-26 07:30:01`），兩次 attempt 都以 `exit(1)` 結束，execution 最終 `Completed=False`／`failedCount=1`／`retriedCount=1`。兩次 application failure summary 都把 `twse-valuation`、`twse-institutional`、`twse-market-activity` 的 target date 落在休市日 `2026-09-25`，並回 `ValueError`。版本化修復 `029_twse_2026_holiday_overrides.sql` 已由既有 operator IAP 路徑成功套用，migration marker 與 `2026-09-25`／`2026-09-28` holiday overrides 已有 live evidence。三個受影響 dataset 的 bounded live acceptance 均已通過：`twse-valuation` execution `janus-ingestion-core-7z8kv`；`twse-institutional` GitHub Actions run `36216088848`／execution `janus-ingestion-core-pwgn9`（保留第一次 transient `HTTPError` 後 retry 成功 evidence）；`twse-market-activity` GitHub Actions run `36218341537`／execution `janus-ingestion-core-zvbc9`，summary `failed=0`、`status=succeeded`、`core.market_activity_v1` 336 rows、Mart `not_required`。三個 bounded repair acceptance 均正確回推至 `2026-09-24`，calendar repair dataset-level slice 完成；但手動 bounded acceptance 不能代替後續自然 Scheduler recovery evidence。
- **第一份 Pilot checkpoint 不宣稱新的 post-start analysis success。**觀察到的自然 Scheduler execution 在 ingestion 階段失敗；三個 repair acceptance 又明確停用 Mart／回報 `not_required`。因此本 checkpoint 的 post-start analysis evidence 記為 `not observed`，而不是推測成功或宣稱整個 GCP project 沒有 Mart execution。Backup／restore、outcome、usefulness、cost、security／privacy 的 post-start delta 本 checkpoint 亦未重新驗證，均維持 `not observed`；Entry baseline 仍保留，但不假設狀態未變。
- 最高優先項目 `WBS-6-TRANSACTION-UX-2` 已完成。Flutter/API 本地測試、canonical dev 100% traffic 切換及 Chrome authenticated read-only acceptance 均通過；持股、交易月份／明細、年度報表與表單可載入，缺價／partial 與 Mart pending 狀態正確顯示。操作表單後皆取消，沒有修改個人帳本。此項不是 Dev Pilot Entry blocker。新 Mart 會保存每檔行情日，早於組合估值日的行情標為 stale。

## 下一個執行序列

1. **繼續 `WBS-8-DEV-PILOT-RUN` 六個月 evidence window。**
   - Checkpoint 001 已記錄於 [`pilot-operational-evidence.md`](pilot-operational-evidence.md)；它保留自然 Scheduler failure、版本化 repair、三個 bounded acceptance，以及目前 `not observed` 的 evidence categories。
   - 下一個 runtime evidence boundary 是 **repair 後的下一筆自然 Scheduler execution**：必須觀察真實自動排程是否能正確避開休市日並走到終態；在該 execution 實際存在前保持 pending，不用手動 bounded run 代替。
   - 起點 `pilot_started_at=2026-09-24T15:29:19Z`；後續仍需持續累積 Scheduler／ingestion／analysis、backup／restore、outcome、usefulness、cost、manual intervention、recurring failure 與 security／privacy evidence。
   - 本原子 task 完成後停止；下一個原子項目必須依 [`todo.md`](todo.md) 的模型確認規則另行選定與確認，不自動開始。
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
4. [`pilot-operational-evidence.md`](pilot-operational-evidence.md) 查六個月 evidence window 的新增 bounded checkpoint；[`spec/operations-and-testing.md`](spec/operations-and-testing.md) 查完整歷史 evidence ledger；交易日曆修復 procedure 與 bounded acceptance evidence 見 [`runbook-pilot-calendar-repair.md`](runbook-pilot-calendar-repair.md)。
5. `archive/` 只用於歷史原因與被取代設計。

文件修改、commit 或 status 摘要更新本身，都不代表功能完成。
