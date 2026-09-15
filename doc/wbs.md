# Janus — Work Breakdown Structure

狀態：索引；執行順序與未完成條件以 [TODO](todo.md) 為準

## AI 最小讀取規則

收到 WBS ID 時，先從 TODO 取得範圍與驗收，再只讀對應切片及其直接引用的 SPEC／UI 切片。每次只執行一個 WBS；未指定 WBS 時不得預讀全部切片。

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
| 4J：個人記帳、筆記、關注股 | 【Sol】 | [WBS 4J](wbs/wbs-4j-personal-workspace.md) | AI 整合才讀 4C；曝險才讀 4R |
| 4C：多供應商私人助理／MCP／Skills | 【Sol】 | [WBS 4C](wbs/wbs-4c-ai-chat.md) | 需要持股／筆記 context 時讀 4J；UI 切片讀 User UI |
| 4R：個人曝險、績效與壓力測試 | 【Sol】 | [WBS 4R](wbs/wbs-4r-personal-risk.md) | AI 解釋時讀 4C |
| 5：Intelligence Mart | 【Sol】 | [WBS 5](wbs/wbs-5-intelligence-mart.md) | 不預讀私人 WBS |
| 6：FastAPI、Flutter、Admin | 依 TODO | [WBS 6](wbs/wbs-6-api-and-apps.md) | 依目標入口讀 User 或 Admin UI |
| 7：安全、監控、FinOps | 【Sol】 | [WBS 7](wbs/wbs-7-security-finops.md) | 依受影響服務增讀其 WBS |
| 8：PIT、QA、發布 | 依 TODO | [WBS 8](wbs/wbs-8-qa-release.md) | 需要現況證據時讀測試摘要 |
| Research Context（Pilot Evolution） | 【Sol】 | [WBS 3](wbs/wbs-3-ingestion-admin.md)、[4J](wbs/wbs-4j-personal-workspace.md)、[5](wbs/wbs-5-intelligence-mart.md)、[6](wbs/wbs-6-api-and-apps.md)、[8](wbs/wbs-8-qa-release.md) | 不重開 WBS 4C；Supply-chain 依 Gate A–E |
| 里程碑規劃 | 【Sol】 | [建議里程碑](wbs/milestones.md) | 不作單一 WBS 的驗收來源 |
