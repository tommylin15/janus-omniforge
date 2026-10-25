# Janus｜管理里程碑與跨線合流（2026-10-24）

本檔只記**交付節點與責任**，不是第二份 TODO 或完成百分比。**唯一未完成工項及實際狀態見 [TODO](../todo.md)，跨線完整依賴與互斥規則見 [WBS](../wbs.md)，工程完成看 [Operations](../spec/operations-and-testing.md)**。舊 10/19 的「單一 M-PRE→D07→D08、24月完整度及 BQ 前置」里程碑為歷史截面，不再作最新工項阻擋；原收據在 [archive](../archive/wbs-milestones-before-consolidation-2026-10-19.md)。

| 里程碑 | 責任 WBS／前置 | 允許並行與最終合流 |
|---|---|---|
| **M0-OPS**：Controller 57 筆狀態安全收斂／備份自然作業收據 | WBS-3/7/8；P0-2 需 lease、artifact、consumer fencing；P0-1 只驗首個自然 occurrence | 能與 research/UI 唯讀並行；**同一 Controller rollout 與隊列變更須互斥** |
| **M1-DATA**：research release/preflight/PIT/單位與 C0-Live→C1-A 讀者證據 | WBS-3/5/7；[資料治理](../spec/data-governance.md)、[研究版本索引](../research/00-四模型最新版本索引.md) | 資料分組、reader 盤點可平行；**C1-B physical DROP/DELETE 仍不得進行**，正式清掃另需有界准入與 rollback |
| **M1-UX**：A-CHANGE 現役功能驗收與 Janus 2.0 簡化 | WBS-5/6；[變化判讀](../spec/change-analysis.md)、[UI](../ui.md) | 可與 M0/M1-DATA/M2-ROLE 並行；與第五角色的 RV-05 合流 API/Owner/UI |
| **M1-RV**：估值參考區間（第五角色） | WBS-5/6；[Valuation Range SPEC](../spec/valuation-range.md)，RV-01/02→03→04→05→06 | 確定性首版與第04 Valuation 研究不互相阻塞；必在真實來源/資料時點/API/UI readback 後才完成 |
| **M2-ROLE**：四角色 Quant/Risk/Fundamental/Valuation 研究／各自 promotion | WBS-5/8；[時間契約](../spec/model-feature-time-contract.md)、[生命週期](../spec/model-lifecycle.md) | 四角色各自 freeze/OOS/source/PIT，僅共用已驗資料；Risk 依 [§1.12](../PROJECT_RULES.md) 仍有嚴格獨立前瞻 gate，不得偷切 ACTIVE |
| **M3-INTEGRATE**：D08 Fact Pack／CEO／Admin／Owner | WBS-5/6/8；[D08 卡](../archive/document-cleanup-2026-10-25/execution-cards/d08-ceo-admin-owner-report.md) | 事實報告先做；各模型輸出需先通過**該角色**發布驗收，無須一次等齊五模型 |

共同完成定義：SPEC 契約 → WBS 前置 → TODO 未完工項 → tests/CI → 受控 dev/runtime readback → Operations 收據 → 關閉 TODO；不以本檔文件已更新稱工程 PASS。
