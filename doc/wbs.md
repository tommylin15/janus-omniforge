# Janus — Work Breakdown Structure

狀態：索引；執行順序與未完成條件以 [TODO](todo.md) 為準

## AI 最小讀取規則

收到 WBS ID 時，先從 TODO 取得範圍與驗收，再只讀對應切片及其直接引用的 SPEC／UI 切片。每次只執行一個 WBS；未指定 WBS 時不得預讀全部切片。

## Dev 平行上線驗收原則

- 目前 `dev` 是個人使用階段的真實平行上線環境；WBS 的主要驗收預設走實際 GCP dev URL、真實 OAuth、真實持久化資料、真實 API／MCP／provider 與既有 Job／Scheduler，而不是先以 mock／fixture／假資料取代。
- 本機 unit／contract／fixture 仍保留，但定位是快速回歸或故障注入；只有 timeout、cancel、disconnect、list-changed、secret-redaction 等真實服務不適合故意製造的情境，才以 fixture 作主要證據。
- 「productionization／Production」只代表未來對外、多使用者、HA／SLA 或更嚴格營運需求；除非 WBS 明確屬於該範圍，不能以尚未 productionize 阻擋目前 dev 的個人真實使用。
- 完成仍需真實證據：程式已寫完但未部署、未觸發、未連真實依賴或只跑模擬資料，不得宣稱整體完成。partial success 不得包裝成 full success。
- 最低安全底線仍有效：secret redaction、owner/auth boundary、migration 可追蹤、重要資料可重建／備份、不可逆大量刪除防護，以及 research/canonical/PIT/provenance/source authorization 邊界。

## 模型執行閘門

- 每個待辦以 TODO 內的【Sol】／【Luna】為準；混合任務先拆成可獨立驗收的最小切片。
- 每次準備執行下一個待辦時，AI 必須先只回報「建議模型：【Sol】」或「建議模型：【Luna】」及任務 ID／名稱，不得開始修改、部署或執行驗收。
- 使用者明確回覆已完成模型切換後，才正式執行該待辦；完成後停止，下一個待辦重新確認模型。
- 【Sol】用於架構、Core／Iceberg／PostgreSQL 底層、安全／OAuth、高風險疑難排解；【Luna】用於 UI、標準 CRUD／API 串接與規則明確的測試。

## WBS 路由

| 任務／WBS | 預設模型 | 必讀切片 | 條件增讀 |
|---|---|---|---|
| 已完成證據定位 | 【Luna】 | [已完成工作](wbs/completed-index.md) | 只在需要歷史證據時讀 archive |
| 3：Ingestion／Core／Admin Data Operations | 【Sol】 | [WBS 3](wbs/wbs-3-ingestion-admin.md) | UI 變更再讀 Admin UI |
| 4J：個人記帳、筆記、關注股 | 【Sol】 | [WBS 4J](wbs/wbs-4j-personal-workspace.md) | 外部助理只透過 Janus domain API／MCP 讀授權 context；曝險才讀 4R |
| 4C：Janus Chat／Agent（已退役） | 歷史 | [目前責任摘要](wbs/wbs-4c-ai-chat.md) | 舊規劃只供查閱；split gate 見 [狀態文件](omniagent-split-status.md) |
| 4R：個人曝險、績效與壓力測試 | 【Sol】 | [WBS 4R](wbs/wbs-4r-personal-risk.md) | 若交由外部助理解釋，依 bounded context／MCP 契約 |
| 5：Intelligence Mart／Fact Pack／AI analysts | 【Sol】 | [WBS 5](wbs/wbs-5-intelligence-mart.md) | 不預讀私人 WBS；atomic slices 依 TODO 的 Pilot M1–M3 |
| 6：FastAPI、Flutter、Admin workspace | 依 TODO | [WBS 6](wbs/wbs-6-api-and-apps.md) | 依目標入口讀 User 或 Admin UI；Admin slices 依 Pilot M4–M6 |
| 7：安全、監控、FinOps | 【Sol】 | [WBS 7](wbs/wbs-7-security-finops.md) | 依受影響服務增讀其 WBS |
| 8：PIT、QA、發布／Pilot AI evaluation | 依 TODO | [WBS 8](wbs/wbs-8-qa-release.md) | 需要現況證據時讀測試摘要；Mart AI evaluation 為 Planned Pilot M6 slice |
| Research Context（Pilot Evolution） | 【Sol】 | [WBS 3](wbs/wbs-3-ingestion-admin.md)、[4J](wbs/wbs-4j-personal-workspace.md)、[5](wbs/wbs-5-intelligence-mart.md)、[6](wbs/wbs-6-api-and-apps.md)、[8](wbs/wbs-8-qa-release.md) | 不重開 WBS 4C；Supply-chain 依 Gate A–E |
| 里程碑規劃 | 【Sol】 | [建議里程碑](wbs/milestones.md) | 不作單一 WBS 的驗收來源 |
