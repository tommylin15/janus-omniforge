# GCP Dev Secret Bundle 清單

更新日期：2026-09-06  
Project：`gen-lang-client-0593591102`  
Region：`us-central1`

本表只記錄 Secret resource、用途、欄位名稱、消費者與 IAM metadata；不記錄
任何 payload、token、password、API key 或 auth 內容。

| Secret | 類型／欄位名稱（不含值） | 消費者 | version 狀態 | 目前 IAM metadata |
|---|---|---|---|---|
| `janus-agent-provider-bundle` | `gemini_api_key`, `openrouter_api_key`, `mcp_owner_signing_key` | `janus-agent-gateway` | latest enabled | Gateway `secretAccessor` |
| `janus-codex-owner-a` | Codex managed `auth.json` payload | Gateway；owner `00000000-0000-4000-8000-000000000001` | version 1 destroyed | Gateway `secretAccessor`, `secretVersionAdder`, `secretVersionManager` |
| `janus-codex-owner-b` | Codex managed `auth.json` payload | Gateway；owner `00000000-0000-4000-8000-000000000002` | version 1 enabled | Gateway `secretAccessor`, `secretVersionAdder`, `secretVersionManager` |
| `janus-codex-owner-temp` | acceptance-only／legacy temporary Codex auth payload | Gateway legacy fixture | metadata not inspected | Gateway `secretAccessor` |
| `janus-postgres-api-bundle` | `database_url`, `catalog_password`, `core_catalog_password`, `google_user_client_id`, `mcp_owner_signing_key` | `janus-user-api` | latest enabled | API `secretAccessor` |
| `janus-postgres-ingestion-bundle` | `control_password`, `catalog_password` | ingestion Cloud Run Job | latest enabled | 尚未授予 runtime IAM |
| `janus-postgres-mart-bundle` | `catalog_password`, `publication_password` | Mart Cloud Run Job | latest enabled | 尚未授予 runtime IAM |
| `janus-postgres-pipeline-bundle` | pipeline／private pipeline database bundle | `janus-private-pipeline` | latest enabled | Pipeline `secretAccessor` |
| `janus-postgres-web-bundle` | `control_password`, `catalog_password` | Admin Web | latest enabled | 尚未授予 runtime IAM |

## 使用規則

- `janus-agent-provider-bundle` 是 MCP signing key 的 bundle 來源；不要重新建立已被 consolidation 移除的獨立 signing Secret。
- Owner Codex auth 以 owner UUID 對應 allowlist；A／B Secret 不得合併，temp Secret 不得作正式驗收證據。
- Rotation 先建立並驗證新 version，再銷毀舊 version；不得只 disable。
- 本表是 2026-09-06 GCP dev metadata 快照，不代表 production topology 或 production 授權。
