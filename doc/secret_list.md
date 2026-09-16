# GCP Dev Secret Bundle 清單

更新日期：2026-09-13
Project：`gen-lang-client-0593591102`  
Region：`us-central1`

本文件只記錄 Secret resource、欄位名稱、consumer、版本狀態與 IAM metadata，
不記錄 payload、token、password、API key 或 auth 內容。GCP dev 已完成收斂，
目前只保留 4 個 Secret container、3 個 enabled versions。

| Secret | 欄位／格式（不含值） | Consumer | Version | IAM |
|---|---|---|---|---|
| `janus-postgres-api-bundle` | API 欄位；`web_*`、`pipeline_*` workload 欄位；含 `web_publication_password` | `janus-api`、`janus-private-pipeline` | v15 enabled；舊版 preserved／未輸出 payload | API／private pipeline `secretAccessor`；legacy `web-runtime` removed |
| `janus-agent-provider-bundle` | provider／MCP 欄位；`mart_*`、`ingestion_*` workload 欄位 | `janus-agent-gateway`、`janus-intelligence-mart`、`janus-ingestion-core` | v8 enabled；舊版 destroyed | 三 runtime `secretAccessor`；Gateway provider access |
| `janus-market-data-bundle` | `finmind_api_token`、`fugle_api_key`、Fugle license／benchmark metadata、`shioaji_api_key`／`shioaji_secret_key`／simulation、`tiingo_api_key` | `janus-ingestion-core` | v1 enabled | 僅 ingestion-core `secretAccessor` |
| `janus-codex-owners-bundle` | 頂層 key 為 allowlisted owner UUID；value 為該 owner 的 Codex `auth.json` object | Agent Gateway | 無 enabled version（尚未建立 auth entry） | Gateway `secretAccessor`、`secretVersionAdder`、`secretVersionManager` |

## 欄位規則

- API／Web／Pipeline 的同名 credential 不互相覆蓋；合併欄位使用 `web_*`、
  `pipeline_*` prefix。Agent／Mart／Ingestion 同理使用 `mart_*`、`ingestion_*`。
- `janus-agent-provider-bundle` 是 MCP signing key 的唯一來源。
- `janus-market-data-bundle` 僅保存 data-source provider credentials；目前只綁定
  `ingestion-core`，不會自動啟用尚未核准或尚未實作的 adapter。`fugle_benchmark_symbol`
  目前為空值，待 Source Matrix／provider scope 確認後再填入。
- Codex A/B 共用 Secret resource，但 auth payload 以 owner UUID 分區；每個 owner
  仍使用隔離的 `CODEX_HOME` 與 App Server process。
- Codex rotate 採 read-modify-write：建立並驗證新 version 後銷毀舊 version；destroy
  只移除目標 owner entry。Cloud Run 目前 `max-instances=1`，程式以 process lock
  序列化 mutation；提高 instance 數前必須改用 distributed lock／CAS。

WBS-7 dev IAM verify（2026-09-13）確認 `janus-web` service 不存在，
`janus-postgres-api-bundle` 不再授權 `web-runtime`；API 與 private pipeline 使用
分離 runtime identity。其他 secret consumers 依表格列示，未擴大 blast radius。
- 新版 PostgreSQL loader 在遷移期間支援舊欄位 fallback；legacy containers 已刪除後，
  fallback 僅作 rollback compatibility，不應再新增舊欄位。

## GCP migration evidence

- `migrate-secret-bundles-dev.sh prepare` 建立並驗證 API v14、Agent v8，並將舊 merged
  versions 設為 `DESTROYED`。
- API、Web、Pipeline 已切換至 `janus-postgres-api-bundle:latest`；Agent、Mart、
  Ingestion 已切換至 `janus-agent-provider-bundle:latest`。
- Gateway revision `janus-agent-gateway-00042-kj2` 使用 provider bundle，Codex owner
  mapping 指向 `janus-codex-owners-bundle`。
- 六個 legacy containers（Web／Pipeline／Mart／Ingestion 舊 bundle、Codex A/B）已在
  明確授權後刪除；刪除前所有 legacy versions 均已確認 destroyed，沒有 active payload
  被刪除。

## Runtime acceptance

- Python targeted tests：14 passed；Agent Gateway tests：10 passed。
- Agent Gateway TypeScript build、Git Bash `bash -n`、Cloud Build contract 均通過；
  contract build：`6bb119e7-da07-4ec2-b52b-3f1f1170a649`。
- Mart smoke：`janus-intelligence-mart-mrz8q`；Pipeline smoke：
  `janus-private-pipeline-8vxnm`；Ingestion smoke：`janus-ingestion-core-7qxbx`，均
  `Completed=True`。
- Codex A/B live auth rotate／destroy isolation 尚未驗證，因新 owner bundle 目前沒有
  active auth entry；建立 dev owner auth 後需重新執行該項驗收。

## Cost note

Secret Manager active versions 與 access operations 才是主要計費項目；若 billing
account 沒有其他 project 的 active versions，目前 3 個 enabled versions 低於每月
6 個免費額度。Secret container 與 management operations 本身不收費。
