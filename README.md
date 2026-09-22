# janus-omniforge

GCP-first AI lakehouse investment research platform

Janus → omniAgent split Phases 0–5 are closed as migration checkpoints. Janus Flutter source now owns investment User/Admin UI only; generic Chat UI source is owned by omniAgent. Janus API Docker build pins the pre-split User App Web artifact, and that deployment protection is verified in GCP dev, so the live API can continue serving the legacy Chat path while later cutover work proceeds.

Remaining omniAgent OAuth, live runtime dispatch, real Janus bounded context/MCP integration, historical migration/write ownership, live cutover, cleanup and final documentation/acceptance are **not** unfinished Phase 3–5 work. They are carried forward to Phase 6 deployment planning, Phase 6B real dev deployment/acceptance, Phase 7 Janus cleanup, Phase 8 documentation/stale-reference migration, and Phase 9 final acceptance. See [omniAgent split status](doc/omniagent-split-status.md) and the [dev deployment runbook](doc/runbook-dev-deploy.md).

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
