# janus-omniforge

GCP-first AI lakehouse investment research platform

Janus 的 Flutter source 現僅持有投資 User/Admin UI；generic Chat UI source 已拆至 omniAgent。API Docker build 固定拆分前 User App Web artifact，以保留 live／rollback Chat UI；此部署保護尚未經新 image 的 GCP dev 驗收。OAuth、runtime dispatch、Janus context、Skills/MCP、歷史 migration 與 live cutover 尚未完成，詳見 [dev 部署 runbook](doc/runbook-dev-deploy.md)。

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
