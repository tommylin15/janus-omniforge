# 2026-10-15 暫停交接

使用者要求先暫停、更新全部進度文件後同步 GitHub。本 checkpoint 保存前次已推送 `a302c268` 之後的未發布原始碼；不派送新 Release、部署、Job 或正式流量切換。以下不把原始碼完成當成 runtime PASS。

## 已確認的真實結果

- Preview／四 Jobs 來源：`4d058c47ac62ad7328f9f7c0e9fcd4ef4f1ac7b1`。完整 [Release #38674231933](https://github.com/tommylin15/janus-omniforge/actions/runs/38674231933)、[candidate #38674767979](https://github.com/tommylin15/janus-omniforge/actions/runs/38674767979)、[auth boundary #38674988598](https://github.com/tommylin15/janus-omniforge/actions/runs/38674988598)、[Preview #38675180575](https://github.com/tommylin15/janus-omniforge/actions/runs/38675180575) PASS。交易代號／名稱第一字下拉及鍵盤選取已在此版本；真人登入畫面仍 NOT_VERIFIED。
- [四 Jobs #38676820532](https://github.com/tommylin15/janus-omniforge/actions/runs/38676820532) PASS，8 canaries 成功、Scheduler 恢復。先前失敗 #38675277641 經 exact recovery #38676493330 恢復；歷史失敗不改寫。
- 費稅 [preview #38679664257](https://github.com/tommylin15/janus-omniforge/actions/runs/38679664257) PASS：154 筆有效交易、88 筆需更正。[apply #38680770336](https://github.com/tommylin15/janus-omniforge/actions/runs/38680770336) PASS：88 組 reversal／replacement，ledger176→352，profile3／折扣0.4，零待更正與 Private Mart checkpoint 檢查通過。MCP 讀回8持股股數不變；沒有製造測試交易。首次 apply #38680407739 在 pre-GCP 測試失敗，未寫資料。
- 059 已由既有 operator IAP／postgres owner 遷移並以 control 身分驗證欄位／ACL。00697B 官方身分 [migration060 #38679346846](https://github.com/tommylin15/janus-omniforge/actions/runs/38679346846) PASS；目前身份 available，但00697B價格仍 missing，完整估值／PnL PARTIAL。
- [公開效能 #38677467684](https://github.com/tommylin15/janus-omniforge/actions/runs/38677467684)：30/30，P50 65.1ms、P95 72.1ms、最大6673.38ms。僅公開 API 讀取，不代表登入 UI、冷啟動或保存後可見 P95。
- 全市場 Bootstrap #38575674367、同日 Cached #38651225144 PASS，1988股票，17/17 cache hits、零重發佈。舊 queue canary #38653931699 原 workflow 仍 FAIL；exact request 唯讀已確認 SUCCEEDED、無 active queue，不等於 UI 按鈕全鏈路通過。

## 本次保存但尚未部署的進度

- TPEx：修復 timedelta 匯入；14:30前允許前一交易日官方收盤，拒絕當日資料；跨 handoff 重抓來源。00697B 缺價仍需新版本與 owner reconcile 證明。
- 首頁：057 bootstrap 成功後補建初始 home snapshot，保留同日 cached 零發佈規則；尚未在 runtime 補建驗證。
- 備份：既有 VM／container 中隨機隔離臨時 DB 還原，驗證備份 hash／大小、owner／ledger／更正鏈完整性並清理，只輸出摘要；workflow／runbook 同步。原 timer enabled／active，新 executor 未安裝，未產生新 controller 備份、未真實還原、未停原 timer。既有 operator IAP 可用，CI WIF IAM 限制未擴權。
- 本機整合 targeted tests 65 PASS；後續 workflow 呼叫接線後相關45 PASS；備份相關10 PASS及 Bash語法 PASS。費稅專用無 API依賴環境27 PASS。本次暫停同步前另重跑還原／schema migration／TPEx直接相關41項 PASS，文件連結與diff檢查PASS。這些不是此 checkpoint 的完整 Release；最新草稿未跑新全套 CI／真實隔離 PostgreSQL gate。
- Release request 撤回未送出的 attempt43，保留既有 attempt42，不因同步自動發 Release；fee repair request 改回 ledger352／profile3 唯讀 preview，保留最後 apply 收據，不重送 apply。
- 不提交 `.cicd-v2-work/` 與 `token-savior/` 等非本次成果／私有暫存。

## 恢復入口（仍按 TODO 1～5）

1. 以新 SHA 完整 Release／candidate／auth boundary／Preview／四 Jobs 驗證 TPEx 修正，受控 owner reconcile 確認00697B及全持股估值；完成交易保存、試算、損益與重算端到端驗收，不重送歷史費稅 apply。
2. 執行057初始快照補建並讀回首頁／快取；保留既有全市場與cached證據。
3. 通用圖表／四頁整合與實際登入瀏覽器、390×844及冷暖／保存可見效能；只用外部Chrome分頁控制，未接通不能冒充已驗收。
4. 按 runbook 完成 controller 真備份、隔離還原、executor驗證後才交接原timer；不啟動 Cloud Build 或擴充IAM。
5. 集中完成適用測試與 dev gates，通過才受控正式API切流及讀回。目前正式100%路由未變，整體1～5仍PARTIAL。
