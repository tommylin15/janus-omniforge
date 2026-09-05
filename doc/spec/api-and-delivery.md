# Janus SPEC — API、User、Admin 與交付

## 12. User、Admin 與 API

- Flutter User App 與 Admin Web 為兩個獨立入口；User 導覽不顯示 Admin，Admin 必須通過獨立認證與授權。
- FastAPI 作為共用 HTTP boundary，但 `/api/v1/public/*`、`/api/v1/me/*` 與 `/api/v1/admin/*` 分離 router、response model、auth、rate limit、CORS 與 audit policy。
- 公開端只讀 publishable Mart／service index，不直讀 Iceberg catalog owner 或 control schema。
- 404 不觸發即時爬蟲、Agent 或 LLM。
- Admin 只寫 control DB／queue，不在 request 中執行長任務。
- Admin「資料營運中心」保留為資料操作入口；`/admin/stocks` 右側一次只呈現一個分頁面板，不把所有管理功能同時展開。
- 股票資料狀態以可排序、篩選、分頁的欄列表格呈現，不以原始 JSON 作主要 UI；巢狀 DQ／quarantine／execution 明細亦轉為子表或定義清單。
- 第一階段只開放 Collection／backfill；Analysis action 與「Mart 分析」必須 hidden／disabled，且不得建立無 consumer 的 queued execution。完成 Mart persisted queue consumer 後才啟用。
- Admin 可按 market／industry／symbol scope 檢視已持久化的 `mart_scoped_analysis`；讀取不得觸發即時 Agent。Prompt 由 repository 版控，不提供 Admin 編輯。
- blocked report、raw payload、secret、traceback、broker data 不得公開。
- User App 主頁以 `mart_daily_brief` 為唯一首屏資料入口；個股健檢讀取 `mart_candidate_health` 與可定位 evidence，前端不重算健康度。
- `/api/v1/me/journal/*`、`/api/v1/me/notes/*`、`/api/v1/me/watchlist/*`、`/api/v1/me/chats/*`、`/api/v1/me/portfolio/*` 與 `/api/v1/me/investment-profile` 只允許 authenticated user 存取自己的資料。所有 query 與 index 以 `user_id` 作為所有權邊界；不接受 client 指定他人 `user_id`。
- Chat engine/profile 受控字彙為 `codex | chatgpt | gemini`。每個 conversation 建立後固定其值；切換建立新 conversation／fork，不在同一 lineage 中無痕更換 provider。所有回答顯示 engine、model、資料日期、是否使用外部搜尋與 citations。
- `codex`／`chatgpt` 只經 Codex App Server subscription auth；`gemini` 只經伺服器端 `GEMINI_API_KEY` 使用 Gemini Developer API 免費層。禁止 client 傳入 provider credential，禁止任何聊天室工具寫入交易、筆記、watchlist、檔案系統或 Admin control plane。
- User token 只接受 User OAuth audience 並只授權 `/api/v1/me/*`；不得用於 `/api/v1/admin/*`。Admin token／session 亦不因具管理權限而取得一般交易內容讀取能力。
- User 可匯出自己的交易、筆記、關注股與對話資料並要求刪除私人資料；刪除採可稽核、可重試的非同步流程，涵蓋 PostgreSQL、Private Core／Mart、Codex local thread/auth state 與 service cache，且不影響依法或安全要求保留的最小 audit metadata。
- 交易日誌／PnL 納入私人 MVP；市場投票排行榜、遊戲化、付費、公開績效排名與券商同步不在當前範圍。
- 個人記帳、筆記、關注股與私人聊天室可在公開 Mart 前獨立上線至 dev；未完成的「今日／公開探索」只顯示 coming soon，不得因此觸發即時分析或阻擋私人功能。
- UI 詳細契約見 `../ui.md`。

## 13. GCP 開發與 CI/CD

| 項目 | 選擇 |
|---|---|
| 開發環境 | Cloud Workstations；低頻可用 Cloud Shell Editor |
| 原始碼 | GitHub monorepo、branch protection、PR review |
| GCP 認證 | Workload Identity Federation，不使用長效 JSON key |
| 建置 | Cloud Build path-based pipelines |
| Image | Artifact Registry，由 source deploy／Cloud Build 管理 |
| 部署 | 同一 immutable image digest 依序 promote dev → staging → prod |
| Secret | Secret Manager，runtime identity 單項授權 |
| IaC | GitHub Actions／gcloud idempotent scripts；production apply 需人工批准 |

### 13.1 Dev PostgreSQL VM

- 使用 Compute Engine `e2-micro`，只承載 control plane、Iceberg catalog、publication index、audit metadata 與低流量私人交易 ledger；GCS／Iceberg 不搬到 VM。
- PostgreSQL 使用 private IP；Cloud Run、Cloud Run Jobs 與 DuckDB 所在 runtime 僅透過 VPC 連線，禁止公開 `5432`。
- VM 使用 Standard Persistent Disk，Free Tier 模式總配置量 ≤30 GB；不自動建立 snapshot／backup，資料庫 credential 存 Secret Manager。任何備份與 restore drill 必須另行評估費用。
- `e2-micro` 只有 1 GiB RAM，僅限 dev／MVP 低併發；私人 ledger 必須有 bounded query、retention／export 與容量告警。production 必須重新評估 dedicated VM、HA 或其他 managed PostgreSQL 方案。
- Free Tier 目標另受 billing account 資格、每月 1 GB outbound 額度與其他 GCP 資源費用影響；gcloud bootstrap guard 不等於保證帳單為 US$0。
- Compute Engine 與 Standard Persistent Disk 依 instance 運轉時間、provisioned disk、snapshot 與網路流量計費；實際價格以 [Compute Engine pricing](https://cloud.google.com/products/compute/pricing) 為準。

PostgreSQL VM 是 Iceberg SQL catalog 與 control DB 的前置基礎；必須先完成 VM、private connectivity、schema／role bootstrap、PostgreSQL repository migration 與 smoke query，才可部署內嵌 DuckDB 的 Cloud Run runtime。SQLite control repository 僅供 unit tests，不是 production backend。

### 13.2 Artifact Registry cost guard

- Cloud Build 可 build、push image、解析 immutable digest 與執行 cleanup；不得呼叫 Artifact Analysis API、Container Scanning API、vulnerability scanning 或 occurrence API。
- SBOM 如有需要，使用本地工具產生 SPDX／CycloneDX，作為一般 build artifact 保存；不建立掃描 occurrence，也不等待 vulnerability result。

Schema evolution、migration、backfill、production Job trigger 不得隨 API、Admin Web 或 User App deployment 自動執行。
