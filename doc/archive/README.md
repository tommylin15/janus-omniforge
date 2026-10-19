# Janus 文件封存區

`doc/archive/` 只保存已完成、已取代或特定日期的歷史 checkpoint，用於追溯與稽核；不得作為目前 execution queue、runtime 現況或契約的第一來源。

查詢順序：

1. 目前要做什麼：`../todo.md`
2. 目前契約：`../spec.md`、`../wbs.md`、`../ui.md`
3. 目前實作／完成狀態：GitHub `main`、tests／CI、deployment／runtime evidence，以及 `../spec/operations-and-testing.md`
4. 只有需要歷史原因、舊 evidence 或被取代設計時才進本目錄

## 2026-10-19 整編追溯

- [整理前 TODO 全文](todo-before-consolidation-2026-10-19.md)、[整理前 Status 全文](status-before-consolidation-2026-10-19.md)、[整理前 AI 開發指令](codex-execution-plan-before-consolidation-2026-10-19.md)、[舊里程碑](wbs-milestones-before-consolidation-2026-10-19.md)：保存多輪歷史狀態與當時命令，**不得復活成 active**。
- 舊 D01～D04 支線、Batch 10/13、補資料 S0、早期 Data Coverage、Admin 六頁、Admin Stocks guide、部署事故、Janus／omniAgent hard split、文件盤點報告等已從 doc 根目錄搬入這裡，保留原文與時間背景。
- [本次文件治理盤點與搬移清冊](documentation-consolidation-2026-10-19.md) 記錄 scope、數量、已處理與未覆蓋驗證。**完整 WBS／SPEC／UI／Runbook 仍在 active 區域，勿從本資料夾推導新的授權。**

封存文件可保留當時的 build ID、revision、digest、舊資源名稱與未完成判斷；這些資料只代表該 checkpoint，不能自動外推為目前狀態。
