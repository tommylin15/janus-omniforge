# GCP Dev Secret Bundle 清單

更新日期：2026-09-23
Project：`gen-lang-client-0593591102`  
Region：`us-central1`

本文件只記錄 Secret resource、欄位名稱、consumer、版本狀態與 IAM metadata，
不記錄 payload、token、password、API key 或 auth 內容。GCP dev 已完成收斂，
目前只保留 1 個 Janus Secret container、1 個 enabled version。資料庫、OAuth、Mart／Ingestion 與市場資料 provider 欄位合併於 `janus-runtime-bundle`；舊 bundle 已清除。

| Secret | 欄位／格式（不含值） | Consumer | Version | IAM |
|---|---|---|---|---|
| `janus-runtime-bundle` | PostgreSQL、Web/Pipeline、OAuth、Mart／Ingestion、provider／market-data 欄位；28 個唯一欄位 | Janus API、private pipeline、ingestion-core、intelligence-mart、PostgreSQL migration build | v2 enabled；v1 disabled | 四個 Janus runtime service accounts 與 Cloud Build default identity 有直接 `secretAccessor` binding；另承接既有 project-level `omniforge-dev-runtime` accessor |

## 欄位規則

- API／Web／Pipeline、Mart／Ingestion 欄位保持既有 key 名；合併採 key union，重複的
  `mcp_owner_signing_key` 僅在來源值一致時合併，沒有衝突。
- 市場資料 credentials 僅合併儲存，不代表啟用 Fugle／Shioaji／Tiingo adapters 或改變
  Source Matrix 核准狀態。
- Janus Codex owners bundle 已在先前 cleanup 刪除，沒有 payload；本次未重建。

WBS-7 dev IAM verify（2026-09-13）確認 `janus-web` service 不存在，
API 與 private pipeline 使用分離 runtime identity。2026-09-23 依使用者核准將
所有 Janus runtime secrets 合併；單一 bundle 的資源層級 IAM 會讓四個 runtime identities
及 Cloud Build default identity 可讀完整欄位，無欄位級隔離。
- 新版 PostgreSQL loader 在遷移期間支援舊欄位 fallback；legacy containers 已刪除後，
  fallback 僅作 rollback compatibility，不應再新增舊欄位。

## GCP migration evidence

- `migrate-secret-bundles-dev.sh prepare` 建立並驗證 API v14、Agent v8，並將舊 merged
  versions 設為 `DESTROYED`。
- 歷史 API／Web／Pipeline 曾使用 `janus-postgres-api-bundle`；Agent／Mart／Ingestion
  曾使用 `janus-agent-provider-bundle`。
- Janus Agent Gateway revisions historically used the provider bundle and Codex owner
  bundle; these references are historical after the 2026-09-23 split cleanup.
- 六個 legacy containers（Web／Pipeline／Mart／Ingestion 舊 bundle、Codex A/B）已在
  明確授權後刪除；刪除前所有 legacy versions 均已確認 destroyed，沒有 active payload
  被刪除。

## 2026-09-19 Secret bundle recovery evidence

- Audit Log 記錄 `janus-postgres-api-bundle` 的 `DeleteSecret` 於
  `2026-09-19T13:07:53.896564036Z`；刪除後 container 與 versions 均回傳 `NOT_FOUND`。
- 以相同 secret name 重建 API container，新增並驗證 v1；payload 只在暫存檔處理，未寫入
  本文件或輸出至 log。
- 重新輪替 `janus_private_api`、`janus_private_pipeline`、`janus_catalog`、
  `janus_web_control`、`janus_web_catalog`、`janus_public_api` 六個 PostgreSQL roles；
  驗證六者均為非 superuser／非 createdb／非 createrole／非 replication。
- Agent bundle 新增並驗證 v9，使用新的 matching MCP owner signing key；舊 v8 僅停用，
  未銷毀，以保留可恢復性。API bundle accessor IAM 已恢復給 `janus-user-api` 與
  `janus-private-pipeline`。
- Recovery 後 `janus-api-00127-sqp` 與 `janus-agent-gateway-00044-jtn` 均為 Ready；
  `MCP_OAUTH_ENABLED=false` 仍維持，OAuth／ChatGPT connector acceptance 尚未因此宣稱完成。

## Runtime acceptance

2026-09-23 unified bundle migration replaced the three extant Janus bundles with
`janus-runtime-bundle`. Janus API, private pipeline, ingestion-core, mart, and the
PostgreSQL migration build use the unified resource. The previous Codex owners
bundle was already absent and had no payload. Secret values were merged in memory;
only field names and conflict status were emitted. Candidate and canonical API,
MCP/OAuth, and User/Admin UI acceptance passed. The single-bundle resource-level
access widening was approved.

On 2026-09-23, read-only Cloud Run PostgreSQL probes found stale credentials for
`janus_catalog` and `janus_private_pipeline`; the bundle's consumer aliases for the
shared `janus_catalog` role were inconsistent. The existing dev DB roles were
reconciled to the canonical bundle values, v2 normalized those aliases, and v1 was
disabled. A Cloud Run read-only `SELECT 1` probe passed for catalog aliases,
`pipeline_database_url`, and the ingestion control role. Both Job templates are
Ready, reference `janus-runtime-bundle:latest`, and their configured image digests
exist. After scoped approval, private-pipeline execution
`janus-private-pipeline-skpmx` completed successfully at checkpoint 68. Bounded
ingestion execution `janus-ingestion-core-hn9mh` completed successfully for taiex
on 2026-09-22 with `FORCE_REFRESH=false`; it staged one object and created one
Core Iceberg table with 64 rows, and did not trigger Mart. No multi-month backfill
was run. An initial bounded invocation had malformed CLI overrides and exited
before source collection; the corrected execution-only overrides passed.
Historical failed executions remain in Cloud Run history.

- Python targeted tests：14 passed；Agent Gateway tests：10 passed。
- Agent Gateway TypeScript build、Git Bash `bash -n`、Cloud Build contract 均通過；
  contract build：`6bb119e7-da07-4ec2-b52b-3f1f1170a649`。
- Mart smoke：`janus-intelligence-mart-mrz8q`；Pipeline smoke：
  `janus-private-pipeline-8vxnm`；Ingestion smoke：`janus-ingestion-core-7qxbx`，均
  `Completed=True`。
- Codex A/B auth rotate／destroy isolation 不再是 Janus 驗收項目；Janus generic Codex runtime 與 owners bundle 已移除。omniAgent auth lifecycle 由其自身 acceptance 追蹤。

## Cost note

Secret Manager active versions 與 access operations 才是主要計費項目；Janus 目前
使用 1 個 enabled version。帳戶免費額度仍取決於其他 project 的 active versions。
Secret container 與 management operations 本身不收費。
