# janus-omniforge

GCP-first AI lakehouse investment research platform.

Janus 目前以 GCP `dev` 作為個人使用階段的真實平行上線環境。Janus source 不再包含通用 Chat／Agent runtime；保留投資 User／Admin、domain API，以及 authenticated read-only MCP／OAuth connector。**目前功能、驗收與剩餘工作以 repository 實作、測試／CI、GCP runtime evidence 與 `doc/status.md`／`doc/todo.md` 為準，不在 README 固定 revision、image digest 或一次性 checkpoint。**

現階段唯一待辦順序：**D07-PRE（Colab 單一資料與模型訓練流程）→ D07 五角色模型品質 → D08 受控 CEO 報告**。已結案 D01～D05、DRL-01、FINOPS-AB、背景補收及 Admin v2 不重啟；詳見 [目前 TODO](doc/todo.md)、[專案管理／重大風險](doc/project-management.md)、[AI 開發指示](doc/codex-execution-plan.md)。

開始工作前先讀：

1. [文件入口與權威地圖](doc/README.md)
2. [專案作業規則](doc/PROJECT_RULES.md)
3. [目前狀態與下一步](doc/status.md)
4. [完整 TODO](doc/todo.md)

需要契約時由 [SPEC](doc/spec.md)、[WBS](doc/wbs.md)、[UI](doc/ui.md) 索引進入對應切片；需要完整驗收／runtime 證據時讀 [Operations and Testing](doc/spec/operations-and-testing.md)。歷史 checkpoint 與已取代規劃只在 `doc/archive/` 查閱。

## Repository layout

| Path | Responsibility |
|---|---|
| `apps/user_app` | Flutter User／Admin application |
| `apps/web` | Web runtime helpers and legacy-compatible web surface |
| `jobs/ingestion-core` | Source ingestion, Stage writing, and Core processing |
| `jobs/intelligence-mart` | Features, governed analysis, aggregation, and Mart writing |
| `services/api` | Janus API, MCP／OAuth, and application delivery runtime |
| `services/trino` | Trino image and runtime configuration |
| `packages/contracts` | Shared versioned data and event contracts |
| `packages/governance` | Governance policy and deterministic constants |
| `packages/provenance` | Provenance models and validation |
| `packages/observability` | Shared telemetry and safe error conventions |
| `infra` | Infrastructure and migrations; changes follow project authorization rules |
| `tests/contract` | Cross-component contract tests |
| `tests/e2e` | End-to-end tests |
| `doc` | Current governance, specs, WBS, UI, runbooks, evidence indexes, and archive |

> Codex／ChatGPT 開發前必須先遵守 `AGENTS.md` 與 `doc/PROJECT_RULES.md`。文件更新不代表功能已實作、測試或部署完成。
