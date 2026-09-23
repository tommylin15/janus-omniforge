# janus-omniforge

GCP-first AI lakehouse investment research platform

Janus source 已移除 generic Agent／Chat runtime，保留投資 User／Admin UI、Janus MCP／OAuth 與既有資料。來源變更已在本機測試並建立 commit；推送、GCP dev 部署與 runtime 驗收尚待完成，目前 live `janus-api` 仍是舊 revision。進度與 gate 見 [split status](doc/omniagent-split-status.md)。

> Codex 開發前必須先閱讀 `AGENTS.md` 與 `doc/PROJECT_RULES.md`。

## Repository layout

| Path | Responsibility |
|---|---|
| `apps/web` | Public and administrative web application |
| `jobs/ingestion-core` | Source ingestion, Stage writing, and Core processing |
| `jobs/intelligence-mart` | Features, agent analysis, aggregation, and Mart writing |
| `services/trino` | Trino image and runtime configuration |
| `packages/contracts` | Shared versioned data and event contracts |
| `packages/governance` | Governance policy and deterministic constants |
| `packages/provenance` | Provenance models and validation |
| `packages/observability` | Shared telemetry and safe error conventions |
| `infra` | Declarative infrastructure; never apply without explicit authorization |
| `tests/contract` | Cross-component contract tests |
| `tests/e2e` | End-to-end tests |

The directories are intentionally implementation-neutral until their owning WBS
selects toolchains and pins versions. Current scope, gates, and remaining manual
decisions are recorded in `doc/todo.md`.
