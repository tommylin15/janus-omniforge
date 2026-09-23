# janus-omniforge

GCP-first AI lakehouse investment research platform

Janus source 已移除 generic Agent／Chat runtime，保留投資 User／Admin UI、Janus MCP／OAuth 與既有資料。Phase 0–5 是已完成的遷移檢查點，不代表 live Chat writer 已切走：目前 GCP dev `janus-api` 仍是舊 revision。source 已本機驗證並提交；後續需推送、部署並完成 GCP dev runtime acceptance，再清理專用舊 runtime。各 gate 見 [split status](doc/omniagent-split-status.md) 與 [dev deployment runbook](doc/runbook-dev-deploy.md)。

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
