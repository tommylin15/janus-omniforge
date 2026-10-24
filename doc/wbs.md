# Janus — Work Breakdown Structure

> **2026-10-24 研究精簡決策優先**：本文涉及獨立資料稽核、逐來源補證、全歷史 PIT／精確時間校準、例行週月稽核及自然驗收等待的要求已取消，不再是待辦或發布前置。依 [研究精簡政策](spec/research-simplification.md)，保留必要日期／單位、基本防洩漏與操作安全；歷史證據不改判 PASS。


更新：2026-10-24（跨線依賴矩陣）
狀態：索引；執行順序與未完成條件以 [TODO](todo.md) 為準

## 現行工作順序

[唯一 TODO](todo.md) 是全部 active 工作。備份故障修復、04 估值情境、現有資料 X/Y 與四模型研究可獨立進行；D08 事實報告不等待模型全部完成。共享 writer／部署仍序列化。

來源稽核、歷史 PIT、前瞻新 cohort 與自然觀察均已取消，不形成跨線依賴。C1-A 已結案，C1-B 不在本輪刪資料。歷史 WBS 名稱只作定位，不恢復已取消驗收。

## WBS 路由

| 任務／WBS | 預設模型 | 必讀切片 | 條件增讀 |
|---|---|---|---|
| D07-PRE：Colab 採集／ChatGPT 四模型貼標（不強制產業歷史 PIT） | 依當前能力 | [Active TODO D07-PRE](todo.md)、[研究採集契約](spec/research-collection-gas-drive-colab.md)、[兩入口與產業歸屬 preflight](research/four-model-collection-label-split-v382.md) | 只在需要時讀 [時間契約](spec/model-feature-time-contract.md)；程式交付與實際資料 PIT 分別驗收，不能把產業指數當逐股名冊 |
| A-CHANGE：站內變化判讀 | 依當前能力 | [方案A卡](execution-cards/a-change-analysis.md)、[契約](spec/change-analysis.md) | A1→A4：已在 2026-10-24 使用者端核對完成，USER_ACCEPTED／CLOSED；後續異常需具體證據；不重開已結案D03 |
| A：User／Admin／效能／資料營運 | 【Sol】 | [執行指令 A](codex-execution-plan.md)、[WBS 6](wbs/wbs-6-api-and-apps.md)、[WBS 7](wbs/wbs-7-security-finops.md) | 私人資料讀 4J／4R；Core query／projection 讀相應 SPEC；User／Admin UI |
| B：specialist／cache | 【Sol】 | [執行指令 B](codex-execution-plan.md)、[Specialist Engines](wbs/wbs-5-specialist-engines.md)、[WBS 5](wbs/wbs-5-intelligence-mart.md) | 對應 runtime／retention／Admin 顯示 |
| C：CEO／profile／User 最終整合 | 【Sol】 | [執行指令 C](codex-execution-plan.md)、[WBS 5](wbs/wbs-5-intelligence-mart.md)、[WBS 6](wbs/wbs-6-api-and-apps.md) | API／auth／User／Admin UI；重用 A 未受改動的驗收 |
| 已完成證據定位 | 【Luna】 | [已完成工作](wbs/completed-index.md) | 只在需要歷史證據時讀 archive |
| 3：Ingestion／Core／Admin Data Operations | 【Sol】 | [WBS 3](wbs/wbs-3-ingestion-admin.md) | UI 變更再讀 Admin UI |
| `WBS-3-DATA-SUPPLEMENT-V1` | 【Sol】 | [補資料第一版](wbs/wbs-3-data-supplement-v1.md) | 已結案；維運依 runbook，不重開舊 minimum-floor 工作 |
| 4J：個人記帳、筆記、關注股 | 【Sol】 | [WBS 4J](wbs/wbs-4j-personal-workspace.md) | 外部助理只透過 Janus domain API／MCP 讀授權 context；曝險才讀 4R |
| 4C：Janus Chat／Agent（已退役） | 歷史 | [退役責任摘要](wbs/wbs-4c-ai-chat.md) | 不作 active execution；舊規劃只供 archive 查閱 |
| 4R：個人曝險、績效與壓力測試 | 【Sol】 | [WBS 4R](wbs/wbs-4r-personal-risk.md) | 若交由外部助理解釋，依 bounded context／MCP 契約 |
| 5：Intelligence Mart／Fact Pack／Token-first specialists／On-demand CEO | 【Sol】 | [WBS 5](wbs/wbs-5-intelligence-mart.md) | specialist 細節讀 [Specialist Engines](wbs/wbs-5-specialist-engines.md)；active slices 只看 TODO |
| 6：FastAPI、Flutter、Admin workspace、MCP | 依 TODO | [WBS 6](wbs/wbs-6-api-and-apps.md) | User 讀 User UI；Admin 讀 Admin UI；不預讀另一側 |
| 7：安全、監控、FinOps | 【Sol】 | [WBS 7](wbs/wbs-7-security-finops.md) | 依受影響服務增讀其 WBS |
| 8：PIT、QA、發布／evaluation | 依 TODO | [WBS 8](wbs/wbs-8-qa-release.md) | 需要現況證據時讀 status／operations；歷史 Pilot checkpoint 不覆蓋 active TODO |
| Research Context（Planned） | 【Sol】 | [WBS 3](wbs/wbs-3-ingestion-admin.md)、[4J](wbs/wbs-4j-personal-workspace.md)、[5](wbs/wbs-5-intelligence-mart.md)、[6](wbs/wbs-6-api-and-apps.md)、[8](wbs/wbs-8-qa-release.md) | 只在 active TODO 啟動後執行；不重開 WBS 4C |
| 里程碑規劃 | 索引 | [目前管理里程碑](wbs/milestones.md) | 不作單一 WBS 的驗收來源 |

任何歷史 WBS 名稱、舊 Pilot milestone 或 archive 內容若與 active TODO／SPEC 衝突，不得反向取得 active execution authority。
