# GCP Dev Secret Bundle 清單

更新日期：2026-09-11
Project：`gen-lang-client-0593591102`  
Region：`us-central1`

本表是本次從 GCP Secret Manager 重新讀取的 metadata 快照，只記錄 Secret
resource、用途、欄位名稱、消費者、版本狀態與 IAM metadata；不記錄任何
payload、token、password、API key 或 auth 內容。GCP dev 在遷移前仍有 8 個
Secret；本次唯讀盤點有 6 個 enabled version。若同一 billing account 沒有其他
project 的 active versions，則正好落在每月 6 個免費額度內；Secret container 與
management operation 本身不收費。下列三 bundle 收斂已通過人工安全 gate，但尚未
執行 GCP 寫入與驗收。

| Secret | 類型／欄位名稱（不含值） | 消費者 | version 狀態 | 目前 IAM metadata |
|---|---|---|---|---|
| `janus-agent-provider-bundle` | `gemini_api_key`, `openrouter_api_key`, `mcp_owner_signing_key` | `janus-agent-gateway` | v1 destroyed；v2 enabled | Gateway `secretAccessor` |
| `janus-codex-owner-a` | Codex managed `auth.json` payload | Gateway；owner `00000000-0000-4000-8000-000000000001` | v1–v5 destroyed | Gateway `secretAccessor`, `secretVersionAdder`, `secretVersionManager` |
| `janus-codex-owner-b` | Codex managed `auth.json` payload | Gateway；owner `00000000-0000-4000-8000-000000000002` | v1–v7 destroyed | Gateway `secretAccessor`, `secretVersionAdder`, `secretVersionManager` |
| `janus-postgres-api-bundle` | `database_url`, `catalog_password`, `core_catalog_password`, `google_user_client_id`, `google_user_client_secret`, `mcp_owner_signing_key` | `janus-user-api`；private-pipeline Core catalog | v1–v6 destroyed；v7 enabled | API、Pipeline `secretAccessor` |
| `janus-postgres-ingestion-bundle` | `control_password`, `catalog_password` | ingestion Cloud Run Job | v1 enabled | `ingestion-core` `secretAccessor` |
| `janus-postgres-mart-bundle` | `catalog_password`, `publication_password` | Mart Cloud Run Job | v1 enabled | `intelligence-mart` `secretAccessor` |
| `janus-postgres-pipeline-bundle` | `database_url`, `catalog_password` | `janus-private-pipeline`（private DB／catalog） | v1 enabled | Pipeline `secretAccessor` |
| `janus-postgres-web-bundle` | `control_password`, `catalog_password`, `google_client_id`, `session_secret` | Admin Web | v1–v2 destroyed；v3 enabled | `web-runtime` `secretAccessor` |

## 使用規則

- 目標只保留三個 Secret container：
  - `janus-postgres-api-bundle`：原 API 欄位，加 `web_*` 與 `pipeline_*` 欄位；
    consumer 為 API、Web、private pipeline。
  - `janus-agent-provider-bundle`：原 provider／MCP 欄位，加 `mart_*` 與
    `ingestion_*` 欄位；consumer 為 Agent Gateway、Mart、ingestion。
  - `janus-codex-owners-bundle`：頂層 key 為 allowlisted owner UUID，value 為該
    owner 的 Codex `auth.json` object；兩個 owner 不共用 auth payload。
- 同名 PostgreSQL credential 不可互相覆蓋；Web、Pipeline、Mart、Ingestion 欄位
  使用 workload prefix，程式在遷移期間才允許 fallback 至舊欄位名稱。
- `janus-agent-provider-bundle` 仍是 MCP signing key 的唯一 bundle 來源。
- Rotation 先建立並驗證新 version，再銷毀舊 version；不得只 disable。
- Codex bundle mutation 在目前 `max-instances=1` 下以 process lock 序列化；提高
  instance 數前必須改用 distributed lock／CAS，避免 owner 更新互相覆蓋。
- 本次重讀只輸出 JSON key 名稱，未記錄或輸出任何 Secret payload value。

## 遷移順序（尚未執行）

1. `ALLOW_SECRET_BUNDLE_MIGRATION=true scripts/gcp/migrate-secret-bundles-dev.sh prepare`
   建立兩個 merged version、`janus-codex-owners-bundle` 與 bounded IAM。
2. 部署 API、Web、Pipeline、Agent、Mart、Ingestion 新映像與 Secret references。
3. 執行 targeted tests、bundle runtime probes、A／B entry rotate／destroy isolation
   與 log payload 檢查。
4. 驗收通過後，另設 `ALLOW_SECRET_BUNDLE_CLEANUP=true` 執行 `cleanup`，刪除六個
   legacy containers；驗收失敗時不得 cleanup。

## 遷移前 Runtime reference（2026-09-11）

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
