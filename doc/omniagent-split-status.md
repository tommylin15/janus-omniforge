# Janus／omniAgent Hard Split — 歷史狀態入口

更新：2026-09-24

Janus source hard split、GCP dev runtime acceptance 與 Janus 專用 runtime cleanup 已完成；通用 Chat／Agent runtime 已不屬於 Janus scope。omniAgent 後續 runtime／gateway／chat 的保留、清理與自身驗收已移至獨立專案，**不再是 Janus active TODO、Pilot Entry gate 或完成前置條件**。

本文件只保留歷史導航，避免舊 Phase 6–9 語意繼續污染 Janus active 文件。

## Janus 現況

- Janus 保留投資 User／Admin、domain API，以及 authenticated read-only MCP／OAuth connector。
- Janus 不再擁有 generic Chat UI、provider runtime、Agent Gateway、Skills、approval 或 Chat persistence。
- 目前 Janus 的未完成工作以 [`todo.md`](todo.md) 為準。
- 最新 runtime／MCP／OAuth／deployment evidence 以 [`spec/operations-and-testing.md`](spec/operations-and-testing.md) 為準。
- Secret 與 runtime inventory 以 [`secret_list.md`](secret_list.md) 為準。

## 歷史證據

2026-09-23 hard split checkpoint、舊 Phase 5–9 狀態、當時的 build／digest／revision 與已取代計畫保留在：

- [`archive/todo-history-and-completed-2026-09-23.md`](archive/todo-history-and-completed-2026-09-23.md)
- [`archive/wbs-4c-janus-assistant-plan-superseded-2026-09-23.md`](archive/wbs-4c-janus-assistant-plan-superseded-2026-09-23.md)
- [`archive/omniagent-split-preparation-superseded-2026-09-23.txt`](archive/omniagent-split-preparation-superseded-2026-09-23.txt)

需要判斷目前是否完成時，不應從這些歷史 snapshot 反推現況；應重新查看 GitHub implementation、tests／CI 與 live runtime evidence。
