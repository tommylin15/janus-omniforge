# Janus — Work Breakdown Structure

更新：2026-10-19
狀態：索引；執行順序與未完成條件以 [TODO](todo.md) 為準

## AI 最小讀取規則

收到 WBS ID 時，先從 TODO 取得範圍與驗收，再只讀對應切片及其直接引用的 SPEC／UI 切片。一般每次只執行一個 WBS；2026-10-05 的 A／B／C 合併工作組依 PROJECT_RULES 例外，以指定整組執行、共用驗收，原 WBS acceptance 保留。只有使用者明確指定全部組才跨組連續執行；不在 dataset／檔案／畫面之間反覆停等。操作見 [Codex 執行指令](codex-execution-plan.md)，範圍與狀態仍只看 [TODO](todo.md)。

## Dev 平行上線驗收原則

- 目前 `dev` 是個人使用階段的真實平行上線環境；WBS 的主要驗收預設走實際 GCP dev URL、真實 OAuth、真實持久化資料、真實 API／MCP／provider 與既有 Job／Scheduler，而不是先以 mock／fixture／假資料取代。
- 本機 unit／contract／fixture 保留作快速回歸或故障注入；不得取代主要 real-path acceptance。
- Production 只代表未來對外、多使用者、HA／SLA 或更嚴格營運需求；除非 WBS 明確屬於該範圍，不能以尚未 productionize 阻擋目前 dev 真實使用。
- 程式已寫完但未部署、未觸發、未連真實依賴或只跑模擬資料，不得宣稱整體完成；partial success 不得包裝成 full success。
- secret redaction、owner/auth boundary、migration 可追蹤、重要資料可重建／備份、不可逆大量刪除防護，以及 research/canonical/PIT/provenance/source authorization 邊界仍有效。

## AI角色分工（非工具可用性閘門）

舊 Sol／Luna 是歷史分工註記，不是模型選擇或前置閘門。**新工程順序以TODO為準：A-CHANGE → D07-PRE → D07 → D08；STAGE獨立收尾**（見 [TODO](todo.md)）；下表 A／B／C、WBS3/4/5/6 的已結案範圍只用於找舊設計、修復所屬模組及稽核，不能成為另列的 backlog。工程依現有能力與 PROJECT_RULES 在 main 執行，不主動建 branch/PR。

## WBS 路由

| 任務／WBS | 預設模型 | 必讀切片 | 條件增讀 |
|---|---|---|---|
| A-CHANGE：站內變化判讀 | 依當前能力 | [方案A卡](execution-cards/a-change-analysis.md)、[契約](spec/change-analysis.md) | WBS-5/6增量；A1→A2→A3→A4整包驗收，不重開已結案D03 |
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
