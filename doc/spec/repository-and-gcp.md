# Janus SPEC — Monorepo 與 GCP 拓撲

## 3. Monorepo 結構

```text
janus-omniforge/
├── apps/
│   ├── user_app/                    # Flutter + Material 3 User App
│   └── web/                         # 現有 Admin Web，遷移後不承載 public UI
├── jobs/
│   ├── ingestion-core/              # Scrapers、Stage、DQ、Core
│   └── intelligence-mart/           # Features、ML、Agents、LLM、Mart
├── services/
│   ├── api/                         # FastAPI public/private/admin API
│   └── agent-gateway/               # Cloud Run 私人助理、providers、Codex／MCP host
├── packages/
│   ├── contracts/                   # Schema、events、API types
│   ├── governance/                  # Parameters、publication policy
│   ├── provenance/                  # Provenance model／validation
│   ├── observability/               # Logging、metrics、errors
│   └── duckdb_query/                # bounded DuckDB／Iceberg read-write primitives
├── infra/                            # GitHub Actions／gcloud／Cloud Build／IAM
├── tests/
│   ├── contract/
│   └── e2e/
└── docs/
```

主要執行／部署單元：

1. `ingestion-core`：Cloud Run Job。
2. `intelligence-mart`：Cloud Run Job。
3. `api`：FastAPI Cloud Run Service，提供 public、private-journal 與 Admin API；Core query 使用獨立、read-only 的內嵌 DuckDB instance。
4. `admin-web`：受限制的 Admin Web 入口，只調用 Admin API。
5. `agent-gateway`：`min-instances=0` 的 Cloud Run Service；在容器內啟動 Codex App Server／stdio MCP 子行程，對 client 只公開 authenticated HTTPS events／commands。
6. `mcp-*`：需獨立擴縮的 remote MCP 使用私有 Cloud Run Service；stdio-only MCP 建入 `agent-gateway` image，不在使用者裝置執行。
7. `user-app`：Flutter Android／iOS／Web client，只調用 Public／Private API 與 Agent Gateway，不持有 provider、MCP、catalog、control DB 或 GCS credential；不新增 React／Tauri desktop client。

## 4. GCP 拓撲

```mermaid
flowchart TD
    A["Cloud Scheduler"] --> B["Pub/Sub ingestion command"]
    B --> C["Ingestion + Core Job"]
    C --> D["GCS Stage"]
    C --> E["Embedded DuckDB / PyIceberg"]
    E --> F["GCS Core / Iceberg"]
    F --> G["Core-ready event"]
    G --> H["Mart + ML / AI / LLM Job"]
    H --> I["GCS Mart / Iceberg"]
    H --> J["PostgreSQL publication index"]
    I --> K["FastAPI Service"]
    J --> K
    K --> M["Flutter User App"]
    K --> N["Admin Web"]
    M -->|"manual journal"| K
    K --> O["PostgreSQL private ledger"]
    O --> P["Private Iceberg Core / Mart"]
    P --> K
    F --> L["Read-only DuckDB query instance"]
    L --> K
    M --> Q["Cloud Run Agent Gateway"]
    Q --> R["Codex App Server + stdio MCP child processes"]
    Q --> S["Private Cloud Run MCP services"]
    Q --> T["OpenRouter / Gemini REST"]
    L --> Q
    P --> Q
    Q --> U["Private conversation / skill artifacts"]
```

建議區域：`us-central1`。開發初期可使用單一 `janus-dev` project。六個月 Dev
Pilot 後只有人工 `GO` 才開始 Production topology review；是否需要 separate
staging、separate production project 或 three-project split，由 Pilot evidence
決定，不預先建立。
