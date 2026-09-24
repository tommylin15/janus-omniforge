# WBS 4C — Janus Chat／Agent 工作已退役

Janus 不再擁有通用 Chat UI、provider runtime、Agent Gateway、Skills、approval 或 Chat persistence；相關產品責任已移出 Janus。舊規劃與驗收條件保存在[歷史 WBS](../archive/wbs-4c-janus-assistant-plan-superseded-2026-09-23.md)，不得作為 Janus 現行開發指示。

Janus 保留自己的 authenticated read-only MCP／OAuth connector 與投資 domain API。這些能力的現行未完成驗收以 [`../todo.md`](../todo.md) 為準，最新 runtime evidence 見 [`../spec/operations-and-testing.md`](../spec/operations-and-testing.md)。

Janus／omniAgent hard split 的 2026-09-23 checkpoint 已轉為歷史資料；omniAgent 後續 gateway／chat runtime 的保留、清理與自身驗收屬於獨立專案，不再是 Janus WBS、Pilot Entry gate 或完成條件。歷史入口見 [`../omniagent-split-status.md`](../omniagent-split-status.md)。
