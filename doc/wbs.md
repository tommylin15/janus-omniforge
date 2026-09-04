# Janus — Work Breakdown Structure

狀態：索引；執行順序與未完成條件以 [TODO](todo.md) 為準

## AI 最小讀取規則

收到 WBS ID 時，先從 TODO 取得範圍與驗收，再只讀對應切片及其直接引用的 SPEC／UI 切片。每次只執行一個 WBS；未指定 WBS 時不得預讀全部切片。

## WBS 路由

| 任務／WBS | 必讀切片 | 條件增讀 |
|---|---|---|
| 已完成證據定位 | [已完成工作](wbs/completed-index.md) | 只在需要歷史證據時讀 archive |
| 3：Ingestion／Core／Admin Data Operations | [WBS 3](wbs/wbs-3-ingestion-admin.md) | UI 變更再讀 Admin UI |
| 4J：個人記帳、筆記、關注股 | [WBS 4J](wbs/wbs-4j-personal-workspace.md) | AI 整合才讀 4C；曝險才讀 4R |
| 4C：Codex／ChatGPT／Gemini 私人聊天室 | [WBS 4C](wbs/wbs-4c-ai-chat.md) | 需要持股／筆記 context 時讀 4J |
| 4R：個人曝險、績效與壓力測試 | [WBS 4R](wbs/wbs-4r-personal-risk.md) | AI 解釋時讀 4C |
| 5：Intelligence Mart | [WBS 5](wbs/wbs-5-intelligence-mart.md) | 不預讀私人 WBS |
| 6：FastAPI、Flutter、Admin | [WBS 6](wbs/wbs-6-api-and-apps.md) | 依目標入口讀 User 或 Admin UI |
| 7：安全、監控、FinOps | [WBS 7](wbs/wbs-7-security-finops.md) | 依受影響服務增讀其 WBS |
| 8：PIT、QA、發布 | [WBS 8](wbs/wbs-8-qa-release.md) | 需要現況證據時讀測試摘要 |
| 里程碑規劃 | [建議里程碑](wbs/milestones.md) | 不作單一 WBS 的驗收來源 |
