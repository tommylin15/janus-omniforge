# GCP Dev Secret Bundle 清單

更新日期：2026-09-10
Project：`gen-lang-client-0593591102`  
Region：`us-central1`

本表是本次從 GCP Secret Manager 重新讀取的 metadata 快照，只記錄 Secret
resource、用途、欄位名稱、消費者、版本狀態與 IAM metadata；不記錄任何
payload、token、password、API key 或 auth 內容。GCP dev 目前共 8 個 Secret。

| Secret | 類型／欄位名稱（不含值） | 消費者 | version 狀態 | 目前 IAM metadata |
|---|---|---|---|---|
| `janus-agent-provider-bundle` | `gemini_api_key`, `openrouter_api_key`, `mcp_owner_signing_key` | `janus-agent-gateway` | v1 destroyed；v2 enabled | Gateway `secretAccessor` |
| `janus-codex-owner-a` | Codex managed `auth.json` payload | Gateway；owner `00000000-0000-4000-8000-000000000001` | v1–v5 destroyed | Gateway `secretAccessor`, `secretVersionAdder`, `secretVersionManager` |
| `janus-codex-owner-b` | Codex managed `auth.json` payload | Gateway；owner `00000000-0000-4000-8000-000000000002` | v1–v4 destroyed；v5–v7 enabled | Gateway `secretAccessor`, `secretVersionAdder`, `secretVersionManager` |
| `janus-postgres-api-bundle` | `database_url`, `catalog_password`, `core_catalog_password`, `google_user_client_id`, `mcp_owner_signing_key` | `janus-user-api`；private-pipeline Core catalog | v1–v4 destroyed；v5–v7 enabled | API、Pipeline `secretAccessor` |
| `janus-postgres-ingestion-bundle` | `control_password`, `catalog_password` | ingestion Cloud Run Job | v1 enabled | `ingestion-core` `secretAccessor` |
| `janus-postgres-mart-bundle` | `catalog_password`, `publication_password` | Mart Cloud Run Job | v1 enabled | `intelligence-mart` `secretAccessor` |
| `janus-postgres-pipeline-bundle` | `database_url`, `catalog_password` | `janus-private-pipeline`（private DB／catalog） | v1 enabled | Pipeline `secretAccessor` |
| `janus-postgres-web-bundle` | `control_password`, `catalog_password`, `google_client_id`, `session_secret` | Admin Web | v1–v2 destroyed；v3 enabled | `web-runtime` `secretAccessor` |

## 使用規則

- `janus-agent-provider-bundle` 是 MCP signing key 的 bundle 來源；不要重新建立獨立 signing Secret。
- Owner Codex auth 以 owner UUID 對應 allowlist；A／B Secret 不得合併。
- Rotation 先建立並驗證新 version，再銷毀舊 version；不得只 disable。
- 本次重讀未記錄或輸出任何 Secret payload value；pipeline bundle 僅核對 JSON key 名稱。

## Runtime reference resolution（2026-09-10）

- `janus-ingestion-core` 已移除 alias／individual refs，只引用
  `janus-postgres-ingestion-bundle:latest`；Job Ready，runtime probe
  `janus-ingestion-core-n8mh2` 成功。
- `janus-intelligence-mart` 已移除 individual refs，只引用
  `janus-postgres-mart-bundle:latest`；Job Ready，runtime probe
  `janus-intelligence-mart-j2hgn` 成功。
- `janus-private-pipeline` 已移除 3 個 individual refs，改用
  `janus-postgres-pipeline-bundle:latest` 加
  `janus-postgres-api-bundle:latest`（Core catalog 欄位）；Job Ready，runtime
  probe `janus-private-pipeline-rvmct` 成功。
- 舊 execution `janus-private-pipeline-k7gtz` 的 bundle schema failure 是修正前證據，
  不列為驗收成功；以上是 dev runtime 設定，不代表 production topology 或授權。
